#!/usr/bin/env python3
"""
CLI entry point for the 3D Spaces Dataset Scraper.

Usage:
    python -m src.cli run [--incremental] [--source NAME]
    python -m src.cli export [--format csv|json|parquet] [--output FILE]
    python -m src.cli stats
    python -m src.cli clean [--cache] [--db]
    python -m src.cli quality [--source NAME]
    python -m src.cli insights
    python -m src.cli dedup [--threshold 85]
    python -m src.cli dashboard
"""

import argparse
import sys
from pathlib import Path

# Ensure project root is in path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.scraper import load_config, run_scraper
from src.utils.export import export_csv, export_json, print_stats
from src.http_cache import clear_cache
from src.storage.database import Database
from src.quality import DataQualityPipeline
from src.analytics import AnalyticsEngine
from src.dedup import DeduplicationEngine
from src.dashboard import Dashboard


def cmd_run(args):
    """Run the scraper."""
    config = load_config()

    if args.source:
        # Filter to specific source
        config["sources"] = [
            s for s in config["sources"] if s["name"].lower() == args.source.lower()
        ]
        if not config["sources"]:
            print(f"Error: Source '{args.source}' not found in config")
            sys.exit(1)

    summary = run_scraper(config, incremental=args.incremental)

    print(f"\n{'='*60}")
    print(f"Scraper Complete")
    print(f"{'='*60}")
    for s in summary["sources"]:
        status = "✅" if s["new"] > 0 else "⏭️"
        print(f"  {status} {s['source']}: {s['total']} records (new={s['new']}, skipped={s['skipped']})")
    print(f"\n  Total new: {summary['total_new']}")
    print(f"  Total skipped: {summary['total_skipped']}")


def cmd_export(args):
    """Export data to CSV, JSON, or Parquet."""
    config = load_config()
    db_path = config["storage"]["database"]
    db = Database(db_path)
    analytics = AnalyticsEngine(db)

    if args.format == "csv":
        output = args.output or "data/export.csv"
        export_csv(db_path, output)
        print(f"Exported to {output}")
    elif args.format == "json":
        output = args.output or "data/export.json"
        export_json(db_path, output)
        print(f"Exported to {output}")
    elif args.format == "parquet":
        output = analytics.export_parquet()
        print(f"Exported to {output}")
    else:
        print(f"Unknown format: {args.format}")
        sys.exit(1)

    db.close()


def cmd_stats(args):
    """Print database statistics."""
    config = load_config()
    db_path = config["storage"]["database"]
    print_stats(db_path)


def cmd_clean(args):
    """Clean cache and/or database."""
    if args.cache:
        clear_cache()
        print("HTTP cache cleared")

    if args.db:
        db_path = Path("data/3d_spaces.db")
        if db_path.exists():
            db_path.unlink()
            print("Database deleted")
        else:
            print("No database found")

    if not args.cache and not args.db:
        # Default: clear both
        clear_cache()
        db_path = Path("data/3d_spaces.db")
        if db_path.exists():
            db_path.unlink()
        print("Cache and database cleared")


def cmd_quality(args):
    """Run data quality checks."""
    config = load_config()
    db_path = config["storage"]["database"]
    db = Database(db_path)
    quality = DataQualityPipeline(db)

    if args.source:
        report = quality.generate_report(args.source)
        print(f"\n🔍 Quality Report: {args.source}")
        print(f"  Total Records: {report.total_records}")
        print(f"  With License: {report.records_with_license}")
        print(f"  With Downloads: {report.records_with_downloads}")
        print(f"  With Geometry: {report.records_with_geometry}")
        print(f"  With Author: {report.records_with_author}")
        print(f"  Avg Quality Score: {report.avg_quality_score}")
        print(f"  Avg Downloads: {report.avg_download_count}")
        print(f"  Freshness: {report.freshness_days} days")

        anomalies = quality.detect_anomalies(args.source)
        if anomalies:
            print(f"\n⚠️  Anomalies ({len(anomalies)}):")
            for a in anomalies:
                print(f"  - {a.get('type', 'unknown')}: {a.get('message', '')}")
    else:
        # All sources
        for source in db.count_by_source():
            report = quality.generate_report(source)
            print(f"\n🔍 {source}:")
            print(f"  Records: {report.total_records}")
            print(f"  Quality: {report.avg_quality_score}")
            print(f"  Freshness: {report.freshness_days} days")

    db.close()


