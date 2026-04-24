"""
Analytics Engine.
Parquet exports, DuckDB queries, and data insights.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import duckdb
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

logger = logging.getLogger(__name__)


class AnalyticsEngine:
    """Analytics and export engine for 3D Spaces Dataset."""

    def __init__(self, db, export_dir: str = "data/exports"):
        self.db = db
        self.export_dir = Path(export_dir)
        self.export_dir.mkdir(parents=True, exist_ok=True)
        self.duckdb = duckdb.connect(":memory:")

    def to_dataframe(self, source: Optional[str] = None) -> pd.DataFrame:
        """Export records to pandas DataFrame."""
        query = "SELECT * FROM records"
        params = ()
        if source:
            query += " WHERE source = ?"
            params = (source,)

        df = pd.read_sql_query(query, self.db.conn, params=params)

        # Parse JSON fields
        for col in ["tags", "categories", "authors", "sponsors", "file_formats"]:
            if col in df.columns:
                df[col] = df[col].apply(
                    lambda x: json.loads(x) if isinstance(x, str) and x.startswith("[") else []
                )
                # Convert lists to strings for parquet compatibility
                df[col] = df[col].apply(lambda x: json.dumps(x) if isinstance(x, list) else x)

        return df

    def export_parquet(self, source: Optional[str] = None, timestamp: bool = True) -> str:
        """Export to Parquet format (analytics-ready, columnar storage)."""
        df = self.to_dataframe(source)

        if timestamp:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            suffix = f"_{ts}"
        else:
            suffix = ""

        filename = f"3d_spaces{suffix}.parquet"
        filepath = self.export_dir / filename

        df.to_parquet(filepath, index=False, engine="pyarrow")
        logger.info(f"Exported {len(df)} records to {filepath}")
        return str(filepath)

    def export_csv(self, source: Optional[str] = None, timestamp: bool = True) -> str:
        """Export to CSV format."""
        df = self.to_dataframe(source)

        if timestamp:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            suffix = f"_{ts}"
        else:
            suffix = ""

        filename = f"3d_spaces{suffix}.csv"
        filepath = self.export_dir / filename

        df.to_csv(filepath, index=False)
        logger.info(f"Exported {len(df)} records to {filepath}")
        return str(filepath)

    def load_to_duckdb(self, table_name: str = "records") -> None:
        """Load data into DuckDB for fast analytics queries."""
        df = self.to_dataframe()
        self.duckdb.execute(f"CREATE TABLE {table_name} AS SELECT * FROM df")
        logger.info(f"Loaded {len(df)} records into DuckDB table '{table_name}'")

    def query(self, sql: str, table_name: str = "records") -> pd.DataFrame:
        """Run a DuckDB query against the dataset."""
        result = self.duckdb.execute(sql).fetchdf()
        return result

    def get_insights(self) -> dict:
        """Generate comprehensive dataset insights."""
        self.load_to_duckdb()

        insights = {}

        # Total records
        insights["total_records"] = self.duckdb.execute("SELECT COUNT(*) FROM records").fetchone()[0]

        # Records by source
        insights["by_source"] = self.duckdb.execute(
            "SELECT source, COUNT(*) as count FROM records GROUP BY source ORDER BY count DESC"
        ).fetchall()

        # Records by license
        insights["by_license"] = self.duckdb.execute(
            "SELECT license, COUNT(*) as count FROM records WHERE license != '' GROUP BY license ORDER BY count DESC"
        ).fetchall()

        # Records by asset type
        insights["by_asset_type"] = self.duckdb.execute(
            "SELECT asset_type, COUNT(*) as count FROM records WHERE asset_type != '' GROUP BY asset_type ORDER BY count DESC"
        ).fetchall()

        # Top 10 most downloaded
        insights["top_downloaded"] = self.duckdb.execute(
            "SELECT title, source, download_count FROM records ORDER BY download_count DESC LIMIT 10"
        ).fetchall()

        # Average quality score by source
        insights["quality_by_source"] = self.duckdb.execute(
            "SELECT source, AVG(popularity_score) as avg_popularity FROM records GROUP BY source ORDER BY avg_popularity DESC"
        ).fetchall()

        # Popularity distribution
        insights["popularity_tiers"] = []  # Computed field, not in DB yet

        # CC0 (free) records
        insights["cc0_records"] = self.duckdb.execute(
            "SELECT COUNT(*) FROM records WHERE license = 'CC0'"
        ).fetchone()[0]

        # Records with geometry data
        insights["with_geometry"] = self.duckdb.execute(
            "SELECT COUNT(*) FROM records WHERE polycount > 0"
        ).fetchone()[0]

        # Records with high resolution (4K+)
        insights["high_resolution"] = self.duckdb.execute(
            "SELECT COUNT(*) FROM records WHERE max_resolution_w >= 4096"
        ).fetchone()[0]

        # Freshness by source
        insights["freshness"] = self.duckdb.execute(
            "SELECT source, MAX(scraped_at) as last_scraped FROM records GROUP BY source"
        ).fetchall()

        return insights

    def get_top_tags(self, limit: int = 20) -> list[tuple]:
        """Get most common tags across all sources."""
        df = self.to_dataframe()
        all_tags = []
        for tags in df["tags"].dropna():
            if isinstance(tags, list):
                all_tags.extend(tags)

        from collections import Counter
        tag_counts = Counter(all_tags)
        return tag_counts.most_common(limit)

    def get_popular_categories(self, limit: int = 20) -> list[tuple]:
        """Get most common categories across all sources."""
        df = self.to_dataframe()
        all_categories = []
        for cats in df["categories"].dropna():
            if isinstance(cats, list):
                all_categories.extend(cats)

        from collections import Counter
        cat_counts = Counter(all_categories)
        return cat_counts.most_common(limit)
