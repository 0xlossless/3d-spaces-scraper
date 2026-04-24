"""
Three.js Examples Parser
Scrapes the Three.js examples JSON API to catalog all WebGL/WebGPU demos.

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
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
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


def scrape_threejs(max_pages: int = 1, rate_limit: tuple = (1, 2)) -> list[dict]:
    """
    Scrape Three.js examples via JSON API.

    Args:
        max_pages: Not used (single API call), kept for API compatibility.
        rate_limit: (min_seconds, max_seconds) between requests.

    Returns:
        List of record dicts matching the data schema.
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
    total_examples = 0
    for category, example_files in files.items():
        for example_file in example_files:
            # Get tags for this example
            example_tags = tags_data.get(example_file, [])

            # Build full URL
            full_url = f"{THREEJS_EXAMPLES_URL}{example_file}.html"

            # Create record
            record = {
                "source": "threejs",
                "title": example_file.replace("_", " ").title(),
                "description": f"Three.js {category} example: {example_file}",
                "tags": example_tags[:10] if example_tags else [category.lower().replace(" ", "-")],
                "genre": category.lower(),
                "engine": "Three.js",
                "platform": "browser",
                "file_size": "",
                "link": full_url,
                "thumbnail_url": "",
                "author": "three.js",
                "game_id": example_file,
            }
            records.append(record)
            total_examples += 1

    logger.info(f"Three.js: total {len(records)} examples scraped across {len(files)} categories")
    return records


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    records = scrape_threejs()
    print(f"\nScraped {len(records)} examples")
    for r in records[:5]:
        print(f"  - {r['title']}")
        print(f"    Tags: {r['tags']}")
        print(f"    {r['link']}")
