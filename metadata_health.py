import requests
from collections import Counter

# --- Configuration ---
SERVER_URL = "http://192.168.0.101:8096" # Replace with your actual server URL
API_KEY = "e2f820c801a24955940d30b2d3fe67ac"            # Use the same API key as your recommender script

# --- Thresholds ---
MIN_TAGS_PER_MEDIA = 12
MIN_MEDIA_PER_TAG = 5

def analyze_metadata():
    headers = {
        "Authorization": f"MediaBrowser Token={API_KEY}",
        "Content-Type": "application/json"
    }
    
    # Query movies and TV series across the server
    params = {
        "IncludeItemTypes": "Movie,Series",
        "Recursive": "true",
        "Fields": "Tags"
    }
    
    print("Fetching library data from Jellyfin...")
    response = requests.get(f"{SERVER_URL}/Items", headers=headers, params=params)
    
    if response.status_code != 200:
        print(f"Error fetching data. HTTP Status: {response.status_code}")
        return
        
    items = response.json().get("Items", [])
    
    sparse_media = []
    tag_counts = Counter()
    
    for item in items:
        name = item.get("Name", "Unknown")
        item_type = item.get("Type", "Unknown")
        all_tags = item.get("Tags", [])
        
        # Isolate standard tags by ignoring your custom structural prefixes
        standard_tags = [
            t for t in all_tags 
            if not t.lower().startswith(("franchise:", "universe:", "dependson:"))
        ]
        
        # 1. Check for sparse metadata
        if len(standard_tags) < MIN_TAGS_PER_MEDIA:
            sparse_media.append({
                "Name": name,
                "Type": item_type,
                "TagCount": len(standard_tags)
            })
            
        # 2. Add to global frequency counter
        tag_counts.update(standard_tags)
        
    # Find tags that don't meet the minimum occurrence threshold
    rare_tags = {tag: count for tag, count in tag_counts.items() if count < MIN_MEDIA_PER_TAG}
    
    # Generate the text report
    report_path = "metadata_health_report.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("=== JELLYFIN METADATA HEALTH REPORT ===\n")
        f.write(f"Total Items Analyzed: {len(items)}\n\n")
        
        f.write(f"--- SPARSE MEDIA (Fewer than {MIN_TAGS_PER_MEDIA} standard tags) ---\n")
        # Sort by those needing the most help first
        sparse_media.sort(key=lambda x: x["TagCount"])
        for m in sparse_media:
            f.write(f"[{m['Type']}] {m['Name']} - {m['TagCount']} tags\n")
            
        f.write(f"\n--- NOISY TAGS (Used in fewer than {MIN_MEDIA_PER_TAG} items) ---\n")
        # Sort by frequency (lowest first), then alphabetically
        sorted_rare_tags = sorted(rare_tags.items(), key=lambda x: (x[1], x[0]))
        for tag, count in sorted_rare_tags:
            f.write(f"[{count}] {tag}\n")
            
    print(f"\nAnalysis complete!")
    print(f"Found {len(sparse_media)} items needing more tags.")
    print(f"Found {len(rare_tags)} noisy tags to clean up.")
    print(f"Full lists saved to: {report_path}")

if __name__ == "__main__":
    analyze_metadata()
