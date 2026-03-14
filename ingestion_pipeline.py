import os
import json
import csv
import time
import requests
from collections import Counter
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
SERVER_URL = os.getenv("JELLYFIN_URL")
API_KEY = os.getenv("JELLYFIN_API_KEY")

# --- Thresholds ---
MIN_MEDIA_PER_TAG = 5
MIN_TAGS_PER_MEDIA = 12
BATCH_SIZE = 20

def get_admin_user(headers):
    response = requests.get(f"{SERVER_URL}/Users", headers=headers)
    if response.status_code == 200:
        for user in response.json():
            if user.get("Policy", {}).get("IsAdministrator"):
                return user.get("Id")
    return None

def clean_noisy_tags(headers, admin_id):
    print("\n--- STEP 1: CLEAN AND LOCK NOISY TAGS ---")
    params = {"IncludeItemTypes": "Movie,Series", "Recursive": "true", "Fields": "Tags,LockedFields"}
    response = requests.get(f"{SERVER_URL}/Items", headers=headers, params=params)
    if response.status_code != 200:
        print("Error fetching data.")
        return
        
    items = response.json().get("Items", [])
    tag_counts = Counter()
    
    for item in items:
        standard_tags = [t for t in item.get("Tags", []) if not t.lower().startswith(("franchise:", "universe:", "dependson:"))]
        tag_counts.update(standard_tags)
        
    tags_to_delete = {tag for tag, count in tag_counts.items() if count < MIN_MEDIA_PER_TAG}
    keys_to_remove = ["UserData", "ImageTags", "BackdropImageTags", "Chapters", "MediaSources", "MediaStreams", "ImageBlurHashes", "Trickplay", "PrimaryImageAspectRatio", "OriginalPrimaryImageAspectRatio", "ServerId", "Etag", "PlayAccess", "ThemeSongIds", "ThemeVideoIds"]
    
    updated_count = 0
    for item in items:
        item_id = item.get("Id")
        current_tags = item.get("Tags", [])
        current_locked = item.get("LockedFields", [])
        
        new_tags = [t for t in current_tags if t.lower().startswith(("franchise:", "universe:", "dependson:")) or t not in tags_to_delete]
        needs_purge = len(new_tags) != len(current_tags)
        is_locked = "Tags" in current_locked
        
        if needs_purge or not is_locked:
            full_item_response = requests.get(f"{SERVER_URL}/Users/{admin_id}/Items/{item_id}", headers=headers)
            if full_item_response.status_code != 200:
                full_item_response = requests.get(f"{SERVER_URL}/Items/{item_id}", headers=headers, params={"userId": admin_id})
                
            if full_item_response.status_code == 200:
                full_item = full_item_response.json()
                for key in keys_to_remove: full_item.pop(key, None)
                
                if needs_purge:
                    full_item["Tags"] = new_tags
                    full_item["LockedFields"] = [f for f in full_item.get("LockedFields", []) if f != "Tags"]
                    requests.post(f"{SERVER_URL}/Items/{item_id}", headers=headers, json=full_item)
                
                locked_fields = full_item.get("LockedFields", [])
                if "Tags" not in locked_fields:
                    locked_fields.append("Tags")
                    full_item["LockedFields"] = locked_fields
                    requests.post(f"{SERVER_URL}/Items/{item_id}", headers=headers, json=full_item)
                updated_count += 1
                
    print(f"Cleaned and locked {updated_count} items.")

def apply_tag_mapping(headers, admin_id):
    print("\n--- STEP 2: APPLY TAG MAPPING ---")
    try:
        with open("tag_mapping.json", "r", encoding="utf-8") as f:
            mapping = json.load(f)
    except FileNotFoundError:
        print("tag_mapping.json not found. Skipping mapping.")
        return

    params = {"IncludeItemTypes": "Movie,Series", "Recursive": "true", "Fields": "Tags,LockedFields"}
    response = requests.get(f"{SERVER_URL}/Items", headers=headers, params=params)
    if response.status_code != 200: return
        
    items = response.json().get("Items", [])
    keys_to_remove = ["UserData", "ImageTags", "BackdropImageTags", "Chapters", "MediaSources", "MediaStreams", "ImageBlurHashes", "Trickplay", "PrimaryImageAspectRatio", "OriginalPrimaryImageAspectRatio", "ServerId", "Etag", "PlayAccess", "ThemeSongIds", "ThemeVideoIds"]
    updated_count = 0

    for item in items:
        current_tags = item.get("Tags", [])
        if not current_tags: continue
            
        new_tags = set()
        needs_update = False
        
        for tag in current_tags:
            if tag in mapping:
                needs_update = True
                replacement = mapping[tag]
                if isinstance(replacement, list): new_tags.update(replacement)
                else: new_tags.add(replacement)
            else:
                new_tags.add(tag)
                
        if needs_update:
            item_id = item.get("Id")
            final_tags = sorted(list(new_tags))
            full_item_response = requests.get(f"{SERVER_URL}/Users/{admin_id}/Items/{item_id}", headers=headers)
            if full_item_response.status_code != 200:
                full_item_response = requests.get(f"{SERVER_URL}/Items/{item_id}", headers=headers, params={"userId": admin_id})
                
            if full_item_response.status_code == 200:
                full_item = full_item_response.json()
                for key in keys_to_remove: full_item.pop(key, None)
                
                full_item["Tags"] = final_tags
                full_item["LockedFields"] = [f for f in full_item.get("LockedFields", []) if f != "Tags"]
                requests.post(f"{SERVER_URL}/Items/{item_id}", headers=headers, json=full_item)
                
                locked_fields = full_item.get("LockedFields", [])
                if "Tags" not in locked_fields:
                    locked_fields.append("Tags")
                    full_item["LockedFields"] = locked_fields
                    requests.post(f"{SERVER_URL}/Items/{item_id}", headers=headers, json=full_item)
                updated_count += 1
                
    print(f"Normalized tags on {updated_count} items.")

