"""
Export utilities for the 3D Spaces Dataset.
Supports CSV and JSON export formats.
"""

import csv
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def export_csv(db_path: str = "data/3d_spaces.db", output: str = "data/export.csv"):
    """Export all records to CSV."""
    import sqlite3

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("SELECT * FROM records ORDER BY source, title").fetchall()
    conn.close()

    if not rows:
        logger.warning("No records to export")
        return

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = list(rows[0].keys())

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            # Convert tags JSON string to pipe-separated for CSV readability
            record = dict(row)
            if record.get("tags"):
                try:
                    tags = json.loads(record["tags"])
                    record["tags"] = " | ".join(tags) if isinstance(tags, list) else record["tags"]
                except json.JSONDecodeError:
                    pass
            writer.writerow(record)

    logger.info(f"Exported {len(rows)} records to {output_path}")


def export_json(db_path: str = "data/3d_spaces.db", output: str = "data/export.json"):
    """Export all records to JSON."""
    import sqlite3

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    rows = conn.execute("SELECT * FROM records ORDER BY source, title").fetchall()
    conn.close()

    if not rows:
        logger.warning("No records to export")
        return

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    records = []
    for row in rows:
        record = dict(row)
        # Parse tags JSON string back to list
        if record.get("tags"):
            try:
                record["tags"] = json.loads(record["tags"])
            except json.JSONDecodeError:
                pass
        records.append(record)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, ensure_ascii=False)

    logger.info(f"Exported {len(records)} records to {output_path}")


def print_stats(db_path: str = "data/3d_spaces.db"):
    """Print database statistics."""
    import sqlite3

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    total = conn.execute("SELECT COUNT(*) as c FROM records").fetchone()["c"]
    print(f"\n📊 3D Spaces Dataset Statistics")
    print(f"   Total records: {total}")

    print("\n   By source:")
    for row in conn.execute("SELECT source, COUNT(*) as c FROM records GROUP BY source ORDER BY c DESC").fetchall():
        print(f"     {row['source']}: {row['c']}")

    print("\n   By platform (top 10):")
    for row in conn.execute("SELECT platform, COUNT(*) as c FROM records GROUP BY platform ORDER BY c DESC LIMIT 10").fetchall():
        print(f"     {row['platform']}: {row['c']}")

    print("\n   By genre (top 10):")
    for row in conn.execute("SELECT genre, COUNT(*) as c FROM records WHERE genre != '' GROUP BY genre ORDER BY c DESC LIMIT 10").fetchall():
        print(f"     {row['genre']}: {row['c']}")

    conn.close()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m src.utils.export [stats|csv|json]")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "stats":
        print_stats()
    elif cmd == "csv":
        export_csv()
    elif cmd == "json":
        export_json()
    else:
        print(f"Unknown command: {cmd}")
