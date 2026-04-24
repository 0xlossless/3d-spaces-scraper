"""
OpenGameArt.org 3D Models Parser - ENRICHED
Scrapes 3D model listings from OpenGameArt.org.
Extracts ALL available fields: license, downloads, rating, file formats, etc.

Uses the art search with proper form parameters.
"""

import logging
import random
import re
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

OGA_SEARCH_URL = "https://opengameart.org/art-search"
OGA_BASE = "https://opengameart.org"


def _get_headers() -> dict:
    return {
        "User-Agent": "3d-spaces-scraper/1.0 (josep@0xlossless.com)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://opengameart.org/",
    }


def _fetch_page(url: str, rate_limit: tuple = (2, 4)) -> Optional[str]:
    """Fetch a page with rate limiting and error handling."""
    time.sleep(random.uniform(*rate_limit))
    try:
        resp = requests.get(url, headers=_get_headers(), timeout=30)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as e:
        logger.error(f"Request failed for {url}: {e}")
        return None


def _is_3d_related(title: str, tags: list) -> bool:
    """Check if an art item is 3D-related based on title and tags."""
    title_lower = title.lower()
    tags_lower = [t.lower() for t in tags]
    all_text = title_lower + " " + " ".join(tags_lower)

    _3d_keywords = [
        "3d", "model", "models", "mesh", "polygon", "poly", "lowpoly", "low-poly",
        "obj", "fbx", "gltf", "glb", "blend", "maya", "blender", "c4d",
        "character", "prop", "environment", "terrain", "vehicle", "weapon",
        "animated", "rigged", "skinned", "vertex", "normal map", "bake",
    ]

    return any(kw in all_text for kw in _3d_keywords)


def _extract_license(text: str) -> str:
    """Extract license type from text."""
    if not text:
        return ""
    lower = text.lower()
    if "cc0" in lower:
        return "CC0"
    elif "cc-by" in lower:
        return "CC-BY"
    elif "cc-by-nc" in lower:
        return "CC-BY-NC"
    elif "cc-by-sa" in lower:
        return "CC-BY-SA"
    elif "cc-by-nd" in lower:
        return "CC-BY-ND"
    elif "gpl" in lower:
        return "GPL"
    elif "mit" in lower:
        return "MIT"
    elif "public domain" in lower:
        return "Public Domain"
    return text


def _parse_art_links(soup: BeautifulSoup) -> list[dict]:
    """Extract art items from search results."""
    records = []

    content_links = soup.select('a[href^="/content/"]')

    seen = set()
    for link in content_links:
        href = link.get("href", "")
        if href in seen or href == "/content/faq":
            continue
        seen.add(href)

        title = link.get_text(strip=True)
        if not title or len(title) < 2:
            continue

        full_url = OGA_BASE + href if href.startswith("/") else href

        parent = link.parent
        if not parent:
            continue

        # Thumbnail
        thumb = parent.select_one("img")
        thumbnail_url = ""
        if thumb:
            thumbnail_url = thumb.get("src", "") or thumb.get("data-src", "")

        # Tags
        tags = []
        for tag_link in parent.select('a[href^="/tag/"]'):
            tag_text = tag_link.get_text(strip=True)
            if tag_text:
                tags.append(tag_text)

        # Author
        author = ""
        author_el = parent.select_one('a[href^="/user/"]')
        if author_el:
            author = author_el.get_text(strip=True)

        # Only include 3D-related items
        if not _is_3d_related(title, tags):
            continue

        # License
        license_el = parent.select_one('a[href*="license"]')
        license_text = license_el.get_text(strip=True) if license_el else ""
        license_type = _extract_license(license_text)

        # Description from parent
        desc_el = parent.select_one(".description, p, .text")
        description = ""
        if desc_el:
            description = desc_el.get_text(strip=True)[:500]

        # File formats from tags
        file_formats = []
        format_keywords = ["obj", "fbx", "gltf", "glb", "blend", "stl", "dae", "ply", "abc"]
        for tag in tags:
            if tag.lower() in format_keywords:
                file_formats.append(tag.lower())

        # Rating (if available)
        rating = 0.0
        rating_el = parent.select_one(".rating, .stars, [class*='rate']")
        if rating_el:
            rating_text = rating_el.get_text(strip=True)
            match = re.search(r"(\d+\.?\d*)", rating_text)
            if match:
                rating = float(match.group(1))

        # Download count (if available)
        download_count = 0
        downloads_el = parent.select_one(".downloads, .download-count, [class*='download']")
        if downloads_el:
            dl_text = downloads_el.get_text(strip=True)
            match = re.search(r"(\d+)", dl_text)
            if match:
                download_count = int(match.group(1))

        record = {
            "source": "opengameart",
            "title": title,
            "description": description,
            "tags": tags[:20],
            "genre": license_type,
            "engine": "",
            "platform": "multiplatform",
            "file_size": "",
            "link": full_url,
            "thumbnail_url": thumbnail_url,
            "author": author,
            "game_id": "",
            # Enriched fields
            "license": license_type,
            "download_count": download_count,
            "view_count": 0,
            "like_count": 0,
            "rating": rating,
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
            "file_formats": file_formats,
            "asset_type": "model",
            "creation_method": "",
            "popularity_score": float(download_count + rating),
            "categories": [],
            "authors": [author] if author else [],
            "sponsors": [],
            "files_hash": "",
            "location": "",
            "square_footage": "",
            "room_count": 0,
            "version": "",
            "is_downloadable": 1,
            "engine_detected": "",
        }
        records.append(record)

    return records


def scrape_opengameart(max_pages: int = 10, rate_limit: tuple = (2, 4),
                       incremental: bool = False, enrich: bool = False, enrich_interval: int = 5) -> list[dict]:
    """
    Scrape OpenGameArt.org for 3D models with FULL data extraction.

    Returns ALL available fields: license, downloads, rating, file formats,
    authors, etc.
    """
    all_records = []
    seen_urls = set()

    for page in range(min(max_pages, 20)):
        url = f"{OGA_SEARCH_URL}?keys=model&sort=new&page={page}"
        logger.info(f"Fetching OpenGameArt page {page + 1}: {url}")

        html = _fetch_page(url, rate_limit)
        if not html:
            logger.warning(f"Failed to fetch page {page + 1}, stopping")
            break

        soup = BeautifulSoup(html, "lxml")
        records = _parse_art_links(soup)

        new_records = []
        for r in records:
            if r["link"] not in seen_urls:
                seen_urls.add(r["link"])
                new_records.append(r)

        if not new_records:
            logger.info("No more new records found — pagination complete")
            break

        logger.info(f"  Page {page + 1}: extracted {len(new_records)} records")
        all_records.extend(new_records)

        next_link = soup.select_one(".pager-next a, .pagination-next a")
        if not next_link:
            logger.info("No next page link — pagination complete")
            break

    logger.info(f"OpenGameArt: total {len(all_records)} records scraped")
    return all_records


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    records = scrape_opengameart(max_pages=3)
    print(f"\nScraped {len(records)} records")
    for r in records[:5]:
        print(f"  - {r['title']} by {r['author']}")
        print(f"    License: {r['license']}, Downloads: {r['download_count']}")
        print(f"    Tags: {r['tags'][:5]}, Formats: {r['file_formats']}")
        print(f"    {r['link']}")
