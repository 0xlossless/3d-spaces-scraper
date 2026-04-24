"""
HTTP caching layer for the 3D Spaces Dataset Scraper.
Uses requests-cache to avoid re-fetching unchanged pages.
"""

import logging
from pathlib import Path

import requests_cache

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).parent.parent.parent / "data" / "http_cache"
CACHE_BACKEND = f"sqlite:///{CACHE_DIR / 'http_cache.db'}"


def init_cache(expire_after: int = 3600, backend: str = CACHE_BACKEND) -> None:
    """
    Initialize HTTP caching.

    Args:
        expire_after: Cache expiry in seconds (default: 1 hour).
        backend: Cache backend URL.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    requests_cache.install_cache(
        cache_name=str(CACHE_DIR / "cache"),
        backend="sqlite",
        expire_after=expire_after,
        stale_if_error=True,
    )
    logger.info(f"HTTP cache initialized: {CACHE_DIR} (expiry: {expire_after}s)")


def clear_cache() -> None:
    """Clear the HTTP cache."""
    requests_cache.clear()
    logger.info("HTTP cache cleared")


def get_cache_stats() -> dict:
    """Get cache statistics."""
    session = requests_cache.CachedSession(
        cache_name=str(CACHE_DIR / "cache"),
        backend="sqlite",
    )
    return {
        "backend": "sqlite",
        "cache_dir": str(CACHE_DIR),
        "valid_responses": session.cache.responses.__len__(),
    }
