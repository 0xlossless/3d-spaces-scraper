"""
SQLite storage layer for 3D Spaces Dataset.
Handles schema creation, inserts with deduplication, and queries.
"""

import json
import logging
import sqlite3
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS records (
    id            TEXT PRIMARY KEY,
    source        TEXT    NOT NULL,
    title         TEXT    NOT NULL,
    description   TEXT,
    tags          TEXT,          -- JSON array stored as text
    genre         TEXT,
    engine        TEXT,
    platform      TEXT,
    file_size     TEXT,
    link          TEXT    NOT NULL,
    thumbnail_url TEXT,
    scraped_at    TEXT    NOT NULL,
    author        TEXT,            -- creator/developer name
    game_id       TEXT,            -- source-specific ID (e.g. itch.io game_id)

    UNIQUE(link, source)
);

CREATE INDEX IF NOT EXISTS idx_source ON records(source);
CREATE INDEX IF NOT EXISTS idx_scraped_at ON records(scraped_at);

-- Track last scrape time per source for incremental scraping
CREATE TABLE IF NOT EXISTS scrape_meta (
    source        TEXT PRIMARY KEY,
    last_scraped  TEXT,
    total_records INTEGER DEFAULT 0
);
"""


class Database:
    """SQLite-backed storage with deduplication."""

    def __init__(self, db_path: str = "data/3d_spaces.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self):
        self.conn.executescript(SCHEMA_SQL)
        self.conn.commit()
        logger.info(f"Database ready: {self.db_path}")

    def _serialize_tags(self, tags: list) -> str:
        """Convert tags list to JSON string for storage."""
        if isinstance(tags, str):
            return tags
        return json.dumps(tags)

    def insert_or_ignore(self, record: dict) -> bool:
        """
        Insert a record, ignoring if link+source already exists.

        Returns:
            True if inserted, False if duplicate.
        """
        try:
            self.conn.execute(
                """
                INSERT OR IGNORE INTO records
                    (id, source, title, description, tags, genre, engine,
                     platform, file_size, link, thumbnail_url, scraped_at,
                     author, game_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.get("id", ""),
                    record.get("source", ""),
                    record.get("title", ""),
                    record.get("description", ""),
                    self._serialize_tags(record.get("tags", [])),
                    record.get("genre", ""),
                    record.get("engine", ""),
                    record.get("platform", ""),
                    record.get("file_size", ""),
                    record.get("link", ""),
                    record.get("thumbnail_url", ""),
                    record.get("scraped_at", ""),
                    record.get("author", ""),
                    record.get("game_id", ""),
                ),
            )
            self.conn.commit()
            return self.conn.total_changes > 0
        except sqlite3.IntegrityError as e:
            logger.debug(f"Duplicate record skipped: {e}")
            return False

    def update_scrape_meta(self, source: str, count: int):
        """Update scrape metadata for a source."""
        from datetime import datetime, timezone

        self.conn.execute(
            """
            INSERT INTO scrape_meta (source, last_scraped, total_records)
            VALUES (?, ?, ?)
            ON CONFLICT(source) DO UPDATE SET
                last_scraped = excluded.last_scraped,
                total_records = excluded.total_records
            """,
            (source, datetime.now(timezone.utc).isoformat(), count),
        )
        self.conn.commit()

    def get_last_scraped(self, source: str) -> Optional[str]:
        """Get last scrape time for a source."""
        row = self.conn.execute(
            "SELECT last_scraped FROM scrape_meta WHERE source = ?", (source,)
        ).fetchone()
        return row["last_scraped"] if row else None

    def count(self) -> int:
        """Total records in database."""
        row = self.conn.execute("SELECT COUNT(*) as c FROM records").fetchone()
        return row["c"]

    def count_by_source(self) -> dict:
        """Record counts grouped by source."""
        rows = self.conn.execute(
            "SELECT source, COUNT(*) as c FROM records GROUP BY source"
        ).fetchall()
        return {r["source"]: r["c"] for r in rows}

    def get_recent(self, limit: int = 10) -> list[dict]:
        """Get the most recently scraped records."""
        rows = self.conn.execute(
            "SELECT * FROM records ORDER BY scraped_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def close(self):
        self.conn.close()
        logger.info("Database closed")
