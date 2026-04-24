"""
Data Quality Pipeline.
Validates records, detects anomalies, computes quality metrics.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from src.models import DataQualityReport, Record

logger = logging.getLogger(__name__)


class DataQualityPipeline:
    """Validates and scores data quality for scraped records."""

    def __init__(self, db):
        self.db = db

    def validate_record(self, record: dict) -> tuple[bool, list[str]]:
        """Validate a single record. Returns (is_valid, errors)."""
        errors = []

        # Required fields
        if not record.get("source"):
            errors.append("Missing 'source'")
        if not record.get("title"):
            errors.append("Missing 'title'")
        if not record.get("link"):
            errors.append("Missing 'link'")
        elif not record["link"].startswith(("http://", "https://")):
            errors.append("Invalid URL format")

        # Numeric fields must be non-negative
        for field in ["download_count", "view_count", "like_count", "polycount"]:
            val = record.get(field, 0)
            if isinstance(val, (int, float)) and val < 0:
                errors.append(f"Negative {field}: {val}")

        # Rating must be 0-5
        rating = record.get("rating", 0.0)
        if isinstance(rating, (int, float)) and not (0 <= rating <= 5):
            errors.append(f"Rating out of range: {rating}")

        # Tags must be list
        tags = record.get("tags", [])
        if not isinstance(tags, list):
            errors.append(f"Tags must be list, got {type(tags).__name__}")

        return len(errors) == 0, errors

    def detect_anomalies(self, source: str) -> list[dict]:
        """Detect data anomalies for a source."""
        anomalies = []

        # Records with extremely high download counts (potential outliers)
        high_dl = self.db.conn.execute(
            "SELECT id, title, download_count FROM records "
            "WHERE source = ? AND download_count > 100000",
            (source,),
        ).fetchall()
        for row in high_dl:
            anomalies.append({
                "type": "extreme_downloads",
                "id": row[0],
                "title": row[1],
                "value": row[2],
                "message": f"Unusually high download count: {row[2]}",
            })

        # Records with missing titles
        missing_title = self.db.conn.execute(
            "SELECT COUNT(*) FROM records WHERE source = ? AND (title = '' OR title IS NULL)",
            (source,),
        ).fetchone()[0]
        if missing_title > 0:
            anomalies.append({
                "type": "missing_titles",
                "count": missing_title,
                "message": f"{missing_title} records have empty titles",
            })

        # Records with future dates
        now = datetime.now(timezone.utc).isoformat()
        future_dates = self.db.conn.execute(
            "SELECT COUNT(*) FROM records WHERE source = ? AND created_at > ?",
            (source, now),
        ).fetchone()[0]
        if future_dates > 0:
            anomalies.append({
                "type": "future_dates",
                "count": future_dates,
                "message": f"{future_dates} records have future timestamps",
            })

        return anomalies

    def generate_report(self, source: str) -> DataQualityReport:
        """Generate a comprehensive quality report for a source."""
        total = self.db.conn.execute(
            "SELECT COUNT(*) FROM records WHERE source = ?", (source,)
        ).fetchone()[0]

        report = DataQualityReport(
            source=source,
            total_records=total,
        )

        if total == 0:
            return report

        # License coverage
        report.records_with_license = self.db.conn.execute(
            "SELECT COUNT(*) FROM records WHERE source = ? AND license != ''",
            (source,),
        ).fetchone()[0]

        # Download data coverage
        report.records_with_downloads = self.db.conn.execute(
            "SELECT COUNT(*) FROM records WHERE source = ? AND download_count > 0",
            (source,),
        ).fetchone()[0]

        # Geometry data coverage
        report.records_with_geometry = self.db.conn.execute(
            "SELECT COUNT(*) FROM records WHERE source = ? AND polycount > 0",
            (source,),
        ).fetchone()[0]

        # Author coverage
        report.records_with_author = self.db.conn.execute(
            "SELECT COUNT(*) FROM records WHERE source = ? AND (author != '' OR authors != '[]')",
            (source,),
        ).fetchone()[0]

        # Timestamp coverage
        report.records_with_timestamp = self.db.conn.execute(
            "SELECT COUNT(*) FROM records WHERE source = ? AND (created_at != '' OR release_date != '')",
            (source,),
        ).fetchone()[0]

        # Tags coverage
        report.records_with_tags = self.db.conn.execute(
            "SELECT COUNT(*) FROM records WHERE source = ? AND tags != '[]' AND tags != ''",
            (source,),
        ).fetchone()[0]

        # Average quality score
        avg_quality = self.db.conn.execute(
            "SELECT AVG(popularity_score) FROM records WHERE source = ?", (source,)
        ).fetchone()[0] or 0.0
        report.avg_quality_score = round(avg_quality, 2)

        # Average download count
        avg_dl = self.db.conn.execute(
            "SELECT AVG(download_count) FROM records WHERE source = ? AND download_count > 0",
            (source,),
        ).fetchone()[0] or 0.0
        report.avg_download_count = round(avg_dl, 2)

        # Freshness (days since last scrape)
        last_scraped = self.db.conn.execute(
            "SELECT MAX(scraped_at) FROM records WHERE source = ?", (source,)
        ).fetchone()[0]
        if last_scraped:
            try:
                last_dt = datetime.fromisoformat(last_scraped)
                now = datetime.now(timezone.utc)
                report.freshness_days = round((now - last_dt).total_seconds() / 86400, 1)
            except (ValueError, TypeError):
                pass

        return report

    def validate_all(self, source: Optional[str] = None) -> dict:
        """Validate all records for a source (or all sources)."""
        results = {
            "total": 0,
            "valid": 0,
            "invalid": 0,
            "errors": [],
        }

        query = "SELECT * FROM records"
        params = ()
        if source:
            query += " WHERE source = ?"
            params = (source,)

        for row in self.db.conn.execute(query, params):
            record = dict(row)
            results["total"] += 1

            is_valid, errors = self.validate_record(record)
            if is_valid:
                results["valid"] += 1
            else:
                results["invalid"] += 1
                results["errors"].append({
                    "id": record.get("id", "unknown"),
                    "title": record.get("title", "unknown")[:50],
                    "errors": errors,
                })

        return results
