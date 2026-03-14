import requests

# --- Configuration ---
SERVER_URL = "http://192.168.0.101:8096" # Replace with your actual server URL
API_KEY = "e2f820c801a24955940d30b2d3fe67ac"            # Use your Jellyfin API key

def get_admin_user(headers):
    response = requests.get(f"{SERVER_URL}/Users", headers=headers)
    if response.status_code == 200:
        for user in response.json():
            if user.get("Policy", {}).get("IsAdministrator"):
                return user.get("Id")
    return None

def seek_and_destroy():
    target_tag = input("\nEnter the EXACT name of the tag you want to destroy: ")
    
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
    
    print("Scanning library for targets...")
    response = requests.get(f"{SERVER_URL}/Items", headers=headers, params=params)
    
    if response.status_code != 200:
        print(f"Error fetching data: {response.status_code}")
        return
        
    items = response.json().get("Items", [])
    
    # Find items that contain the target tag
    affected_items = [
        item for item in items 
        if target_tag in item.get("Tags", [])
    ]
    
    if not affected_items:
        print(f"\nTarget acquired: 0. The tag '{target_tag}' was not found on any media items.")
        return
        
    # Warning and Confirmation
    print(f"\n!!! WARNING: THIS ACTION CANNOT BE UNDONE !!!")
    print(f"You are about to permanently purge the tag '{target_tag}'.")
    print(f"This will alter {len(affected_items)} media items.")
    
    confirmation = input("\nType 'yes' to confirm the purge: ")
    
    if confirmation != "yes":
        print("Confirmation failed. Aborting sequence. No changes have been made.")
        return
        
    print("\nExecuting purge sequence...")
    
    updated_count = 0
    keys_to_remove = [
        "UserData", "ImageTags", "BackdropImageTags", "Chapters", 
        "MediaSources", "MediaStreams", "ImageBlurHashes", "Trickplay",
        "PrimaryImageAspectRatio", "OriginalPrimaryImageAspectRatio",
        "ServerId", "Etag", "PlayAccess", "ThemeSongIds", "ThemeVideoIds"
    ]
    
    for item in affected_items:
        item_id = item.get("Id")
        item_name = item.get("Name", "Unknown")
        current_tags = item.get("Tags", [])
        
        # Remove the target tag
        new_tags = [t for t in current_tags if t != target_tag]
        
        full_item_response = requests.get(f"{SERVER_URL}/Users/{admin_id}/Items/{item_id}", headers=headers)
        
        if full_item_response.status_code != 200:
            full_item_response = requests.get(f"{SERVER_URL}/Items/{item_id}", headers=headers, params={"userId": admin_id})
            
        if full_item_response.status_code == 200:
            full_item = full_item_response.json()
            
            for key in keys_to_remove:
                full_item.pop(key, None)
                
            # PHASE 1: UNLOCK AND PURGE
            full_item["Tags"] = new_tags
            full_item["LockedFields"] = [f for f in full_item.get("LockedFields", []) if f != "Tags"]
            
            purge_response = requests.post(f"{SERVER_URL}/Items/{item_id}", headers=headers, json=full_item)
            if purge_response.status_code not in (200, 204):
                print(f"Failed to purge {item_name}. Status: {purge_response.status_code}")
                continue
                
            # PHASE 2: RE-LOCK
            locked_fields = full_item.get("LockedFields", [])
            if "Tags" not in locked_fields:
                locked_fields.append("Tags")
                full_item["LockedFields"] = locked_fields
                
                lock_response = requests.post(f"{SERVER_URL}/Items/{item_id}", headers=headers, json=full_item)
                if lock_response.status_code in (200, 204):
                    updated_count += 1
                    print(f"Success: Removed '{target_tag}' from {item_name}")
                else:
                    print(f"Failed to apply lock to {item_name}.")
        else:
            print(f"Failed to GET record for {item_name}.")
            
    print(f"\nOperation complete! Successfully purged '{target_tag}' from {updated_count} media items.")

if __name__ == "__main__":
    seek_and_destroy()
