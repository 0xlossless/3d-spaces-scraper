"""
Matterport Gallery Parser
Scrapes public 3D spaces from the Matterport gallery using Playwright.

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
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }


def _fetch_with_playwright(url: str, timeout: int = 60000) -> Optional[str]:
    """Fetch a JS-rendered page using Playwright."""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/125.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1920, "height": 1080},
            )
            page = context.new_page()

            logger.info(f"Navigating to {url}")
            page.goto(url, wait_until="networkidle", timeout=timeout)

            # Wait for gallery items to load
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
            # Try any link with meaningful text
            title_link = item.select_one("h2 a, h3 a, a")

        if not title_link:
            return None

        title = title_link.get_text(strip=True)
        if not title or len(title) < 3:
            return None

        # Filter out navigation/UI elements
        skip_titles = ["matterport gallery", "matterport", "gallery", "tour", "showcase", "virtual tour"]
        if title.lower() in skip_titles:
            return None

        link = title_link.get("href", "")
        if link.startswith("/"):
            link = MATTERPORT_BASE + link
        elif not link.startswith("http"):
            link = f"{MATTERPORT_BASE}/{link}"

        # Skip non-space links
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

        # Tags from any visible text elements
        tags = ["3d-tour", "virtual-tour", "matterport"]

        return {
            "source": "matterport",
            "title": title,
            "description": description,
            "tags": tags,
            "genre": "virtual-tour",
            "engine": "Matterport",
            "platform": "browser",
            "file_size": "",
            "link": link,
            "thumbnail_url": thumbnail_url,
            "author": author,
            "game_id": "",
        }

    except Exception as e:
        logger.debug(f"Failed to parse space item: {e}")
        return None


def scrape_matterport(max_pages: int = 10, rate_limit: tuple = (3, 5),
                      incremental: bool = False, enrich: bool = False, enrich_interval: int = 5) -> list[dict]:
    """
    Scrape Matterport gallery public 3D spaces.

    Uses Playwright for JS rendering, then BeautifulSoup for parsing.

    Args:
        max_pages: Maximum pages (Matterport gallery is typically single-page with load-more).
        rate_limit: (min_seconds, max_seconds) between requests.

    Returns:
        List of record dicts matching the data schema.
    """
    all_records = []

    # Fetch the initial gallery page with JS rendering
    logger.info(f"Fetching Matterport gallery: {MATTERPORT_GALLERY_URL}")
    html = _fetch_with_playwright(MATTERPORT_GALLERY_URL)

    if not html:
        logger.error("Failed to fetch Matterport gallery")
        return []

    soup = BeautifulSoup(html, "lxml")

    # Try multiple selectors for gallery items
    items = (
        soup.select(".gallery-item, .space-card, .card, .showcase-item")
        or soup.select("[data-space-id], [data-tour-id]")
        or [a.parent for a in soup.select("a[href*='/showcase/']") if a.parent]
    )

    if not items:
        # Try finding all cards or grid items
        items = soup.select(".card, .grid-item, [class*='space'], [class*='tour']")

    if items:
        seen_links = set()
        for item in items:
            rec = _parse_space_item(item)
            if rec and rec["title"] and rec["link"] not in seen_links:
                seen_links.add(rec["link"])
                all_records.append(rec)
    else:
        # Fallback: try to extract any links that look like space URLs
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
