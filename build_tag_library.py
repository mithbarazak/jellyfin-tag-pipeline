import os
import json
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
SERVER_URL = os.getenv("JELLYFIN_URL")
API_KEY = os.getenv("JELLYFIN_API_KEY")

def get_admin_user(headers):
    """Fetches the Administrator User ID."""
    response = requests.get(f"{SERVER_URL}/Users", headers=headers)
    if response.status_code == 200:
        for user in response.json():
            if user.get("Policy", {}).get("IsAdministrator"):
                return user.get("Id")
    return None

def build_library():
    print("Connecting to Jellyfin to build the reference library...")
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
        "Fields": "Tags"
    }
    
    response = requests.get(f"{SERVER_URL}/Items", headers=headers, params=params)
    if response.status_code != 200:
        print(f"Error fetching data: {response.status_code}")
        return

    items = response.json().get("Items", [])
    unique_tags = set()

    for item in items:
        tags = item.get("Tags", [])
        unique_tags.update(tags)

    sorted_tags = sorted(list(unique_tags))
    
    output_file = "tag_library.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(sorted_tags, f, indent=4)

    print(f"Success! Built reference library with {len(sorted_tags)} clean tags.")
    print(f"Saved to {output_file}.")

if __name__ == "__main__":
    build_library()
