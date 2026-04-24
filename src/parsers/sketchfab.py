"""
Sketchfab 3D Models Parser
Uses the public Sketchfab REST API v3 — no auth needed for public models.

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
        "User-Agent": "3d-spaces-scraper/1.0",
        "Accept": "application/json",
    }


def _fetch(url: str, rate_limit: tuple = (3, 5), max_retries: int = 3) -> Optional[dict]:
    """Fetch a JSON page from the Sketchfab API with retry/backoff."""
    time.sleep(random.uniform(*rate_limit))

    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=_get_headers(), timeout=30)

            if resp.status_code == 429:
                # Rate limited — wait and retry
                retry_after = int(resp.headers.get("Retry-After", 10))
                wait = retry_after + random.uniform(2, 5)
                logger.warning(f"Rate limited (429), waiting {wait:.1f}s...")
                time.sleep(wait)
                continue

            resp.raise_for_status()
            return resp.json()

        except requests.RequestException as e:
            logger.error(f"Request attempt {attempt + 1} failed for {url}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)

    return None


def _enrich_model(uid: str, rate_limit: tuple = (0.5, 1)) -> Optional[dict]:
    """Fetch detailed model info from the API."""
    url = f"https://api.sketchfab.com/v3/models/{uid}"
    return _fetch(url, rate_limit, max_retries=2)


def _parse_model(model: dict) -> Optional[dict]:
    """Convert a Sketchfab model object to our data schema."""
    try:
        uid = model.get("uid", "")
        name = model.get("name", "")
        if not uid or not name:
            return None

        tags = model.get("tags", [])
        categories = model.get("categories", [])

        # Thumbnail — pick best quality
        thumbnails = model.get("thumbnails", {}).get("images", [])
        thumbnail_url = ""
        if thumbnails:
            best = max(thumbnails, key=lambda t: t.get("width", 0))
            thumbnail_url = best.get("url", "")

        user = model.get("user", {})
        author = user.get("username", "")

        viewer_url = model.get("viewerUrl", "")
        if not viewer_url:
            viewer_url = f"{SKETCHFAB_BASE}/3d-models/none-{uid}"

        description = model.get("description", "") or ""
        if description:
            description = description[:500]

        engine = model.get("engine", "") or ""

        return {
            "source": "sketchfab",
            "title": name,
            "description": description,
            "tags": tags[:10],
            "genre": categories[0] if categories else "",
            "engine": engine,
            "platform": "browser",
            "file_size": "",
            "link": viewer_url,
            "thumbnail_url": thumbnail_url,
            "author": author,
            "game_id": uid,
        }

    except Exception as e:
        logger.debug(f"Failed to parse model: {e}")
        return None


def scrape_sketchfab(max_pages: int = 10, rate_limit: tuple = (2, 4)) -> list[dict]:
    """
    Scrape Sketchfab's public 3D models via REST API.

    Uses cursor-based pagination with aggressive rate limiting.

    Args:
        max_pages: Maximum number of pages to scrape.
        rate_limit: (min_seconds, max_seconds) between list requests.

    Returns:
        List of record dicts matching the data schema.
    """
    all_records = []
    page = 1

    url = SKETCHFAB_API
    params = {
        "sort": "views",
        "license": "CC Attribution",
        "per_page": 20,
    }

    while page <= max_pages:
        logger.info(f"Fetching Sketchfab page {page}")

        if page == 1:
            full_url = url
            for k, v in params.items():
                full_url += f"&{k}={v}" if "?" in full_url else f"?{k}={v}"
        else:
            full_url = url

        data = _fetch(full_url, rate_limit, max_retries=3)
        if not data:
            logger.warning("Failed to fetch page — stopping pagination")
            break

        results = data.get("results", [])
        if not results:
            logger.info("No more models — pagination complete")
            break

        page_records = []
        for i, model in enumerate(results):
            uid = model.get("uid", "")
            if not uid:
                continue

            # Enrich every 3rd model for richer metadata
            if i % 3 == 0:
                detail = _enrich_model(uid, rate_limit=(0.5, 1))
                if detail:
                    merged = {**model, **detail}
                else:
                    merged = model
            else:
                merged = model

            rec = _parse_model(merged)
            if rec:
                page_records.append(rec)

        logger.info(f"  Page {page}: extracted {len(page_records)} records")
        all_records.extend(page_records)

        next_url = data.get("next")
        if not next_url:
            logger.info("No next page — pagination complete")
            break

        url = next_url
        page += 1

    logger.info(f"Sketchfab: total {len(all_records)} records scraped")
    return all_records


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    records = scrape_sketchfab(max_pages=3)
    print(f"\nScraped {len(records)} records")
    for r in records[:3]:
        print(f"  - {r['title']} by {r['author']}")
        print(f"    Tags: {r['tags']}")
        print(f"    {r['link']}")
