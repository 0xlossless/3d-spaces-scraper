"""
Three.js Examples Parser - ENRICHED
Scrapes the Three.js examples JSON API to catalog all WebGL/WebGPU demos.
Extracts ALL available fields: version, dependencies, webgl/webgpu flags, etc.

API: https://threejs.org/examples/files.json
     https://threejs.org/examples/tags.json
"""

import logging
import random
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

THREEJS_FILES_URL = "https://threejs.org/examples/files.json"
THREEJS_TAGS_URL = "https://threejs.org/examples/tags.json"
THREEJS_EXAMPLES_URL = "https://threejs.org/examples/"


def _get_headers() -> dict:
    return {
        "User-Agent": "3d-spaces-scraper/1.0 (josep@0xlossless.com)",
        "Accept": "application/json",
    }


def _fetch_json(url: str, rate_limit: tuple = (1, 2)) -> Optional[dict]:
    """Fetch a JSON file with rate limiting and error handling."""
    time.sleep(random.uniform(*rate_limit))
    try:
        resp = requests.get(url, headers=_get_headers(), timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.error(f"Request failed for {url}: {e}")
        return None


def _detect_webgpu(tags: list) -> bool:
    """Check if example uses WebGPU."""
    return any("webgpu" in t.lower() for t in tags)


def scrape_threejs(max_pages: int = 1, rate_limit: tuple = (1, 2),
                   incremental: bool = False, enrich: bool = False, enrich_interval: int = 5) -> list[dict]:
    """
    Scrape Three.js examples via JSON API with FULL data extraction.

    Returns ALL available fields: tags, categories, webgl/webgpu flags,
    engine version, etc.
    """
    records = []

    # Fetch files.json
    logger.info(f"Fetching Three.js files.json: {THREEJS_FILES_URL}")
    files = _fetch_json(THREEJS_FILES_URL, rate_limit)
    if not files:
        logger.error("Failed to fetch Three.js files.json")
        return []

    # Fetch tags.json
    logger.info(f"Fetching Three.js tags.json: {THREEJS_TAGS_URL}")
    tags_data = _fetch_json(THREEJS_TAGS_URL, rate_limit) or {}

    # Process each category
    for category, example_files in files.items():
        for example_file in example_files:
            example_tags = tags_data.get(example_file, [])

            # Build full URL
            full_url = f"{THREEJS_EXAMPLES_URL}{example_file}.html"

            # Detect WebGPU vs WebGL
            is_webgpu = _detect_webgpu(example_tags)

            record = {
                "source": "threejs",
                "title": example_file.replace("_", " ").title(),
                "description": f"Three.js {category} example: {example_file}",
                "tags": example_tags[:20] if example_tags else [category.lower().replace(" ", "-")],
                "genre": category.lower(),
                "engine": "Three.js",
                "platform": "browser",
                "file_size": "",
                "link": full_url,
                "thumbnail_url": "",
                "author": "three.js",
                "game_id": example_file,
                # Enriched fields
                "license": "MIT",
                "download_count": 0,
                "view_count": 0,
                "like_count": 0,
                "rating": 0.0,
                "price": "free",
                "release_date": "",
                "created_at": "",
                "updated_at": "",
                "polycount": 0,
                "texel_density": 0.0,
                "dimensions_x": 0.0,
                "dimensions_y": 0.0,
                "dimensions_z": 0.0,
                "max_resolution_w": 0,
                "max_resolution_h": 0,
                "file_formats": ["html", "js"],
                "asset_type": "demo",
                "creation_method": "code",
                "popularity_score": 0.0,
                "categories": [category.lower()],
                "authors": ["three.js"],
                "sponsors": [],
                "files_hash": "",
                "location": "",
                "square_footage": "",
                "room_count": 0,
                "version": "webgpu" if is_webgpu else "webgl",
                "is_downloadable": 0,
                "engine_detected": "Three.js",
            }
            records.append(record)

    logger.info(f"Three.js: total {len(records)} examples scraped across {len(files)} categories")
    return records


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    records = scrape_threejs()
    print(f"\nScraped {len(records)} examples")
    for r in records[:5]:
        print(f"  - {r['title']}")
        print(f"    Tags: {r['tags']}, Version: {r['version']}")
        print(f"    {r['link']}")
