import os
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
# The genai.Client() automatically securely pulls your GEMINI_API_KEY from .env

def generate_tag_mapping():
    print("Loading tags...")
    with open("current_tags.json", "r", encoding="utf-8") as f:
        all_tags = json.load(f)

    # Token optimization: Filter out tags that are already standardized
    prefixes_to_ignore = ("DependsOn:", "Franchise:", "Universe:", "1", "2")
    tags_to_analyze = [tag for tag in all_tags if not tag.startswith(prefixes_to_ignore)]
    
    print(f"Filtered {len(all_tags)} total tags down to {len(tags_to_analyze)} for AI analysis.")

    # Initialize the new SDK Client
    client = genai.Client()

    prompt = f"""
    You are a data standardization assistant. Review the following list of media tags.
    Identify duplicates, near-misses, synonyms, or non-English tags (e.g., 'xmas' and 'christmas', 'alien' and 'alien life-form').
    Choose the best, most common English tag as the standard.
    
    Return ONLY a valid JSON dictionary where the key is the stale tag and the value is the standardized replacement tag.
    Do not include tags that do not need to be merged.
    
    Tags to analyze:
    {json.dumps(tags_to_analyze)}
    """

    print("Sending to Gemini for analysis (this may take a moment)...")
    
    # Execute the call using the new syntax and active model
    response = client.models.generate_content(
        model='gemini-3-flash-preview',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )

    mapping = json.loads(response.text)
    
    output_file = "tag_mapping.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=4)

    print(f"Success! Identified {len(mapping)} tags to merge.")
    print(f"Mapping saved to {output_file}. Please review it before we apply changes.")

if __name__ == "__main__":
    generate_tag_mapping()
