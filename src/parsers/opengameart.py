"""
OpenGameArt.org 3D Models Parser
Scrapes 3D model listings from OpenGameArt.org.

Uses the art search with proper form parameters.
"""

import logging
import random
import time
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

OGA_SEARCH_URL = "https://opengameart.org/art-search"
OGA_BASE = "https://opengameart.org"


def _get_headers() -> dict:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/125.0.0.0 Safari/537.36"
        ),
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

    # Keywords that indicate 3D content
    _3d_keywords = [
        "3d", "model", "models", "mesh", "polygon", "poly", "lowpoly", "low-poly",
        "obj", "fbx", "gltf", "glb", "blend", "maya", "blender", "c4d",
        "character", "prop", "environment", "terrain", "vehicle", "weapon",
        "animated", "rigged", "skinned", "vertex", "normal map", "bake",
    ]

    return any(kw in all_text for kw in _3d_keywords)


def _parse_art_links(soup: BeautifulSoup) -> list[dict]:
    """Extract art items from search results."""
    records = []

    # Find all content links (art items)
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

        # Build full URL
        full_url = OGA_BASE + href if href.startswith("/") else href

        # Get parent container for more info
        parent = link.parent
        if not parent:
            continue

        # Thumbnail
        thumb = parent.select_one("img")
        thumbnail_url = ""
        if thumb:
            thumbnail_url = thumb.get("src", "") or thumb.get("data-src", "")

        # Find tags in parent
        tags = []
        for tag_link in parent.select("a[href^=\"/tag/\"]"):
            tag_text = tag_link.get_text(strip=True)
            if tag_text:
                tags.append(tag_text)

        # Find author
        author = ""
        author_el = parent.select_one("a[href^=\"/user/\"]")
        if author_el:
            author = author_el.get_text(strip=True)

        # Only include 3D-related items
        if not _is_3d_related(title, tags):
            continue

        # License from parent
        license_el = parent.select_one("a[href*=\"license\"]")
        genre = license_el.get_text(strip=True) if license_el else ""

        record = {
            "source": "opengameart",
            "title": title,
            "description": "",
            "tags": tags[:10],
            "genre": genre,
            "engine": "",
            "platform": "multiplatform",
            "file_size": "",
            "link": full_url,
            "thumbnail_url": thumbnail_url,
            "author": author,
            "game_id": "",
        }
        records.append(record)

    return records


def scrape_opengameart(max_pages: int = 10, rate_limit: tuple = (2, 4)) -> list[dict]:
    """
    Scrape OpenGameArt.org for 3D models.

    Searches for "model" keyword to find 3D model listings.

    Args:
        max_pages: Maximum number of pages to scrape.
        rate_limit: (min_seconds, max_seconds) between requests.

    Returns:
        List of record dicts matching the data schema.
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

        # Deduplicate
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

        # Check for next page
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
        print(f"    Tags: {r['tags']}")
        print(f"    {r['link']}")
