"""
Poly Haven 3D Assets Parser
Scrapes Poly Haven's API for 3D models, HDRIs, and textures.

API: https://api.polyhaven.com/
"""

import logging
import random
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

POLYHAVEN_API = "https://api.polyhaven.com"


def _get_headers() -> dict:
    return {
        "User-Agent": "3d-spaces-scraper/1.0 (josep@0xlossless.com)",
        "Accept": "application/json",
    }


def _fetch_json(url: str, rate_limit: tuple = (1, 2)) -> Optional[dict]:
    """Fetch a JSON file from Poly Haven API."""
    time.sleep(random.uniform(*rate_limit))
    try:
        resp = requests.get(url, headers=_get_headers(), timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.error(f"Request failed for {url}: {e}")
        return None


def scrape_polyhaven(max_pages: int = 10, rate_limit: tuple = (1, 2),
                     incremental: bool = False, enrich: bool = False, enrich_interval: int = 5) -> list[dict]:
    """
    Scrape Poly Haven for 3D assets.

    Args:
        max_pages: Maximum number of pages (limit=100 per page).
        rate_limit: (min_seconds, max_seconds) between requests.
        incremental: If True, skip pages already scraped (best-effort).
        enrich: If True, fetch individual asset details.
        enrich_interval: Enrich every Nth asset (default: 5).

    Returns:
        List of record dicts matching the data schema.
    """
    all_records = []
    categories = ["models", "hdris", "textures"]

    for category in categories:
        url = f"{POLYHAVEN_API}/assets?type={category}"
        logger.info(f"Fetching Poly Haven {category}: {url}")

        data = _fetch_json(url, rate_limit)
        if not data or not isinstance(data, dict):
            logger.info(f"No {category} assets found")
            continue

        # Poly Haven returns all assets in a single dict: {asset_id: asset_data}
        for asset_id, asset in data.items():
            title = asset.get("name", asset_id)
            if not asset_id:
                continue

            tags = asset.get("tags", [])
            thumbnail_url = asset.get("thumbnail_url", "")

            # Build link
            if category == "models":
                link = f"https://polyhaven.com/models/{asset_id}"
            elif category == "hdris":
                link = f"https://polyhaven.com/hdris/{asset_id}"
            else:
                link = f"https://polyhaven.com/textures/{asset_id}"

            record = {
                "source": "polyhaven",
                "title": title,
                "description": f"Poly Haven {category} asset: {title}",
                "tags": tags[:10],
                "genre": category,
                "engine": "",
                "platform": "multiplatform",
                "file_size": "",
                "link": link,
                "thumbnail_url": thumbnail_url,
                "author": "Poly Haven",
                "game_id": asset_id,
            }
            all_records.append(record)

        logger.info(f"  {category}: extracted {len(data)} records")

    logger.info(f"Poly Haven: total {len(all_records)} records scraped")
    return all_records


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    records = scrape_polyhaven(max_pages=3)
    print(f"\nScraped {len(records)} records")
    for r in records[:5]:
        print(f"  - {r['title']} ({r['genre']})")
        print(f"    {r['link']}")
