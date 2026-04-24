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

    -- License & usage
    license       TEXT,            -- CC0, CC-BY, CC-BY-NC, MIT, proprietary, etc.
    download_count INTEGER,
    view_count    INTEGER,
    like_count    INTEGER,
    rating        REAL,
    price         TEXT,
    release_date  TEXT,            -- ISO date or unix timestamp
    created_at    TEXT,
    updated_at    TEXT,

    -- 3D geometry & technical
    polycount     INTEGER,         -- triangle/vertex count
    texel_density REAL,            -- texels per unit
    dimensions_x  REAL,            -- model dimensions in mm
    dimensions_y  REAL,
    dimensions_z  REAL,
    max_resolution_w INTEGER,      -- max texture/resolution width
    max_resolution_h INTEGER,
    file_formats  TEXT,            -- JSON array: ["glb", "fbx", "obj", ...]
    asset_type    TEXT,            -- model, hdri, texture, material, virtual-tour, game, demo
    creation_method TEXT,          -- PBRPhotogrammetry, 3DSoftware, Scan, etc.
    popularity_score REAL,

    -- Taxonomy & attribution
    categories    TEXT,            -- JSON array: ["furniture", "seating"]
    authors       TEXT,            -- JSON array: ["Author Name", "Contributor"]
    sponsors      TEXT,            -- JSON array of sponsor IDs
    files_hash    TEXT,            -- SHA1 hash for version tracking
    location      TEXT,            -- GPS coords or physical location
    square_footage TEXT,
    room_count    INTEGER,
    version       TEXT,            -- software version or asset version
    is_downloadable INTEGER,       -- 0 or 1
    engine_detected TEXT,          -- Unity, Unreal, Godot, Three.js, etc.

    UNIQUE(link, source)
);

CREATE INDEX IF NOT EXISTS idx_source ON records(source);
CREATE INDEX IF NOT EXISTS idx_scraped_at ON records(scraped_at);
CREATE INDEX IF NOT EXISTS idx_license ON records(license);
CREATE INDEX IF NOT EXISTS idx_asset_type ON records(asset_type);
CREATE INDEX IF NOT EXISTS idx_download_count ON records(download_count);

-- Track last scrape time per source for incremental scraping
CREATE TABLE IF NOT EXISTS scrape_meta (
    source        TEXT PRIMARY KEY,
    last_scraped  TEXT,
    total_records INTEGER DEFAULT 0
);
"""

MIGRATION_COLUMNS = [
    "license TEXT",
    "download_count INTEGER",
    "view_count INTEGER",
    "like_count INTEGER",
    "rating REAL",
    "price TEXT",
    "release_date TEXT",
    "created_at TEXT",
    "updated_at TEXT",
    "polycount INTEGER",
    "texel_density REAL",
    "dimensions_x REAL",
    "dimensions_y REAL",
    "dimensions_z REAL",
    "max_resolution_w INTEGER",
    "max_resolution_h INTEGER",
    "file_formats TEXT",
    "asset_type TEXT",
    "creation_method TEXT",
    "popularity_score REAL",
    "categories TEXT",
    "authors TEXT",
    "sponsors TEXT",
    "files_hash TEXT",
    "location TEXT",
    "square_footage TEXT",
    "room_count INTEGER",
    "version TEXT",
    "is_downloadable INTEGER",
    "engine_detected TEXT",
]

INSERT_COLUMNS = """
    id, source, title, description, tags, genre, engine,
    platform, file_size, link, thumbnail_url, scraped_at,
    author, game_id,
    license, download_count, view_count, like_count, rating, price,
    release_date, created_at, updated_at,
    polycount, texel_density, dimensions_x, dimensions_y, dimensions_z,
    max_resolution_w, max_resolution_h, file_formats, asset_type,
    creation_method, popularity_score,
    categories, authors, sponsors, files_hash, location,
    square_footage, room_count, version, is_downloadable, engine_detected
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
        self._run_migrations()
        self.conn.commit()
        logger.info(f"Database ready: {self.db_path}")

    def _run_migrations(self):
        """Add new columns if they don't exist (safe for existing DBs)."""
        existing = self._get_columns()
        for col_def in MIGRATION_COLUMNS:
            col_name = col_def.split()[0]
            if col_name not in existing:
                try:
                    self.conn.execute(f"ALTER TABLE records ADD COLUMN {col_def}")
                    logger.info(f"Migration: added column '{col_name}'")
                except sqlite3.OperationalError:
                    pass  # Column already exists or conflict

    def _get_columns(self) -> set:
        """Get set of existing column names."""
        rows = self.conn.execute("PRAGMA table_info(records)").fetchall()
        return {r[1] for r in rows}

    def _serialize_json(self, value) -> str:
        """Convert list/dict to JSON string for storage."""
        if isinstance(value, str):
            return value
        if value is None:
            return ""
        return json.dumps(value)

    def insert_or_ignore(self, record: dict) -> bool:
        """
        Insert a record, ignoring if link+source already exists.

        Returns:
            True if inserted, False if duplicate.
        """
        try:
            self.conn.execute(
                f"""
                INSERT OR IGNORE INTO records ({INSERT_COLUMNS})
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                        ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.get("id", ""),
                    record.get("source", ""),
                    record.get("title", ""),
                    record.get("description", ""),
                    self._serialize_json(record.get("tags", [])),
                    record.get("genre", ""),
                    record.get("engine", ""),
                    record.get("platform", ""),
                    record.get("file_size", ""),
                    record.get("link", ""),
                    record.get("thumbnail_url", ""),
                    record.get("scraped_at", ""),
                    record.get("author", ""),
                    record.get("game_id", ""),
                    # New fields
                    record.get("license", ""),
                    record.get("download_count", 0) or 0,
                    record.get("view_count", 0) or 0,
                    record.get("like_count", 0) or 0,
                    record.get("rating", 0.0) or 0.0,
                    record.get("price", ""),
                    record.get("release_date", ""),
                    record.get("created_at", ""),
                    record.get("updated_at", ""),
                    record.get("polycount", 0) or 0,
                    record.get("texel_density", 0.0) or 0.0,
                    record.get("dimensions_x", 0.0) or 0.0,
                    record.get("dimensions_y", 0.0) or 0.0,
                    record.get("dimensions_z", 0.0) or 0.0,
                    record.get("max_resolution_w", 0) or 0,
                    record.get("max_resolution_h", 0) or 0,
                    self._serialize_json(record.get("file_formats", [])),
                    record.get("asset_type", ""),
                    record.get("creation_method", ""),
                    record.get("popularity_score", 0.0) or 0.0,
                    self._serialize_json(record.get("categories", [])),
                    self._serialize_json(record.get("authors", [])),
                    self._serialize_json(record.get("sponsors", [])),
                    record.get("files_hash", ""),
                    record.get("location", ""),
                    record.get("square_footage", ""),
                    record.get("room_count", 0) or 0,
                    record.get("version", ""),
                    record.get("is_downloadable", 0) or 0,
                    record.get("engine_detected", ""),
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
