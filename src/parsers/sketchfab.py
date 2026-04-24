"""
Sketchfab 3D Models Parser - ENRICHED
Uses the public Sketchfab REST API v3 — no auth needed for public models.
Extracts ALL available fields: downloads, likes, views, licenses, dates, etc.

API docs: https://sketchfab.com/developers/api/docs
Endpoint: https://api.sketchfab.com/v3/models
"""

import logging
import random
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

SKETCHFAB_API = "https://api.sketchfab.com/v3/models"
SKETCHFAB_BASE = "https://sketchfab.com"


def _get_headers() -> dict:
    return {
        "User-Agent": "3d-spaces-scraper/1.0 (josep@0xlossless.com)",
        "Accept": "application/json",
    }


def _fetch(url: str, rate_limit: tuple = (5, 8), max_retries: int = 3) -> Optional[dict]:
    """Fetch a JSON page from the Sketchfab API with retry/backoff."""
    time.sleep(random.uniform(*rate_limit))

    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=_get_headers(), timeout=30)

            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", 15))
                wait = retry_after + random.uniform(5, 10)
                logger.warning(f"Rate limited (429), waiting {wait:.1f}s...")
                time.sleep(wait)
                continue

            resp.raise_for_status()
            return resp.json()

        except requests.RequestException as e:
            logger.error(f"Request attempt {attempt + 1} failed for {url}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt + random.uniform(1, 3))

    return None


def _format_size(size_bytes: int) -> str:
    """Convert bytes to human-readable size."""
    if not size_bytes:
        return ""
    if size_bytes > 1_073_741_824:
        return f"{size_bytes / 1_073_741_824:.1f} GB"
    elif size_bytes > 1_048_576:
        return f"{size_bytes / 1_048_576:.1f} MB"
    else:
        return f"{size_bytes / 1024:.1f} KB"


def _detect_engine(tags: list, description: str) -> str:
    """Detect 3D engine from tags and description."""
    engines = {
        "Unity": ["unity", "unity3d"],
        "Unreal Engine": ["unreal", "unreal engine", "ue4", "ue5"],
        "Blender": ["blender"],
        "Godot": ["godot"],
        "Maya": ["maya"],
        "Cinema 4D": ["cinema 4d", "c4d"],
        "3ds Max": ["3ds max", "max"],
        "Substance": ["substance", "substance painter"],
    }
    
    text = " ".join(tags).lower() + " " + description.lower()
    for engine, keywords in engines.items():
        for kw in keywords:
            if kw in text:
                return engine
    return ""


def _parse_model(model: dict) -> Optional[dict]:
    """Convert a Sketchfab model object to our enriched data schema."""
    try:
        uid = model.get("uid", "")
        name = model.get("name", "")
        if not uid or not name:
            return None

        # Tags
        tags_raw = model.get("tags", [])
        tags = []
        for t in tags_raw:
            if isinstance(t, dict):
                tags.append(t.get("name", ""))
            elif isinstance(t, str):
                tags.append(t)
        tags = [t for t in tags if t][:20]

        # Categories
        categories_raw = model.get("categories", [])
        categories = []
        for c in categories_raw:
            if isinstance(c, dict):
                categories.append(c.get("name", ""))
            elif isinstance(c, str):
                categories.append(c)

        # Thumbnail — pick best quality
        thumbnails = model.get("thumbnails", {}).get("images", [])
        thumbnail_url = ""
        if thumbnails:
            best = max(thumbnails, key=lambda t: t.get("width", 0))
            thumbnail_url = best.get("url", "")

        # Author
        user = model.get("user", {})
        author = user.get("displayName") or user.get("username", "")

        # Link
        viewer_url = model.get("viewerUrl", "")
        if not viewer_url:
            viewer_url = f"{SKETCHFAB_BASE}/3d-models/none-{uid}"

        # Description
        description = model.get("description", "") or ""
        if description:
            description = description[:1000]

        # File size from archives
        file_size = ""
        file_formats = []
        archives = model.get("archives", {})
        if archives:
            for fmt, info in archives.items():
                if isinstance(info, dict) and info.get("size"):
                    file_size = _format_size(info["size"])
                    ext = fmt.lower()
                    if ext not in file_formats:
                        file_formats.append(ext)

        # Stats
        view_count = model.get("viewCount", 0) or 0
        download_count = model.get("downloadCount", 0) or 0
        like_count = model.get("likeCount", 0) or 0

        # License
        license_info = model.get("license", {})
        if isinstance(license_info, dict):
            license_label = license_info.get("label", "")
        else:
            license_label = ""

        # Dates
        created_at = model.get("createdAt", "") or ""
        updated_at = model.get("updatedAt", "") or ""

        # Downloadable flag
        is_downloadable = 1 if model.get("downloadable", False) else 0

        # Engine detection
        engine_detected = _detect_engine(tags, description)

        return {
            "source": "sketchfab",
            "title": name,
            "description": description,
            "tags": tags,
            "genre": categories[0] if categories else "",
            "engine": "",
            "platform": "browser",
            "file_size": file_size,
            "link": viewer_url,
            "thumbnail_url": thumbnail_url,
            "author": author,
            "game_id": uid,
            # Enriched fields
            "license": license_label,
            "download_count": download_count,
            "view_count": view_count,
            "like_count": like_count,
            "rating": 0.0,
            "price": "",
            "release_date": created_at,
            "created_at": created_at,
            "updated_at": updated_at,
            "polycount": 0,
            "texel_density": 0.0,
            "dimensions_x": 0.0,
            "dimensions_y": 0.0,
            "dimensions_z": 0.0,
            "max_resolution_w": 0,
            "max_resolution_h": 0,
            "file_formats": file_formats,
            "asset_type": "model",
            "creation_method": "",
            "popularity_score": float(view_count + download_count),
            "categories": categories,
            "authors": [author],
            "sponsors": [],
            "files_hash": "",
            "location": "",
            "square_footage": "",
            "room_count": 0,
            "version": "",
            "is_downloadable": is_downloadable,
            "engine_detected": engine_detected,
        }

    except Exception as e:
        logger.debug(f"Failed to parse model: {e}")
        return None


def scrape_sketchfab(max_pages: int = 10, rate_limit: tuple = (5, 8),
                     incremental: bool = False, enrich: bool = False, enrich_interval: int = 5) -> list[dict]:
    """
    Scrape Sketchfab's public 3D models via REST API with FULL data extraction.

    Returns ALL available fields: downloads, likes, views, licenses,
    dates, file formats, engine detection, etc.
    """
    all_records = []
    page = 1

    url = SKETCHFAB_API
    params = {
        "sort": "views",
        "license": "CC Attribution",
        "per_page": 20,
    }
    query_parts = "&".join(f"{k}={v}" for k, v in params.items())
    current_url = f"{url}?{query_parts}"

    while page <= max_pages:
        logger.info(f"Fetching Sketchfab page {page}")

        data = _fetch(current_url, rate_limit, max_retries=3)
        if not data:
            logger.warning("Failed to fetch page — stopping pagination")
            break

        results = data.get("results", [])
        if not results:
            logger.info("No more models — pagination complete")
            break

        page_records = []
        for model in results:
            rec = _parse_model(model)
            if rec:
                page_records.append(rec)

        logger.info(f"  Page {page}: extracted {len(page_records)} records")
        all_records.extend(page_records)

        next_url = data.get("next")
        if not next_url:
            logger.info("No next page — pagination complete")
            break

        current_url = next_url
        page += 1

    logger.info(f"Sketchfab: total {len(all_records)} records scraped")
    return all_records


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    records = scrape_sketchfab(max_pages=3)
    print(f"\nScraped {len(records)} records")
    for r in records[:3]:
        print(f"  - {r['title']} by {r['author']}")
        print(f"    Views: {r['view_count']}, Downloads: {r['download_count']}, Likes: {r['like_count']}")
        print(f"    License: {r['license']}, Engine: {r['engine_detected']}")
        print(f"    {r['link']}")
