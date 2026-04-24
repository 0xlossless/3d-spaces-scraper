# 🗂️ 3D Spaces Dataset Scraper

Collects metadata about interactive 3D spaces from multiple sources into a structured SQLite database.

## Target Sources

| Source | Status | Method | Records |
|---|---|---|---|
| itch.io | ✅ Built + Enriched | requests + BeautifulSoup | ~360 |
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
python -m src.cli run

# Run with specific source
python -m src.cli run --source "itch.io"

# Export data
python -m src.cli export --format csv
python -m src.cli export --format json

# View statistics
python -m src.cli stats

# Clean cache and database
python -m src.cli clean
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
config.yaml                    ← Source config, per-source rate limits, enrichment settings
requirements.txt               ← Python dependencies
src/cli.py                     ← CLI entry point (run, export, stats, clean)
src/http_cache.py              ← HTTP caching layer (requests-cache)
src/scraper.py                 ← Main orchestrator (auto-discovers parsers from config)
src/parsers/                   ← Per-source parser modules
  ├── itch.py                  ← itch.io 3D games (with enrichment)
  ├── sketchfab.py             ← Sketchfab 3D models (API)
  ├── matterport.py            ← Matterport gallery (Playwright)
  ├── threejs.py               ← Three.js examples (JSON API)
  └── opengameart.py           ← OpenGameArt 3D models
src/storage/database.py        ← SQLite storage with deduplication + scrape tracking
src/utils/export.py            ← CSV/JSON export + stats
data/3d_spaces.db              ← Output database
data/export.csv                ← CSV export
data/export.json               ← JSON export
.github/workflows/scrape.yml   ← GitHub Actions daily automation
```

## Configuration

Edit `config.yaml` to:
- Enable/disable sources
- Set per-source rate limits (override global defaults)
- Configure enrichment (fetch individual pages for deeper metadata)
- Adjust pagination limits
- Set HTTP cache TTL

### Per-Source Settings

```yaml
sources:
  - name: itch.io
    enabled: true
    rate_limit:
      min: 1
      max: 3
    max_pages: 10
    enrich:
      enabled: true      # Fetch individual game pages
      interval: 5        # Enrich every 5th game
```

## CLI Commands

### Run
```bash
python -m src.cli run                          # Run all sources
python -m src.cli run --source "itch.io"       # Run specific source
python -m src.cli run --incremental            # Only fetch new content
```

### Export
```bash
python -m src.cli export --format csv          # Export to CSV
python -m src.cli export --format json         # Export to JSON
python -m src.cli export --format csv --output data/custom.csv
```

### Stats
```bash
python -m src.cli stats                        # Print database statistics
```

### Clean
```bash
python -m src.cli clean                        # Clear cache and database
python -m src.cli clean --cache                # Only clear HTTP cache
python -m src.cli clean --db                   # Only delete database
```

## Adding a New Source

1. Create `src/parsers/newsource.py` with a `scrape_newsource(max_pages, rate_limit, incremental, enrich, enrich_interval)` function
2. Add config entry in `config.yaml` under `sources`
3. The scraper auto-discovers parsers from config — no code changes needed

## GitHub Actions

Push to a repo with the `.github/workflows/scrape.yml` file to enable daily automated scraping at 3:00 AM UTC.

## Output Formats

- **SQLite**: `data/3d_spaces.db` — primary storage with deduplication
- **CSV**: `data/export.csv` — spreadsheet-friendly format
- **JSON**: `data/export.json` — structured data for APIs

## Optimizations

- **HTTP Caching**: `requests-cache` avoids re-fetching unchanged pages (configurable TTL)
- **Per-Source Rate Limits**: Each source can have its own rate limiting settings
- **Data Enrichment**: Fetch individual pages for deeper metadata (tags, engine detection)
- **Incremental Scraping**: Track last scrape time per source
- **CLI Interface**: Easy-to-use commands for run, export, stats, and clean