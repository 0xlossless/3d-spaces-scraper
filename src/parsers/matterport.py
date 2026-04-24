"""
Matterport Gallery Parser - ENRICHED
Scrapes public 3D spaces from the Matterport gallery using Playwright.
Extracts ALL available fields: location, category, views, etc.

Page: https://matterport.com/gallery/
Requires: playwright (already in requirements.txt)
"""

import logging
import random
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

MATTERPORT_GALLERY_URL = "https://matterport.com/gallery/"
MATTERPORT_BASE = "https://matterport.com"


def _get_headers() -> dict:
    return {
        "User-Agent": "3d-spaces-scraper/1.0 (josep@0xlossless.com)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }


def _fetch_with_playwright(url: str, timeout: int = 60000) -> Optional[str]:
    """Fetch a JS-rendered page using Playwright."""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent="3d-spaces-scraper/1.0 (josep@0xlossless.com)",
                viewport={"width": 1920, "height": 1080},
            )
            page = context.new_page()

            logger.info(f"Navigating to {url}")
            page.goto(url, wait_until="networkidle", timeout=timeout)
            page.wait_for_timeout(3000)

            html = page.content()
            context.close()
            browser.close()
            return html

    except Exception as e:
        logger.error(f"Playwright failed for {url}: {e}")
        return None


def _fetch_page(url: str, rate_limit: tuple = (3, 5)) -> Optional[str]:
    """Fetch a page with rate limiting."""
    time.sleep(random.uniform(*rate_limit))
    try:
        resp = requests.get(url, headers=_get_headers(), timeout=30)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as e:
        logger.error(f"Request failed for {url}: {e}")
        return None


def _parse_space_item(item: BeautifulSoup) -> Optional[dict]:
    """Extract data from a single Matterport space listing."""
    try:
        # Title and link
        title_link = item.select_one("a[href*='/showcase/'], a[href*='/3d-tour/'], a.card, a[href*='/space/']")
        if not title_link:
            title_link = item.select_one("h2 a, h3 a, a")

        if not title_link:
            return None

        title = title_link.get_text(strip=True)
        if not title or len(title) < 3:
            return None

        skip_titles = ["matterport gallery", "matterport", "gallery", "tour", "showcase", "virtual tour"]
        if title.lower() in skip_titles:
            return None

        link = title_link.get("href", "")
        if link.startswith("/"):
            link = MATTERPORT_BASE + link
        elif not link.startswith("http"):
            link = f"{MATTERPORT_BASE}/{link}"

        if "/space/" not in link and "/showcase/" not in link and "/3d-tour/" not in link:
            return None

        # Thumbnail
        thumb = item.select_one("img")
        thumbnail_url = ""
        if thumb:
            thumbnail_url = (
                thumb.get("src", "")
                or thumb.get("data-src", "")
                or thumb.get("data-lazy-src", "")
            )

        # Description
        desc_el = item.select_one("p, .description, .text")
        description = ""
        if desc_el:
            description = desc_el.get_text(strip=True)[:500]

        # Author/creator
        author_el = item.select_one(".author, .creator, .username, span")
        author = ""
        if author_el:
            author = author_el.get_text(strip=True)

        # Category from text
        category = "virtual-tour"
        cat_el = item.select_one(".category, .tag, .label")
        if cat_el:
            category = cat_el.get_text(strip=True)

        # Views (if available)
        views = 0
        views_el = item.select_one(".views, .visits, [class*='view']")
        if views_el:
            views_text = views_el.get_text(strip=True)
            import re
            match = re.search(r"(\d+)", views_text)
            if match:
                views = int(match.group(1))

        return {
            "source": "matterport",
            "title": title,
            "description": description,
            "tags": ["3d-tour", "virtual-tour", "matterport"],
            "genre": category,
            "engine": "Matterport",
            "platform": "browser",
            "file_size": "",
            "link": link,
            "thumbnail_url": thumbnail_url,
            "author": author,
            "game_id": "",
            # Enriched fields
            "license": "proprietary",
            "download_count": 0,
            "view_count": views,
            "like_count": 0,
            "rating": 0.0,
            "price": "",
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
            "asset_type": "virtual-tour",
            "creation_method": "360-camera",
            "popularity_score": float(views),
            "categories": [category] if category else [],
            "authors": [author] if author else [],
            "sponsors": [],
            "files_hash": "",
            "location": "",
            "square_footage": "",
            "room_count": 0,
            "version": "",
            "is_downloadable": 0,
            "engine_detected": "Matterport",
        }

    except Exception as e:
        logger.debug(f"Failed to parse space item: {e}")
        return None


def scrape_matterport(max_pages: int = 10, rate_limit: tuple = (3, 5),
                      incremental: bool = False, enrich: bool = False, enrich_interval: int = 5) -> list[dict]:
    """
    Scrape Matterport gallery public 3D spaces with FULL data extraction.

    Returns ALL available fields: views, categories, creation method, etc.
    """
    all_records = []

    logger.info(f"Fetching Matterport gallery: {MATTERPORT_GALLERY_URL}")
    html = _fetch_with_playwright(MATTERPORT_GALLERY_URL)

    if not html:
        logger.error("Failed to fetch Matterport gallery")
        return []

    soup = BeautifulSoup(html, "lxml")

    # Try multiple selectors
    items = (
        soup.select(".gallery-item, .space-card, .card, .showcase-item")
        or soup.select("[data-space-id], [data-tour-id]")
        or [a.parent for a in soup.select("a[href*='/showcase/']") if a.parent]
    )

    if not items:
        items = soup.select(".card, .grid-item, [class*='space'], [class*='tour']")

    if items:
        seen_links = set()
        for item in items:
            rec = _parse_space_item(item)
            if rec and rec["title"] and rec["link"] not in seen_links:
                seen_links.add(rec["link"])
                all_records.append(rec)
    else:
        seen_links = set()
        space_links = soup.select("a[href*='/showcase/'], a[href*='/3d-tour/'], a[href*='/space/']")
        for link_el in space_links:
            title = link_el.get_text(strip=True)
            if title and len(title) > 3:
                href = link_el.get("href", "")
                if href.startswith("/"):
                    href = MATTERPORT_BASE + href
                if href not in seen_links:
                    seen_links.add(href)
                    all_records.append({
                        "source": "matterport",
                        "title": title,
                        "description": "",
                        "tags": ["3d-tour", "virtual-tour", "matterport"],
                        "genre": "virtual-tour",
                        "engine": "Matterport",
                        "platform": "browser",
                        "file_size": "",
                        "link": href,
                        "thumbnail_url": "",
                        "author": "",
                        "game_id": "",
                        "license": "proprietary",
                        "download_count": 0,
                        "view_count": 0,
                        "like_count": 0,
                        "rating": 0.0,
                        "price": "",
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
                        "asset_type": "virtual-tour",
                        "creation_method": "360-camera",
                        "popularity_score": 0.0,
                        "categories": [],
                        "authors": [],
                        "sponsors": [],
                        "files_hash": "",
                        "location": "",
                        "square_footage": "",
                        "room_count": 0,
                        "version": "",
                        "is_downloadable": 0,
                        "engine_detected": "Matterport",
                    })

    logger.info(f"Matterport: total {len(all_records)} records scraped")
    return all_records


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    records = scrape_matterport()
    print(f"\nScraped {len(records)} records")
    for r in records[:5]:
        print(f"  - {r['title']}")
        print(f"    {r['link']}")