def cmd_insights(args):
    """Show dataset insights."""
    config = load_config()
    db_path = config["storage"]["database"]
    db = Database(db_path)
    analytics = AnalyticsEngine(db)

    insights = analytics.get_insights()

    print(f"\n🧠 Dataset Insights")
    print(f"{'='*40}")
    print(f"Total Records: {insights['total_records']}")
    print(f"CC0 (Free) Records: {insights['cc0_records']}")
    print(f"With Geometry Data: {insights['with_geometry']}")
    print(f"High Resolution (4K+): {insights['high_resolution']}")

    print(f"\n📈 By Source:")
    for source, count in insights["by_source"]:
        print(f"  {source}: {count}")

    print(f"\n📜 By License:")
    for license_type, count in insights["by_license"]:
        print(f"  {license_type}: {count}")

    print(f"\n🎮 By Asset Type:")
    for asset_type, count in insights["by_asset_type"]:
        print(f"  {asset_type}: {count}")

    print(f"\n🏆 Top 10 Most Downloaded:")
    for title, source, downloads in insights["top_downloaded"][:10]:
        print(f"  {title[:40]} ({source}): {downloads:,}")

    db.close()


def cmd_dedup(args):
    """Run cross-source deduplication."""
    config = load_config()
    db_path = config["storage"]["database"]
    db = Database(db_path)
    dedup = DeduplicationEngine(threshold=args.threshold)

    print(f"\n🔍 Running cross-source deduplication (threshold: {args.threshold}%)...")
    duplicates = dedup.find_cross_source_duplicates(db, threshold=args.threshold)

    if duplicates:
        print(f"\nFound {len(duplicates)} potential duplicates:")
        for i, dup in enumerate(duplicates[:20]):  # Show first 20
            print(f"\n  [{i+1}] Similarity: {dup['similarity']:.1f}%")
            print(f"    A: {dup['title_a'][:50]} ({dup['record_a']['source']})")
            print(f"    B: {dup['title_b'][:50]} ({dup['record_b']['source']})")

        if len(duplicates) > 20:
            print(f"\n  ... and {len(duplicates) - 20} more")
    else:
        print("No duplicates found.")

    db.close()


def cmd_dashboard(args):
    """Show rich monitoring dashboard."""
    config = load_config()
    db_path = config["storage"]["database"]
    db = Database(db_path)
    quality = DataQualityPipeline(db)
    analytics = AnalyticsEngine(db)
    dashboard = Dashboard(db, quality, analytics)

    dashboard.show_overview()
    dashboard.show_freshness_alerts()
    dashboard.show_insights()

    db.close()


def main():
    parser = argparse.ArgumentParser(
        description="3D Spaces Dataset Scraper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # run command
    run_parser = subparsers.add_parser("run", help="Run the scraper")
    run_parser.add_argument("--incremental", action="store_true",
                           help="Only fetch new content since last run")
    run_parser.add_argument("--source", type=str,
                           help="Only scrape specific source (e.g. 'itch.io')")

    # export command
    export_parser = subparsers.add_parser("export", help="Export data")
    export_parser.add_argument("--format", choices=["csv", "json", "parquet"], default="csv",
                              help="Export format (default: csv)")
    export_parser.add_argument("--output", type=str,
                              help="Output file path")

    # stats command
    subparsers.add_parser("stats", help="Print database statistics")

    # clean command
    clean_parser = subparsers.add_parser("clean", help="Clean cache and/or database")
    clean_parser.add_argument("--cache", action="store_true",
                             help="Only clear HTTP cache")
    clean_parser.add_argument("--db", action="store_true",
                             help="Only delete database")

    # quality command
    quality_parser = subparsers.add_parser("quality", help="Run data quality checks")
    quality_parser.add_argument("--source", type=str,
                               help="Check specific source")

    # insights command
    subparsers.add_parser("insights", help="Show dataset insights")

    # dedup command
    dedup_parser = subparsers.add_parser("dedup", help="Run cross-source deduplication")
    dedup_parser.add_argument("--threshold", type=float, default=85.0,
                             help="Similarity threshold (default: 85.0)")

    # dashboard command
    subparsers.add_parser("dashboard", help="Show rich monitoring dashboard")

    args = parser.parse_args()

    if args.command == "run":
        cmd_run(args)
    elif args.command == "export":
        cmd_export(args)
    elif args.command == "stats":
        cmd_stats(args)
    elif args.command == "clean":
        cmd_clean(args)
    elif args.command == "quality":
        cmd_quality(args)
    elif args.command == "insights":
        cmd_insights(args)
    elif args.command == "dedup":
        cmd_dedup(args)
    elif args.command == "dashboard":
        cmd_dashboard(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
