# 🗂️ 3D Spaces Dataset Scraper

Collects metadata about interactive 3D spaces from multiple sources into a structured SQLite database.

## Target Sources

| Source | Status | Method |
|---|---|---|
| itch.io | ✅ Built | requests + BeautifulSoup |
| Sketchfab | 🔲 Planned | REST API |
| Matterport | 🔲 Planned | Playwright |
| Three.js Examples | 🔲 Planned | requests |
| OpenGameArt.org | 🔲 Planned | requests |

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Run the scraper
python -m src.scraper

# Check the database
sqlite3 data/3d_spaces.db "SELECT COUNT(*) FROM records;"
sqlite3 data/3d_spaces.db "SELECT source, COUNT(*) FROM records GROUP BY source;"
```

## Data Schema

```json
{
  "id": "unique_hash",
  "source": "itch.io",
  "title": "My 3D Space",
  "description": "A walkthrough of...",
  "tags": ["3D", "walkthrough", "WebGL"],
  "genre": "architectural",
  "engine": "Unity",
  "platform": "browser",
  "file_size": "45MB",
  "link": "https://...",
  "thumbnail_url": "https://...",
  "scraped_at": "2026-04-23T20:00:00+00:00"
}
```

## Architecture

```
config.yaml          ← Source config, rate limits, UA rotation
src/scraper.py       ← Main orchestrator
src/parsers/         ← Per-source parser modules
src/storage/database.py  ← SQLite storage with deduplication
data/3d_spaces.db    ← Output database
```

## Adding a New Source

1. Create `src/parsers/newsource.py` with a `scrape_newsource()` function
2. Register it in `src/scraper.py` parser_map
3. Add config entry in `config.yaml`

## GitHub Actions

Push to a repo with the `.github/workflows/scrape.yml` file to enable daily automated scraping.
