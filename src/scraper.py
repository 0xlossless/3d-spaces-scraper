"""
3D Spaces Dataset Scraper
Main orchestrator — loads config, runs parsers, stores results.
"""

import importlib
import hashlib
import logging
import random
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

from src.http_cache import init_cache, get_cache_stats
from src.storage.database import Database

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def load_config(path: str = "config.yaml") -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def make_record_id(source: str, url: str) -> str:
    """Generate a stable unique hash from source + URL."""
    raw = f"{source}|{url}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _load_parser(module_path: str, function_name: str):
    """Dynamically import a parser function from a module path."""
    module = importlib.import_module(module_path)
    return getattr(module, function_name)


def run_scraper(config: dict, incremental: bool = False) -> dict:
    """
    Run the scraper pipeline.

    Args:
        config: Configuration dict from config.yaml.
        incremental: If True, only fetch pages with new content since last run.

    Returns:
        Summary dict with counts.
    """
    # Initialize HTTP cache
    cache_ttl = config.get("scraping", {}).get("cache_ttl", 3600)
    init_cache(expire_after=cache_ttl)
    cache_stats = get_cache_stats()
    logger.info(f"HTTP cache: {cache_stats}")

    storage_cfg = config["storage"]
    db = Database(storage_cfg["database"])

    scrape_cfg = config["scraping"]
    max_pages = scrape_cfg["max_pages_per_source"]

    sources = config["sources"]
    total_new = 0
    total_skipped = 0
    total_cached = 0
    source_summaries = []

    for source_cfg in sources:
        if not source_cfg.get("enabled", True):
            logger.info(f"Skipping disabled source: {source_cfg['name']}")
            continue

        name = source_cfg["name"]
        logger.info(f"\n{'='*60}")
        logger.info(f"Scraping source: {name}")
        logger.info(f"{'='*60}")

        # Per-source rate limits (override global if set)
        source_rate = source_cfg.get("rate_limit", {})
        rate_min = source_rate.get("min", scrape_cfg["rate_limit_min"])
        rate_max = source_rate.get("max", scrape_cfg["rate_limit_max"])
        source_max_pages = source_cfg.get("max_pages", max_pages)

        # Enrichment settings
        enrich = source_cfg.get("enrich", {})
        enrich_enabled = enrich.get("enabled", False)
        enrich_interval = enrich.get("interval", 5)  # enrich every Nth item

        parsers = source_cfg.get("parsers", [])
        if not parsers:
            logger.warning(f"No parsers configured for source: {name}")
            continue

        all_records = []
        for parser_cfg in parsers:
            module_path = parser_cfg["module"]
            function_name = parser_cfg["function"]

            try:
                parser_fn = _load_parser(module_path, function_name)
            except (ImportError, AttributeError) as e:
                logger.error(f"Failed to load parser {module_path}.{function_name}: {e}")
                continue

            try:
                raw_records = parser_fn(
                    max_pages=source_max_pages,
                    rate_limit=(rate_min, rate_max),
                    incremental=incremental,
                    enrich=enrich_enabled,
                    enrich_interval=enrich_interval,
                )
                all_records.extend(raw_records)
                logger.info(f"  Parser {function_name}: {len(raw_records)} records")
            except Exception as e:
                logger.error(f"Parser {function_name} failed for {name}: {e}", exc_info=True)
                continue

        new_count = 0
        skip_count = 0
        for rec in all_records:
            rec["id"] = make_record_id(rec["source"], rec["link"])
            rec["scraped_at"] = datetime.now(timezone.utc).isoformat()

            if db.insert_or_ignore(rec):
                new_count += 1
            else:
                skip_count += 1

        total_new += new_count
        total_skipped += skip_count

        source_summaries.append({
            "source": name,
            "total": len(all_records),
            "new": new_count,
            "skipped": skip_count,
        })

        logger.info(f"  {name}: {len(all_records)} total (new={new_count}, skipped={skip_count})")

        # Small delay between sources
        if new_count > 0:
            time.sleep(random.uniform(2, 5))

    db.close()

    # Final cache stats
    final_cache = get_cache_stats()
    logger.info(f"\n{'='*60}")
    logger.info(f"Done. Total new: {total_new}, Total skipped (dupes): {total_skipped}")
    logger.info(f"HTTP cache: {final_cache}")
    logger.info(f"{'='*60}")

    return {
        "total_new": total_new,
        "total_skipped": total_skipped,
        "sources": source_summaries,
    }


if __name__ == "__main__":
    config = load_config()
    run_scraper(config)
