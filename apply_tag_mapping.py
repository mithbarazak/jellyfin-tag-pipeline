import os
import json
import requests
from dotenv import load_dotenv

# Load environment variables
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

def apply_mapping():
    # 1. Load the Mapping
    try:
        with open("tag_mapping.json", "r", encoding="utf-8") as f:
            mapping = json.load(f)
    except FileNotFoundError:
        print("Error: tag_mapping.json not found.")
        return

    headers = {
        "Authorization": f"MediaBrowser Token={API_KEY}",
        "Content-Type": "application/json"
    }
    
    admin_id = get_admin_user(headers)
    if not admin_id:
        print("Error: Could not find an Administrator user.")
        return

    params = {
        "IncludeItemTypes": "Movie,Series",
        "Recursive": "true",
        "Fields": "Tags,LockedFields"
    }
    
    print("Fetching library items...")
    response = requests.get(f"{SERVER_URL}/Items", headers=headers, params=params)
    if response.status_code != 200:
        print(f"Error fetching data: {response.status_code}")
        return
        
    items = response.json().get("Items", [])
    
    keys_to_remove = [
        "UserData", "ImageTags", "BackdropImageTags", "Chapters", 
        "MediaSources", "MediaStreams", "ImageBlurHashes", "Trickplay",
        "PrimaryImageAspectRatio", "OriginalPrimaryImageAspectRatio",
        "ServerId", "Etag", "PlayAccess", "ThemeSongIds", "ThemeVideoIds"
    ]
    
    updated_count = 0

    # 2. Process Items
    for item in items:
        current_tags = item.get("Tags", [])
        if not current_tags:
            continue
            
        new_tags = set()
        needs_update = False
        
        for tag in current_tags:
            if tag in mapping:
                needs_update = True
                replacement = mapping[tag]
                # Handle both string replacements and list replacements (e.g., killer robot -> murder, robot)
                if isinstance(replacement, list):
                    new_tags.update(replacement)
                else:
                    new_tags.add(replacement)
            else:
                new_tags.add(tag)
                
        if not needs_update:
            continue
            
        # Convert set back to sorted list
        final_tags = sorted(list(new_tags))
        item_id = item.get("Id")
        item_name = item.get("Name", "Unknown")
        
        # Fetch full record for the POST payload
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
                print(f"Failed to update tags for {item_name}. Status: {purge_response.status_code}")
                continue
                
            # PHASE 2: RE-LOCK
            locked_fields = full_item.get("LockedFields", [])
            if "Tags" not in locked_fields:
                locked_fields.append("Tags")
                full_item["LockedFields"] = locked_fields
                
                lock_response = requests.post(f"{SERVER_URL}/Items/{item_id}", headers=headers, json=full_item)
                if lock_response.status_code in (200, 204):
                    updated_count += 1
                    print(f"Success: Normalized tags for {item_name}")
                else:
                    print(f"Failed to re-apply lock to {item_name}.")
        else:
            print(f"Failed to GET record for {item_name}.")

    print(f"\nOperation complete! Successfully normalized tags on {updated_count} media items.")

if __name__ == "__main__":
    apply_mapping()