def generate_ai_suggestions(headers):
    print("\n--- STEP 3: GENERATE AI SUGGESTIONS ---")
    try:
        with open("tag_library.json", "r", encoding="utf-8") as f:
            tag_library = json.load(f)
    except FileNotFoundError:
        print("tag_library.json not found. Skipping AI generation.")
        return

    client = genai.Client()
    params = {"IncludeItemTypes": "Movie,Series", "Recursive": "true", "Fields": "Tags,Overview,ProductionYear"}
    response = requests.get(f"{SERVER_URL}/Items", headers=headers, params=params)
    if response.status_code != 200: return
        
    items = response.json().get("Items", [])
    
    # Check existing CSV to avoid wasting quota on already-processed items
    csv_file = "proposed_tags.csv"
    processed_ids = set()
    file_exists = os.path.isfile(csv_file)
    
    if file_exists:
        with open(csv_file, mode="r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            processed_ids = {row["Item ID"] for row in reader}

    # Filter out items that have 12+ tags OR are already sitting in the CSV
    sparse_items = [
        item for item in items 
        if len(item.get("Tags", [])) < MIN_TAGS_PER_MEDIA and item.get("Id") not in processed_ids
    ]
    
    print(f"Found {len(sparse_items)} items needing tags (excluding items already in CSV).")
    if not sparse_items: return
    
    with open(csv_file, mode="a" if file_exists else "w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(["Item ID", "Title", "Year", "Current Tags", "Proposed Tags"])
        
        for i in range(0, len(sparse_items), BATCH_SIZE):
            chunk = sparse_items[i:i + BATCH_SIZE]
            print(f"Processing Batch {i // BATCH_SIZE + 1}...")
            
            media_payload = []
            item_lookup = {} 
            
            for item in chunk:
                item_id = item.get("Id")
                title = item.get("Name", "Unknown Title")
                year = item.get("ProductionYear", "Unknown Year")
                overview = item.get("Overview", "No overview available.")
                current_tags = item.get("Tags", [])
                
                item_lookup[item_id] = {"title": title, "year": year, "current_tags": current_tags}
                media_payload.append({"id": item_id, "title": title, "year": year, "overview": overview})

            prompt = f"""
            You are a media metadata expert. Analyze the following JSON array of media items:
            {json.dumps(media_payload, indent=2)}

            For EACH item, select between 12 and 15 tags EXCLUSIVELY from the Allowed Tags list.
            Only apply a tag if highly confident. Do not invent new tags. 

            Specific Definitions:
            - "ensemble cast": The media has at least four principal actors with roughly equal screen time and importance to the plot.
            - "bechdel pass": The movie has to have at least two named women in it who talk to each other about something besides a man.
            - "bechdel fail": The media does not feature two named women talking to each other about something other than a man.
            CRITICAL RULE FOR BECHDEL TAGS: Do NOT guess. If you do not have absolute, concrete knowledge of the specific scenes in the media to verify the Bechdel test, you MUST omit both Bechdel tags entirely. It is better to apply neither tag than to guess incorrectly.
            
            Allowed Tags:
            {json.dumps(tag_library)}

            Return ONLY a valid JSON array of objects, where each object has exactly two keys: "id" and "tags" (array of strings).
            """

            try:
                ai_response = client.models.generate_content(
                    model='gemini-3-flash-preview',
                    contents=prompt,
                    # THE FIX: Added max_output_tokens=8192 below
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json", 
                        temperature=0.2,
                        max_output_tokens=8192
                    )
                )
                
                raw_text = ai_response.text.strip()
                if raw_text.startswith("```json"):
                    raw_text = raw_text[7:]
                if raw_text.startswith("```"):
                    raw_text = raw_text[3:]
                if raw_text.endswith("```"):
                    raw_text = raw_text[:-3]
                    
                raw_text = raw_text.strip()
                batch_results = json.loads(raw_text)
                
                for result in batch_results:
                    res_id = result.get("id")
                    if res_id in item_lookup:
                        meta = item_lookup[res_id]
                        writer.writerow([res_id, meta["title"], meta["year"], ", ".join(meta["current_tags"]), ", ".join(result.get("tags", []))])
                        
            except json.JSONDecodeError as e:
                print(f"JSON Parsing Error: {e}")
                print(f"Raw AI Output for debugging:\n{ai_response.text}")
            except Exception as e:
                error_msg = str(e).lower()
                # Hard fail on quota exhaustion
                if "429" in error_msg or "quota" in error_msg or "exhausted" in error_msg:
                    print(f"\n⚠️ API Rate Limit or Quota Reached: {e}")
                    print("Stopping generation. Your progress is saved in proposed_tags.csv.")
                    break
                else:
                    print(f"Failed to process batch: {e}")
            
            time.sleep(4)
            
    print(f"Suggestions generated and appended to {csv_file}.")

def main():
    print("Starting Jellyfin Ingestion Pipeline...")
    headers = {
        "Authorization": f"MediaBrowser Token={API_KEY}",
        "Content-Type": "application/json"
    }
    
    admin_id = get_admin_user(headers)
    if not admin_id:
        print("Error: Could not authenticate Administrator user.")
        return

    clean_noisy_tags(headers, admin_id)
    apply_tag_mapping(headers, admin_id)
    generate_ai_suggestions(headers)
    print("\nPipeline Complete! Review proposed_tags.csv and run commit_tags.py when ready.")

if __name__ == "__main__":
    main()
