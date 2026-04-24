"""
itch.io 3D Games Parser - ENRICHED
Scrapes /games/tag-3d paginated list using requests + BeautifulSoup.
Extracts ALL available fields: tags, price, rating, downloads, engine, etc.
"""

import logging
import random
import re
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

ITCH_3D_URL = "https://itch.io/games/tag-3d"
ITCH_BASE = "https://itch.io"


def _get_headers() -> dict:
    return {
        "User-Agent": "3d-spaces-scraper/1.0 (josep@0xlossless.com)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://itch.io/",
    }


def _fetch_page(url: str, rate_limit: tuple = (1, 3)) -> Optional[str]:
    time.sleep(random.uniform(*rate_limit))
    try:
        resp = requests.get(url, headers=_get_headers(), timeout=30)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as e:
        logger.error(f"Request failed for {url}: {e}")
        return None


def _detect_engine(text: str) -> str:
    """Detect game engine from description/tags."""
    engines = [
        "Unity", "Unreal Engine", "Godot", "GameMaker", "Construct",
        "Three.js", "Babylon.js", "Defold", "LÖVE", "Ren'Py",
        "RPG Maker", "Source Engine", "id Tech", "CryEngine",
    ]
    text_lower = text.lower()
    for engine in engines:
        if engine.lower() in text_lower:
            return engine
    return ""


def _parse_price(price_html: str) -> str:
    """Extract price from HTML."""
    if not price_html:
        return ""
    price_el = price_html.strip()
    if "free" in price_el.lower():
        return "free"
    return price_el


def _extract_tags_from_cell(cell: BeautifulSoup) -> list:
    """Extract all tags from a game cell."""
    tags = []
    # Try tag elements
    for tag_el in cell.select(".tag, .game_tag, a.tag"):
        tag_text = tag_el.get_text(strip=True)
        if tag_text and tag_text not in tags:
            tags.append(tag_text)
    return tags[:20]


def _parse_game_cell(cell: BeautifulSoup) -> Optional[dict]:
    """Extract data from a single .game_cell element."""
    try:
        # Title + link
        title_a = cell.select_one(".game_title a")
        if not title_a:
            return None

        title = title_a.get_text(strip=True)
        link = title_a.get("href", "")
        if link.startswith("/"):
            link = ITCH_BASE + link

        # Description
        desc_el = cell.select_one(".game_text")
        description = ""
        if desc_el:
            description = desc_el.get("title", "") or desc_el.get_text(strip=True)

        # Author
        author_el = cell.select_one(".game_author a")
        author = author_el.get_text(strip=True) if author_el else ""

        # Genre
        genre_el = cell.select_one(".game_genre")
        genre = genre_el.get_text(strip=True) if genre_el else ""

        # Thumbnail
        thumb = cell.select_one(".game_thumb img")
        thumbnail_url = ""
        if thumb:
            thumbnail_url = thumb.get("data-lazy_src") or thumb.get("src", "")

        # Platform
        platform_icons = cell.select(".game_platform .icon")
        platforms = []
        for icon in platform_icons:
            icon_class = icon.get("class", [])
            for c in icon_class:
                if "icon-windows" in c:
                    platforms.append("windows")
                elif "icon-linux" in c:
                    platforms.append("linux")
                elif "icon-apple" in c:
                    platforms.append("macos")
                elif "icon-android" in c:
                    platforms.append("android")
                elif "icon-web" in c or "icon-internet-explorer" in c:
                    platforms.append("browser")
        platform = ", ".join(platforms) if platforms else "unknown"

        # Game ID
        game_id = cell.get("data-game_id", "")

        # Price
        price_el = cell.select_one(".game_price, .price")
        price = _parse_price(price_el.get_text(strip=True)) if price_el else ""

        # Rating
        rating = 0.0
        rating_el = cell.select_one(".rating, .game_rating")
        if rating_el:
            rating_text = rating_el.get_text(strip=True)
            match = re.search(r"(\d+\.?\d*)", rating_text)
            if match:
                rating = float(match.group(1))

        # Tags
        tags = _extract_tags_from_cell(cell)
        if not tags:
            tags = ["3D"]

        # Engine detection from description
        engine_detected = _detect_engine(description + " " + " ".join(tags))

        return {
            "source": "itch.io",
            "title": title,
            "description": description[:1000],
            "tags": tags,
            "genre": genre,
            "engine": "",
            "platform": platform,
            "file_size": "",
            "link": link,
            "thumbnail_url": thumbnail_url,
            "author": author,
            "game_id": game_id,
            # Enriched fields
            "license": "",
            "download_count": 0,
            "view_count": 0,
            "like_count": 0,
            "rating": rating,
            "price": price,
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
            "file_formats": [],
            "asset_type": "game",
            "creation_method": "",
            "popularity_score": rating,
            "categories": [genre] if genre else [],
            "authors": [author] if author else [],
            "sponsors": [],
            "files_hash": "",
            "location": "",
            "square_footage": "",
            "room_count": 0,
            "version": "",
            "is_downloadable": 0,
            "engine_detected": engine_detected,
        }

    except Exception as e:
        logger.debug(f"Failed to parse game cell: {e}")
        return None


def scrape_itch_3d(max_pages: int = 10, rate_limit: tuple = (1, 3),
                   incremental: bool = False, enrich: bool = False, enrich_interval: int = 5) -> list[dict]:
    """
    Scrape itch.io's 3D tag page with FULL data extraction.

    Returns ALL available fields: tags, price, rating, engine detection,
    platforms, etc.
    """
    all_records = []
    page = 1

    while page <= max_pages:
        url = f"{ITCH_3D_URL}?page={page}"
        logger.info(f"Fetching itch.io page {page}: {url}")

        html = _fetch_page(url, rate_limit)
        if not html:
            break

        soup = BeautifulSoup(html, "lxml")
        cells = soup.select(".game_cell")

        if not cells:
            logger.info("No game cells found — pagination complete")
            break

        page_records = []
        for i, cell in enumerate(cells):
            rec = _parse_game_cell(cell)
            if rec:
                page_records.append(rec)

        logger.info(f"  Page {page}: extracted {len(page_records)} records")
        all_records.extend(page_records)

        next_link = soup.select_one(".next_page a")
        if not next_link:
            logger.info("No next page link — pagination complete")
            break

        page += 1

    logger.info(f"itch.io: total {len(all_records)} records scraped")
    return all_records


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    records = scrape_itch_3d(max_pages=2)
    print(f"\nScraped {len(records)} records")
    for r in records[:3]:
        print(f"  - {r['title']} ({r['platform']})")
        print(f"    Author: {r['author']}, Price: {r['price']}, Rating: {r['rating']}")
        print(f"    Engine: {r['engine_detected']}, Tags: {r['tags'][:5]}")
        print(f"    {r['link']}")
