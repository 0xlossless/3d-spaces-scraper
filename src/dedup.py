"""
Cross-Source Deduplication.
Fuzzy matching to detect duplicate assets across different sources.
"""

import logging
from typing import Optional

from rapidfuzz import fuzz, process

logger = logging.getLogger(__name__)


class DeduplicationEngine:
    """Detects duplicate assets across sources using fuzzy matching."""

    def __init__(self, threshold: float = 85.0):
        """
        Args:
            threshold: Similarity threshold (0-100). Default 85.
        """
        self.threshold = threshold

    def normalize_title(self, title: str) -> str:
        """Normalize title for comparison."""
        # Lowercase, remove extra spaces, strip
        normalized = title.lower().strip()
        # Remove common suffixes
        for suffix in [" 3d model", " 3d", " model", " asset", " pack", " set"]:
            if normalized.endswith(suffix):
                normalized = normalized[:-len(suffix)].strip()
        return normalized

    def find_duplicates(self, records: list[dict], source: str) -> list[dict]:
        """
        Find potential duplicates of new records against existing database.

        Args:
            records: New records to check
            source: Source of new records

        Returns:
            List of {new_record, existing_record, similarity} matches
        """
        duplicates = []

        # Get existing records from other sources
        existing = []
        for row in records:
            existing.append({
                "title": self.normalize_title(row.get("title", "")),
                "original": row,
            })

        # Compare new records against existing
        for new_rec in records:
            new_title = self.normalize_title(new_rec.get("title", ""))
            if not new_title:
                continue

            # Find best match in existing
            titles = [r["title"] for r in existing if r["original"] != new_rec]
            if not titles:
                continue

            best_match = process.extractOne(
                new_title,
                titles,
                scorer=fuzz.token_sort_ratio,
            )

            if best_match and best_match[1] >= self.threshold:
                # Find the matching record
                for existing_rec in existing:
                    if existing_rec["title"] == best_match[0]:
                        duplicates.append({
                            "new_record": new_rec,
                            "existing_record": existing_rec["original"],
                            "similarity": best_match[1],
                            "new_title": new_rec.get("title", ""),
                            "existing_title": existing_rec["original"].get("title", ""),
                        })
                        break

        return duplicates

    def find_cross_source_duplicates(self, db, threshold: Optional[float] = None) -> list[dict]:
        """
        Find duplicates across different sources in the database.

        Args:
            db: Database instance
            threshold: Override similarity threshold

        Returns:
            List of duplicate pairs
        """
        threshold = threshold or self.threshold
        duplicates = []

        # Get all records grouped by normalized title
        all_records = []
        for row in db.conn.execute("SELECT * FROM records"):
            record = dict(row)
            title = self.normalize_title(record.get("title", ""))
            if title:
                all_records.append({
                    "title": title,
                    "original": record,
                })

        # Group by source
        sources = {}
        for rec in all_records:
            source = rec["original"].get("source", "")
            if source not in sources:
                sources[source] = []
            sources[source].append(rec)

        # Compare across sources
        source_list = list(sources.keys())
        for i in range(len(source_list)):
            for j in range(i + 1, len(source_list)):
                source_a = source_list[i]
                source_b = source_list[j]

                titles_b = [r["title"] for r in sources[source_b]]
                if not titles_b:
                    continue

                for rec_a in sources[source_a]:
                    best_match = process.extractOne(
                        rec_a["title"],
                        titles_b,
                        scorer=fuzz.token_sort_ratio,
                    )

                    if best_match and best_match[1] >= threshold:
                        # Find the matching record
                        for rec_b in sources[source_b]:
                            if rec_b["title"] == best_match[0]:
                                duplicates.append({
                                    "record_a": rec_a["original"],
                                    "record_b": rec_b["original"],
                                    "similarity": best_match[1],
                                    "title_a": rec_a["original"].get("title", ""),
                                    "title_b": rec_b["original"].get("title", ""),
                                })
                                break

        return duplicates

    def merge_duplicates(self, duplicates: list[dict]) -> list[dict]:
        """
        Merge duplicate records by keeping the one with richer metadata.

        Args:
            duplicates: List of duplicate pairs

        Returns:
            List of merged records
        """
        merged = []

        for dup in duplicates:
            rec_a = dup["record_a"]
            rec_b = dup["record_b"]

            # Score each record by metadata richness
            score_a = self._score_richness(rec_a)
            score_b = self._score_richness(rec_b)

            # Keep the richer one
            winner = rec_a if score_a >= score_b else rec_b

            # Merge tags/categories from both
            if rec_a.get("tags") and rec_b.get("tags"):
                winner["tags"] = list(set(rec_a["tags"] + rec_b["tags"]))[:20]

            if rec_a.get("categories") and rec_b.get("categories"):
                winner["categories"] = list(set(rec_a["categories"] + rec_b["categories"]))

            merged.append({
                "winner": winner,
                "loser": rec_b if score_a >= score_b else rec_a,
                "similarity": dup["similarity"],
            })

        return merged

    def _score_richness(self, record: dict) -> int:
        """Score a record by how much metadata it has."""
        score = 0
        for field in [
            "description", "tags", "categories", "authors", "license",
            "download_count", "view_count", "polycount", "file_formats",
            "release_date", "created_at", "file_size", "engine_detected",
        ]:
            val = record.get(field, "")
            if val and val != "[]" and val != 0 and val != 0.0:
                score += 1
        return score
