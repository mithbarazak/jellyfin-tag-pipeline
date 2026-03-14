# Jellyfin Metadata Ingestion Pipeline

A Python-based automation suite designed to clean, normalize, and enrich Jellyfin media metadata tags using local dictionaries and the Google Gemini API. 

This project was built to prepare a Jellyfin media library for a custom machine-learning recommendation engine by ensuring all media items have a robust, standardized set of descriptive tags.

⚠️ **Disclaimer:** This project utilizes the Google Gemini API. The author of this repository is not affiliated with Google. By using this script, you are responsible for securing your own API key, managing your own API quota, and ensuring your usage complies with [Google's API Terms of Service](https://developers.google.com/terms). This script is designed to operate within the limits of the Gemini free tier.

## Features

* **Library Initialization (`build_tag_library.py`):** Scans your current Jellyfin database to build a foundational, approved JSON tag vocabulary.
* **Mapping Generation (`generate_mapping.py`):** Creates a template dictionary for mapping old, unwanted, or duplicate tags to their standardized replacements.
* **Noisy Tag Purge (`ingestion_pipeline.py`):** Automatically removes obscure or hyper-specific tags that appear on fewer than 5 media items.
* **Tag Normalization (`ingestion_pipeline.py`):** Standardizes existing tags by running them through your localized mapping dictionary.
* **AI Tag Enrichment (`ingestion_pipeline.py`):** Queries the Gemini API to analyze media summaries and apply 12-15 highly accurate tags from your predefined vocabulary to any sparse media items.
* **Backlog Processing (`export_for_notebooklm.py`):** Generates a CSV export of sparse media items, allowing for bulk manual processing via Google's NotebookLM to bypass standard API rate limits.
* **Database Commit (`commit_proposed_tags.py`):** Pushes reviewed and approved tags back to the Jellyfin server and archives the working data.

## Prerequisites

* Python 3.12.3+
* A running Jellyfin Server
* A Google Gemini API Key

## Installation

1. Clone this repository to your local machine or server:
   ```bash
   git clone [https://github.com/mithbarazak/jellyfin-tag-pipeline.git](https://github.com/mithbarazak/jellyfin-tag-pipeline.git)
   cd jellyfin-tag-pipeline

2. Create and activate a virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate

```


3. Install the required dependencies:
```bash
pip install -r requirements.txt

```


4. Create a `.env` file in the root directory and add your credentials:
```env
JELLYFIN_URL="http://your-jellyfin-server-url:8096"
JELLYFIN_API_KEY="your_jellyfin_api_key"
GEMINI_API_KEY="your_gemini_api_key"

```



## Pre-Configuration

Before running the automated pipeline, you must build your local tag dictionaries:

1. **Build the Tag Library:** Run `python3 build_tag_library.py`. This will scan your server and create `tag_library.json`, which acts as the strict vocabulary the AI is allowed to pull from. Edit this JSON file manually to remove any tags you do not want the AI to use.
2. **Build the Tag Mapping:** Run `python3 generate_mapping.py`. This creates `tag_mapping.json`. Open this file and define which tags should be automatically converted into other tags (e.g., mapping "sci-fi" to "science fiction").

## Usage

**Standard Pipeline (Daily Automation):**
Run the main ingestion pipeline to clean tags, map duplicates, and generate a batch of AI suggestions in `proposed_tags.csv`. Because of API limits, this is best set up as a daily cron job.

```bash
python3 ingestion_pipeline.py

```

**Committing Tags:**
Once you have reviewed the generated `proposed_tags.csv`, commit the changes to Jellyfin. This updates the database and archives the CSV.

```bash
python3 commit_proposed_tags.py

```

## License

This project is licensed under the GNU Affero General Public License v3.0 (AGPL-3.0) - see the LICENSE file for details.

```
