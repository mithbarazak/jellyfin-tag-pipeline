import os
import csv
import requests
from dotenv import load_dotenv

load_dotenv()
SERVER_URL = os.getenv("JELLYFIN_URL")
API_KEY = os.getenv("JELLYFIN_API_KEY")
MIN_TAGS_PER_MEDIA = 12

def export_backlog():
    headers = {
        "Authorization": f"MediaBrowser Token={API_KEY}",
        "Content-Type": "application/json"
    }
    
    print("Fetching library data from Jellyfin...")
    params = {"IncludeItemTypes": "Movie,Series", "Recursive": "true", "Fields": "Tags,Overview,ProductionYear"}
    response = requests.get(f"{SERVER_URL}/Items", headers=headers, params=params)
    
    if response.status_code != 200:
        print("Error fetching data.")
        return
        
    items = response.json().get("Items", [])
    
    # Exclude items already processed in your current proposed_tags.csv
    processed_ids = set()
    if os.path.isfile("proposed_tags.csv"):
        with open("proposed_tags.csv", mode="r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            processed_ids = {row["Item ID"] for row in reader}

    sparse_items = [
        item for item in items 
        if len(item.get("Tags", [])) < MIN_TAGS_PER_MEDIA and item.get("Id") not in processed_ids
    ]
    
    print(f"Found {len(sparse_items)} items to export.")
    
    export_file = "notebooklm_source.csv"
    with open(export_file, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["Row", "Item ID", "Title", "Year", "Current Tags", "Overview"])
        
        for index, item in enumerate(sparse_items, start=1):
            writer.writerow([
                index,
                item.get("Id"),
                item.get("Name", "Unknown Title"),
                item.get("ProductionYear", "Unknown Year"),
                ", ".join(item.get("Tags", [])),
                item.get("Overview", "No overview available.")
            ])

    print(f"Export complete. Upload {export_file} to NotebookLM.")

if __name__ == "__main__":
    export_backlog()
