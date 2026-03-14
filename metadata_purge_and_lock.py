import requests
from collections import Counter

# --- Configuration ---
SERVER_URL = "http://192.168.0.101:8096" # Replace with your actual server URL
API_KEY = "e2f820c801a24955940d30b2d3fe67ac"            # Use your Jellyfin API key

# --- Thresholds ---
MIN_MEDIA_PER_TAG = 5

def get_admin_user(headers):
    response = requests.get(f"{SERVER_URL}/Users", headers=headers)
    if response.status_code == 200:
        for user in response.json():
            if user.get("Policy", {}).get("IsAdministrator"):
                return user.get("Id")
    return None

def clean_and_lock_tags():
    headers = {
        "Authorization": f"MediaBrowser Token={API_KEY}",
        "Content-Type": "application/json"
    }
    
    admin_id = get_admin_user(headers)
    if not admin_id:
        print("Error: Could not find an Administrator user. API key may lack permissions.")
        return
        
    print(f"Authenticated successfully. Admin User ID: {admin_id}")
    
    params = {
        "IncludeItemTypes": "Movie,Series",
        "Recursive": "true",
        "Fields": "Tags,LockedFields"
    }
    
    print("Scanning library to identify noisy tags...")
    response = requests.get(f"{SERVER_URL}/Items", headers=headers, params=params)
    
    if response.status_code != 200:
        print(f"Error fetching data: {response.status_code}")
        return
        
    items = response.json().get("Items", [])
    tag_counts = Counter()
    
    for item in items:
        standard_tags = [
            t for t in item.get("Tags", [])
            if not t.lower().startswith(("franchise:", "universe:", "dependson:"))
        ]
        tag_counts.update(standard_tags)
        
    tags_to_delete = {tag for tag, count in tag_counts.items() if count < MIN_MEDIA_PER_TAG}
    print(f"Identified {len(tags_to_delete)} unique noisy tags for removal.")
    
    updated_count = 0
    print("Beginning Two-Phase Update (Unlock/Purge -> Re-Lock)...")
    
    # Fields that cause 500 errors if sent back to the server
    keys_to_remove = [
        "UserData", "ImageTags", "BackdropImageTags", "Chapters", 
        "MediaSources", "MediaStreams", "ImageBlurHashes", "Trickplay",
        "PrimaryImageAspectRatio", "OriginalPrimaryImageAspectRatio",
        "ServerId", "Etag", "PlayAccess", "ThemeSongIds", "ThemeVideoIds"
    ]
    
    for item in items:
        item_id = item.get("Id")
        item_name = item.get("Name", "Unknown")
        current_tags = item.get("Tags", [])
        current_locked_fields = item.get("LockedFields", [])
        
        new_tags = [
            t for t in current_tags 
            if t.lower().startswith(("franchise:", "universe:", "dependson:")) 
            or t not in tags_to_delete
        ]
        
        needs_tag_purge = len(new_tags) != len(current_tags)
        is_currently_locked = "Tags" in current_locked_fields
        
        # We only need to act if there are garbage tags to remove, OR if the item is unlocked
        if needs_tag_purge or not is_currently_locked:
            full_item_response = requests.get(f"{SERVER_URL}/Users/{admin_id}/Items/{item_id}", headers=headers)
            
            if full_item_response.status_code != 200:
                full_item_response = requests.get(f"{SERVER_URL}/Items/{item_id}", headers=headers, params={"userId": admin_id})
                
            if full_item_response.status_code == 200:
                full_item = full_item_response.json()
                
                # Scrub read-only data to prevent the 500 error crash
                for key in keys_to_remove:
                    full_item.pop(key, None)
                
                # PHASE 1: UNLOCK AND PURGE
                if needs_tag_purge:
                    full_item["Tags"] = new_tags
                    # Explicitly remove the lock so the server accepts the new tags
                    full_item["LockedFields"] = [f for f in full_item.get("LockedFields", []) if f != "Tags"]
                    
                    purge_response = requests.post(f"{SERVER_URL}/Items/{item_id}", headers=headers, json=full_item)
                    if purge_response.status_code not in (200, 204):
                        print(f"Failed to purge tags for {item_name}. Status: {purge_response.status_code}")
                        continue 
                
                # PHASE 2: RE-LOCK
                locked_fields = full_item.get("LockedFields", [])
                if "Tags" not in locked_fields:
                    locked_fields.append("Tags")
                    full_item["LockedFields"] = locked_fields
                    
                    lock_response = requests.post(f"{SERVER_URL}/Items/{item_id}", headers=headers, json=full_item)
                    if lock_response.status_code in (200, 204):
                        updated_count += 1
                        if needs_tag_purge:
                            print(f"Success (Purged & Locked): {item_name}")
                        else:
                            print(f"Success (Locked Only): {item_name}")
                    else:
                        print(f"Failed to apply lock to {item_name}. Status: {lock_response.status_code}")
                        
            else:
                print(f"Failed to GET record for {item_name}. Status: {full_item_response.status_code}")
                
    print(f"\nOperation complete! Successfully processed {updated_count} media items.")

if __name__ == "__main__":
    clean_and_lock_tags()
