# 🗂️ 3D Spaces Dataset Scraper

Collects metadata about interactive 3D spaces from multiple sources into a structured SQLite database.

## Target Sources

| Source | Status | Method | Records |
|---|---|---|---|
| itch.io | ✅ Built | requests + BeautifulSoup | ~360 |
| Sketchfab | ✅ Built | REST API | ~240 |
| Matterport | ✅ Built | Playwright (JS rendering) | ~100 |
| Three.js Examples | ✅ Built | JSON API | ~577 |
| OpenGameArt.org | ✅ Built | requests + BeautifulSoup | ~180 |

**Total: ~1,450 records across 5 sources**

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers (for Matterport)
playwright install chromium

# Run the scraper
python -m src.scraper

# Export data
python -m src.utils.export csv
python -m src.utils.export json
python -m src.utils.export stats
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
  "scraped_at": "2026-04-23T20:00:00+00:00",
  "author": "creator_name",
  "game_id": "source_specific_id"
}
```

## Architecture

```
config.yaml                    ← Source config, rate limits, UA rotation
requirements.txt               ← Python dependencies
src/scraper.py                 ← Main orchestrator (auto-discovers parsers from config)
src/parsers/                   ← Per-source parser modules
  ├── itch.py                  ← itch.io 3D games
  ├── sketchfab.py             ← Sketchfab 3D models (API)
  ├── matterport.py            ← Matterport gallery (Playwright)
  ├── threejs.py               ← Three.js examples (JSON API)
  └── opengameart.py           ← OpenGameArt 3D models
src/storage/database.py        ← SQLite storage with deduplication
src/utils/export.py            ← CSV/JSON export + stats
data/3d_spaces.db              ← Output database
data/export.csv                ← CSV export
data/export.json               ← JSON export
.github/workflows/scrape.yml   ← GitHub Actions daily automation
```

## Configuration

Edit `config.yaml` to:
- Enable/disable sources
- Adjust rate limits
- Change pagination limits
- Modify user agents

## Adding a New Source

1. Create `src/parsers/newsource.py` with a `scrape_newsource(max_pages, rate_limit)` function
2. Add config entry in `config.yaml` under `sources`
3. The scraper auto-discovers parsers from config — no code changes needed

## GitHub Actions

Push to a repo with the `.github/workflows/scrape.yml` file to enable daily automated scraping at 3:00 AM UTC.

## Output Formats

- **SQLite**: `data/3d_spaces.db` — primary storage with deduplication
- **CSV**: `data/export.csv` — spreadsheet-friendly format
- **JSON**: `data/export.json` — structured data for APIs