"""
AmbientCG 3D Assets Parser - ENRICHED
Scrapes AmbientCG's API for materials, HDRIs, and models.
Extracts ALL available fields: technical data, popularity, creation method, etc.

API: https://ambientcg.com/api/v2/
License: CC0 (Public Domain)
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
        "User-Agent": "3d-spaces-scraper/1.0 (josep@0xlossless.com)",
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


def _parse_technical_data(technical: dict) -> tuple:
    """Extract resolution and formats from technicalData."""
    resolution_w = 0
    resolution_h = 0
    formats = []
    
    if not technical:
        return resolution_w, resolution_h, formats
    
    # Try to extract resolution
    res = technical.get("resolution", "")
    if "8K" in res:
        resolution_w, resolution_h = 8192, 8192
    elif "4K" in res:
        resolution_w, resolution_h = 4096, 4096
    elif "2K" in res:
        resolution_w, resolution_h = 2048, 2048
    elif "1K" in res:
        resolution_w, resolution_h = 1024, 1024
    
    # Extract formats from file list
    file_list = technical.get("fileList", [])
    if file_list:
        for f in file_list:
            ext = f.get("extension", "") or f.get("format", "")
            if ext and ext not in formats:
                formats.append(ext)
    
    return resolution_w, resolution_h, formats


def _build_record(asset: dict) -> dict:
    """Convert an AmbientCG asset to our enriched data schema."""
    asset_id = asset.get("assetId", "")
    if not asset_id:
        return {}
    
    # Basic info
    data_type = asset.get("dataType", "Material")
    creation_method = asset.get("creationMethod", "")
    tags = asset.get("tags", [])
    
    # Dates
    release_date = asset.get("releaseDate", "")
    early_release = asset.get("earlyReleaseDate", "")
    
    # Downloads & popularity
    download_count = asset.get("downloadCount", 0)
    download_month = asset.get("downloadCountMonth", 0)
    download_week = asset.get("downloadCountWeek", 0)
    popularity_score = asset.get("popularityScore", 0.0)
    
    # Technical data
    technical = asset.get("technicalData", {})
    res_w, res_h, formats = _parse_technical_data(technical)
    
    # Preview
    preview_data = asset.get("previewData", {})
    thumbnail_url = preview_data.get("preview", "") if isinstance(preview_data, dict) else ""
    
    # Link
    link = f"https://ambientcg.com/view/{asset_id}"
    
    record = {
        "source": "ambientcg",
        "title": asset_id,
        "description": f"AmbientCG {data_type} asset: {asset_id}",
        "tags": tags[:20],
        "genre": data_type.lower(),
        "engine": "",
        "platform": "multiplatform",
        "file_size": "",
        "link": link,
        "thumbnail_url": thumbnail_url,
        "author": "AmbientCG",
        "game_id": asset_id,
        # Enriched fields
        "license": "CC0",
        "download_count": download_count,
        "view_count": 0,
        "like_count": 0,
        "rating": 0.0,
        "price": "free",
        "release_date": release_date,
        "created_at": early_release or release_date,
        "updated_at": "",
        "polycount": 0,
        "texel_density": 0.0,
        "dimensions_x": 0.0,
        "dimensions_y": 0.0,
        "dimensions_z": 0.0,
        "max_resolution_w": res_w,
        "max_resolution_h": res_h,
        "file_formats": formats,
        "asset_type": data_type.lower(),
        "creation_method": creation_method,
        "popularity_score": popularity_score,
        "categories": [],
        "authors": ["AmbientCG"],
        "sponsors": [],
        "files_hash": "",
        "location": "",
        "square_footage": "",
        "room_count": 0,
        "version": "",
        "is_downloadable": 1,
        "engine_detected": "",
    }
    
    return record


def scrape_ambientcg(max_pages: int = 10, rate_limit: tuple = (1, 2),
                     incremental: bool = False, enrich: bool = False, enrich_interval: int = 5) -> list[dict]:
    """
    Scrape AmbientCG for 3D assets with FULL data extraction.

    Returns ALL available fields: technical data, popularity scores,
    creation methods, download stats, file formats, etc.
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

        page_records = []
        for asset in assets:
            record = _build_record(asset)
            if record:
                page_records.append(record)

        all_records.extend(page_records)
        logger.info(f"  Page {page + 1}: extracted {len(page_records)} records")

    logger.info(f"AmbientCG: total {len(all_records)} records scraped")
    return all_records


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    records = scrape_ambientcg(max_pages=3)
    print(f"\nScraped {len(records)} records")
    for r in records[:3]:
        print(f"  - {r['title']} ({r['asset_type']})")
        print(f"    Downloads: {r['download_count']}, Popularity: {r['popularity_score']}")
        print(f"    Creation: {r['creation_method']}, Formats: {r['file_formats']}")
        print(f"    {r['link']}")
