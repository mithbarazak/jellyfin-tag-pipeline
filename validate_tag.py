import json
import difflib

def load_library():
    try:
        with open("tag_library.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print("Error: tag_library.json not found.")
        return []

def validate_new_tag():
    library = load_library()
    if not library:
        return

    print(f"Loaded reference library ({len(library)} tags).")
    
    while True:
        new_tag = input("\nEnter a new tag to validate (or type 'quit' to exit): ").strip().lower()
        
        if new_tag == 'quit':
            break
            
        if not new_tag:
            continue

        # 1. Exact Match Check
        if new_tag in library:
            print(f"❌ REJECTED: '{new_tag}' already exists exactly in the library.")
            continue

        # 2. Fuzzy Match Check (Threshold 0.8 catches typos, plurals, and missing hyphens)
        close_matches = difflib.get_close_matches(new_tag, library, n=3, cutoff=0.8)
        
        if close_matches:
            print(f"⚠️ WARNING: '{new_tag}' is very similar to existing tags:")
            for match in close_matches:
                print(f"   - {match}")
            print("Consider using an existing tag instead.")
        else:
            print(f"✅ PASSED: '{new_tag}' appears to be a unique string.")

if __name__ == "__main__":
    validate_new_tag()
