#!/usr/bin/env python3
"""
CLI entry point for the 3D Spaces Dataset Scraper.

Usage:
    python -m src.cli run [--incremental] [--source NAME]
    python -m src.cli export [--format csv|json] [--output FILE]
    python -m src.cli stats
    python -m src.cli clean [--cache] [--db]
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
    """Export data to CSV or JSON."""
    config = load_config()
    db_path = config["storage"]["database"]

    if args.format == "csv":
        output = args.output or "data/export.csv"
        export_csv(db_path, output)
        print(f"Exported to {output}")
    elif args.format == "json":
        output = args.output or "data/export.json"
        export_json(db_path, output)
        print(f"Exported to {output}")


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
    export_parser.add_argument("--format", choices=["csv", "json"], default="csv",
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

    args = parser.parse_args()

    if args.command == "run":
        cmd_run(args)
    elif args.command == "export":
        cmd_export(args)
    elif args.command == "stats":
        cmd_stats(args)
    elif args.command == "clean":
        cmd_clean(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
