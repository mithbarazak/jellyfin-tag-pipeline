import os
import csv
import time
import requests
from dotenv import load_dotenv

load_dotenv()
SERVER_URL = os.getenv("JELLYFIN_URL")
API_KEY = os.getenv("JELLYFIN_API_KEY")

def get_admin_user(headers):
    response = requests.get(f"{SERVER_URL}/Users", headers=headers)
    if response.status_code == 200:
        for user in response.json():
            if user.get("Policy", {}).get("IsAdministrator"):
                return user.get("Id")
    return None

def commit_approved_tags():
    csv_file = "proposed_tags.csv"
    try:
        with open(csv_file, mode="r", encoding="utf-8") as file:
            reader = csv.DictReader(file)
            rows = list(reader)
    except FileNotFoundError:
        print(f"Error: '{csv_file}' not found. There is nothing to commit.")
        return

    headers = {
        "Authorization": f"MediaBrowser Token={API_KEY}",
        "Content-Type": "application/json"
    }
    
    admin_id = get_admin_user(headers)
    if not admin_id:
        print("Error: Could not find an Administrator user.")
        return

    keys_to_remove = [
        "UserData", "ImageTags", "BackdropImageTags", "Chapters", 
        "MediaSources", "MediaStreams", "ImageBlurHashes", "Trickplay",
        "PrimaryImageAspectRatio", "OriginalPrimaryImageAspectRatio",
        "ServerId", "Etag", "PlayAccess", "ThemeSongIds", "ThemeVideoIds"
    ]

    updated_count = 0

    print("Committing approved tags to Jellyfin...")

    for row in rows:
        item_id = row["Item ID"]
        title = row["Title"]
        
        current_tags = [t.strip() for t in row["Current Tags"].split(",") if t.strip()]
        proposed_tags = [t.strip() for t in row["Proposed Tags"].split(",") if t.strip()]
        
        final_tags = sorted(list(set(current_tags + proposed_tags)))

        full_item_response = requests.get(f"{SERVER_URL}/Users/{admin_id}/Items/{item_id}", headers=headers)
        if full_item_response.status_code != 200:
            full_item_response = requests.get(f"{SERVER_URL}/Items/{item_id}", headers=headers, params={"userId": admin_id})
            
        if full_item_response.status_code == 200:
            full_item = full_item_response.json()
            
            for key in keys_to_remove:
                full_item.pop(key, None)
                
            # PHASE 1: UNLOCK AND APPLY TAGS
            full_item["Tags"] = final_tags
            full_item["LockedFields"] = [f for f in full_item.get("LockedFields", []) if f != "Tags"]
            
            purge_response = requests.post(f"{SERVER_URL}/Items/{item_id}", headers=headers, json=full_item)
            if purge_response.status_code not in (200, 204):
                print(f"Failed to update tags for {title}. Status: {purge_response.status_code}")
                continue
                
            # PHASE 2: RE-LOCK
            locked_fields = full_item.get("LockedFields", [])
            if "Tags" not in locked_fields:
                locked_fields.append("Tags")
                full_item["LockedFields"] = locked_fields
                requests.post(f"{SERVER_URL}/Items/{item_id}", headers=headers, json=full_item)
                
            updated_count += 1
            print(f"Success: Committed {len(final_tags)} unique tags to '{title}'")
        else:
            print(f"Failed to fetch record for '{title}'.")

    print(f"\nOperation complete! Successfully updated {updated_count} media items.")
    
    # Safety Net: Archive the processed CSV
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    archived_filename = f"committed_tags_{timestamp}.csv"
    os.rename(csv_file, archived_filename)
    print(f"Archived '{csv_file}' to '{archived_filename}' to prevent accidental reprocessing.")

if __name__ == "__main__":
    commit_approved_tags()
