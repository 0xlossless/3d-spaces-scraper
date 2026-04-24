"""
Poly Haven 3D Assets Parser - ENRICHED
Scrapes Poly Haven's API for 3D models, HDRIs, and textures.
Extracts ALL available fields: geometry, resolution, downloads, authors, etc.

API: https://api.polyhaven.com/
License: CC0 (Public Domain)
"""

import logging
import random
import time
from datetime import datetime, timezone
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


def _parse_authors(authors_dict: dict) -> list:
    """Convert authors dict {"Name": "Role"} to list."""
    if not authors_dict:
        return []
    return list(authors_dict.keys())


def _build_record(asset_id: str, asset: dict, category: str) -> dict:
    """Convert a Poly Haven asset to our enriched data schema."""
    title = asset.get("name", asset_id)
    description = asset.get("description", "")

    # Categories & tags
    categories = asset.get("categories", [])
    tags = asset.get("tags", [])

    # Authors
    authors_dict = asset.get("authors", {})
    authors = _parse_authors(authors_dict)

    # Thumbnail
    thumbnail_url = asset.get("thumbnail_url", "")

    # Build link
    if category == "models":
        link = f"https://polyhaven.com/models/{asset_id}"
    elif category == "hdris":
        link = f"https://polyhaven.com/hdris/{asset_id}"
    else:
        link = f"https://polyhaven.com/textures/{asset_id}"

    # Date
    date_published = asset.get("date_published", 0)
    if date_published:
        release_date = datetime.fromtimestamp(date_published, tz=timezone.utc).isoformat()
    else:
        release_date = ""

    # Common record
    record = {
        "source": "polyhaven",
        "title": title,
        "description": description[:1000] if description else "",
        "tags": tags[:20],
        "genre": category,
        "engine": "",
        "platform": "multiplatform",
        "file_size": "",
        "link": link,
        "thumbnail_url": thumbnail_url,
        "author": ", ".join(authors) if authors else "Poly Haven",
        "game_id": asset_id,
        # Enriched fields
        "license": "CC0",
        "download_count": asset.get("download_count", 0),
        "view_count": 0,
        "like_count": 0,
        "rating": 0.0,
        "price": "free",
        "release_date": release_date,
        "created_at": release_date,
        "updated_at": "",
        "polycount": asset.get("polycount", 0),
        "texel_density": asset.get("texel_density", 0.0),
        "dimensions_x": asset.get("dimensions", [0, 0, 0])[0] if asset.get("dimensions") and len(asset.get("dimensions", [])) >= 3 else 0.0,
        "dimensions_y": asset.get("dimensions", [0, 0, 0])[1] if asset.get("dimensions") and len(asset.get("dimensions", [])) >= 3 else 0.0,
        "dimensions_z": asset.get("dimensions", [0, 0, 0])[2] if asset.get("dimensions") and len(asset.get("dimensions", [])) >= 3 else 0.0,
        "max_resolution_w": asset.get("max_resolution", [0, 0])[0] if asset.get("max_resolution") else 0,
        "max_resolution_h": asset.get("max_resolution", [0, 0])[1] if asset.get("max_resolution") else 0,
        "file_formats": [],
        "asset_type": category,
        "creation_method": "",
        "popularity_score": float(asset.get("download_count", 0)),
        "categories": categories,
        "authors": authors,
        "sponsors": asset.get("sponsors", []),
        "files_hash": asset.get("files_hash", ""),
        "location": "",
        "square_footage": "",
        "room_count": 0,
        "version": "",
        "is_downloadable": 1,
        "engine_detected": "",
    }

    # HDRIs specific fields
    if category == "hdris":
        record["whitebalance"] = asset.get("whitebalance", 0)
        record["backplates"] = asset.get("backplates", False)
        record["evs_cap"] = asset.get("evs_cap", 0.0)
        coords = asset.get("coords", [])
        if coords and len(coords) >= 2:
            record["location"] = f"{coords[0]:.4f}, {coords[1]:.4f}"

    # Models specific fields
    if category == "models":
        record["lods"] = asset.get("lods", False)

    return record


def scrape_polyhaven(max_pages: int = 10, rate_limit: tuple = (1, 2),
                     incremental: bool = False, enrich: bool = False, enrich_interval: int = 5) -> list[dict]:
    """
    Scrape Poly Haven for 3D assets with FULL data extraction.

    Returns ALL available fields: geometry, resolution, downloads, authors,
    categories, timestamps, hashes, sponsors, GPS coords (HDRIs), etc.
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

        for asset_id, asset in data.items():
            if not asset_id:
                continue
            record = _build_record(asset_id, asset, category)
            all_records.append(record)

        logger.info(f"  {category}: extracted {len(data)} records")

    logger.info(f"Poly Haven: total {len(all_records)} records scraped")
    return all_records


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    records = scrape_polyhaven(max_pages=1)
    print(f"\nScraped {len(records)} records")
    for r in records[:3]:
        print(f"  - {r['title']} ({r['asset_type']})")
        print(f"    Author: {r['author']}, Downloads: {r['download_count']}")
        print(f"    Polycount: {r['polycount']}, Resolution: {r['max_resolution_w']}x{r['max_resolution_h']}")
        print(f"    Categories: {r['categories']}")
        print(f"    {r['link']}")
