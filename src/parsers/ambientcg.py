"""
AmbientCG 3D Assets Parser
Scrapes AmbientCG's API for materials, HDRIs, and models.

API: https://ambientcg.com/api/v1/
"""

import logging
import random
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

AMBIENTCG_API = "https://ambientcg.com/api/v2"


def _get_headers() -> dict:
    return {
        "User-Agent": "3d-spaces-scraper/1.0",
        "Accept": "application/json",
    }


def _fetch_json(url: str, rate_limit: tuple = (1, 2)) -> Optional[dict]:
    """Fetch a JSON file from AmbientCG API."""
    time.sleep(random.uniform(*rate_limit))
    try:
        resp = requests.get(url, headers=_get_headers(), timeout=30)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as e:
        logger.error(f"Request failed for {url}: {e}")
        return None


def scrape_ambientcg(max_pages: int = 10, rate_limit: tuple = (1, 2),
                     incremental: bool = False, enrich: bool = False, enrich_interval: int = 5) -> list[dict]:
    """
    Scrape AmbientCG for 3D assets.

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

    for page in range(max_pages):
        offset = page * 100
        url = f"{AMBIENTCG_API}/full_json?limit=100&offset={offset}"
        logger.info(f"Fetching AmbientCG page {page + 1}: {url}")

        data = _fetch_json(url, rate_limit)
        if not data or "foundAssets" not in data:
            logger.info("No more assets found")
            break

        assets = data["foundAssets"]
        if not assets:
            break

        for asset in assets:
            asset_id = asset.get("assetId", "")
            title = asset.get("assetId", asset_id)
            if not asset_id:
                continue

            tags = asset.get("tags", [])
            preview_data = asset.get("previewData", {})
            thumbnail_url = preview_data.get("preview", "") if isinstance(preview_data, dict) else ""

            # Build link
            asset_type = asset.get("dataType", "materials")
            link = f"https://ambientcg.com/view/{asset_id}"

            record = {
                "source": "ambientcg",
                "title": title,
                "description": f"AmbientCG {asset_type} asset: {title}",
                "tags": tags[:10],
                "genre": asset_type.lower(),
                "engine": "",
                "platform": "multiplatform",
                "file_size": "",
                "link": link,
                "thumbnail_url": thumbnail_url,
                "author": "AmbientCG",
                "game_id": asset_id,
            }
            all_records.append(record)

        logger.info(f"  Page {page + 1}: extracted {len(assets)} records")

    logger.info(f"AmbientCG: total {len(all_records)} records scraped")
    return all_records


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    records = scrape_ambientcg(max_pages=3)
    print(f"\nScraped {len(records)} records")
    for r in records[:5]:
        print(f"  - {r['title']} ({r['genre']})")
        print(f"    {r['link']}")
