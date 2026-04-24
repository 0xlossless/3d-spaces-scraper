"""
itch.io 3D Games Parser
Scrapes /games/tag-3d paginated list using requests + BeautifulSoup.

Page structure:
  .game_grid_widget > .game_cell (x36 per page)
    .game_title a          → title + link
    .game_text             → description
    .game_author a         → author
    .game_genre            → genre
    .game_thumb img        → thumbnail (data-lazy_src)
    .game_platform         → platform icons
  Pagination: ?page=N query parameter
"""

import logging
import random
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

ITCH_3D_URL = "https://itch.io/games/tag-3d"
ITCH_BASE = "https://itch.io"


def _get_headers() -> dict:
    """Build request headers."""
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://itch.io/",
    }


def _fetch_page(url: str, rate_limit: tuple = (1, 3)) -> Optional[str]:
    """Fetch a page with rate limiting and error handling."""
    time.sleep(random.uniform(*rate_limit))
    try:
        resp = requests.get(url, headers=_get_headers(), timeout=30)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as e:
        logger.error(f"Request failed for {url}: {e}")
        return None


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
        description = desc_el.get("title", "") or desc_el.get_text(strip=True) if desc_el else ""

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

        # Game ID from data attribute
        game_id = cell.get("data-game_id", "")

        return {
            "source": "itch.io",
            "title": title,
            "description": description[:500],
            "tags": ["3D"],  # All results are from tag-3d
            "genre": genre,
            "engine": "",
            "platform": platform,
            "file_size": "",
            "link": link,
            "thumbnail_url": thumbnail_url,
            "author": author,
            "game_id": game_id,
        }

    except Exception as e:
        logger.debug(f"Failed to parse game cell: {e}")
        return None


def scrape_itch_3d(max_pages: int = 10, rate_limit: tuple = (1, 3)) -> list[dict]:
    """
    Scrape itch.io's 3D tag page, paginating through results.

    Args:
        max_pages: Maximum number of pages to scrape.
        rate_limit: (min_seconds, max_seconds) between requests.

    Returns:
        List of record dicts matching the data schema.
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
        for cell in cells:
            rec = _parse_game_cell(cell)
            if rec:
                page_records.append(rec)

        logger.info(f"  Page {page}: extracted {len(page_records)} records")
        all_records.extend(page_records)

        # Check for next page
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
        print(f"    {r['link']}")
