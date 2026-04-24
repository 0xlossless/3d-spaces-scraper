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
from src.pipeline.storage import StorageManager, StorageConfig
from src.pipeline.downloader import Downloader
from src.pipeline.manifest import Manifest


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


def cmd_download(args):
    """Download actual 3D assets."""
    config = load_config()
    dl_config = config.get("downloads", {})

    if not dl_config.get("enabled", False):
        print("❌ Downloads disabled in config.yaml")
        return

    # Setup storage manager
    storage = StorageConfig(
        base_path=Path(dl_config.get("base_path", "data/assets")),
        max_total_bytes=dl_config.get("max_total_gb", 50) * 1024**3,
        max_resolution=dl_config.get("max_resolution", "4k"),
    )
    manager = StorageManager(storage)
    downloader = Downloader(
        manager,
        rate_limit=dl_config.get("rate_limit", 2.0),
        max_retries=dl_config.get("max_retries", 3),
    )
    manifest = Manifest()
    db = Database(config["storage"]["database"])

    # Show current storage status
    manager.print_stats()

    # Get downloadable records
    source = args.source
    limit = args.limit
    downloadable = db.get_downloadable(source=source, limit=limit)

    if not downloadable:
        print(f"\n✅ No new downloads needed{' ' + f'for {source}' if source else ''}")
        db.close()
        return

    print(f"\n📥 Found {len(downloadable)} downloadable assets")

    # Build download list
    downloads = []
    for record in downloadable:
        asset_id = record.get("game_id", "")
        asset_type = record.get("asset_type", "models")
        source_name = record.get("source", "unknown")

        # Skip if already in manifest
        if manifest.is_downloaded(source_name, asset_id, asset_type):
            continue

        # Build download URL based on source
        url = _build_download_url(record, dl_config)
        if not url:
            continue

        # Determine filename and path
        filename = _build_filename(asset_id, asset_type, dl_config)
        file_path = manager.get_file_path(source_name, asset_type, filename)

        downloads.append({
            "url": url,
            "path": str(file_path),
            "hash": record.get("files_hash", ""),
            "record": record,
        })

    if not downloads:
        print("✅ All assets already downloaded")
        db.close()
        return

    # Show what will be downloaded
    print(f"\n📋 Download queue: {len(downloads)} files")
    for dl in downloads[:5]:
        print(f"  - {Path(dl['path']).name}")
    if len(downloads) > 5:
        print(f"  ... and {len(downloads) - 5} more")

    # Confirm
    if not args.yes:
        response = input(f"\nDownload {len(downloads)} files? [y/N]: ")
        if response.lower() not in ("y", "yes"):
            print("Cancelled.")
            db.close()
            return

    # Execute downloads
    print(f"\n{'='*50}")
    print(f"Starting downloads...")
    print(f"{'='*50}")

    results = downloader.download_batch(downloads, source or "mixed")

    # Update database and manifest
    success = 0
    failed = 0
    for result in results:
        if "error" not in result:
            record = None
            for dl in downloads:
                if dl["path"] == result["path"]:
                    record = dl["record"]
                    break

            if record:
                db.update_download_status(
                    record_id=record["id"],
                    file_path=result["path"],
                    file_size=result["size"],
                    file_hash=result.get("hash", ""),
                    status="completed",
                )
                manifest.mark_downloaded(
                    source=record["source"],
                    asset_id=record["game_id"],
                    asset_type=record["asset_type"],
                    file_path=result["path"],
                    file_size=result["size"],
                    file_hash=result.get("hash", ""),
                    url=dl["url"],
                )
                success += 1
        else:
            failed += 1

    # Print summary
    print(f"\n{'='*50}")
    print(f"Download Complete")
    print(f"{'='*50}")
    print(f"  ✅ Success: {success}")
    print(f"  ❌ Failed:  {failed}")
    manager.print_stats()
    manifest.print_stats()

    db.close()


def cmd_storage(args):
    """Show storage statistics."""
    config = load_config()
    dl_config = config.get("downloads", {})

    storage = StorageConfig(
        base_path=Path(dl_config.get("base_path", "data/assets")),
        max_total_bytes=dl_config.get("max_total_gb", 50) * 1024**3,
    )
    manager = StorageManager(storage)
    manifest = Manifest()

    manager.print_stats()
    manifest.print_stats()


def cmd_verify(args):
    """Verify downloaded file integrity."""
    manifest = Manifest()
    issues = manifest.verify_integrity()

    if issues:
        print(f"\n❌ Found {len(issues)} integrity issues:")
        for issue in issues:
            print(f"  - {issue['key']}: {issue['issue']}")
            print(f"    Path: {issue.get('path', 'N/A')}")
    else:
        print("\n✅ All downloaded files verified OK")


def _build_download_url(record: dict, dl_config: dict) -> str:
    """Build download URL from record metadata.

    Poly Haven CDN patterns:
    - HDRIs:  dl.polyhaven.org/file/ph-assets/HDRIs/hdr/{res}/{id}_{res}.hdr
    - Models: dl.polyhaven.org/file/ph-assets/Models/{fmt}/{res}/{id}/{id}_{res}.{fmt}
    - Textures: dl.polyhaven.org/file/ph-assets/Textures/png/{res}/{id}/{id}_diff_{res}.png
    """
    source = record.get("source", "")
    asset_id = record.get("game_id", "")
    asset_type = record.get("asset_type", "models")

    if source == "polyhaven":
        resolution = dl_config.get("max_resolution", "4k")

        if asset_type == "hdris":
            return f"https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/{resolution}/{asset_id}_{resolution}.hdr"
        elif asset_type == "models":
            # Models come as blend/fbx/gltf/usd - use blend as default (smallest, most compatible)
            fmt = dl_config.get("preferred_formats", {}).get("models", ["blend"])[0]
            return f"https://dl.polyhaven.org/file/ph-assets/Models/{fmt}/{resolution}/{asset_id}/{asset_id}_{resolution}.{fmt}"
        elif asset_type == "textures":
            # Textures come as individual maps (diffuse, normal, etc.) in png/jpg/exr
            # Download diffuse map as representative
            fmt = dl_config.get("preferred_formats", {}).get("textures", ["png"])[0]
            return f"https://dl.polyhaven.org/file/ph-assets/Textures/{fmt}/{resolution}/{asset_id}/{asset_id}_diff_{resolution}.{fmt}"

    return ""


def _build_filename(asset_id: str, asset_type: str, dl_config: dict) -> str:
    """Build standardized filename."""
    resolution = dl_config.get("max_resolution", "4k")

    if asset_type == "hdris":
        return f"{asset_id}_{resolution}.hdr"
    elif asset_type == "models":
        fmt = dl_config.get("preferred_formats", {}).get("models", ["blend"])[0]
        return f"{asset_id}_{resolution}.{fmt}"
    elif asset_type == "textures":
        fmt = dl_config.get("preferred_formats", {}).get("textures", ["png"])[0]
        return f"{asset_id}_diff_{resolution}.{fmt}"
    return f"{asset_id}.zip"


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

    # download command
    download_parser = subparsers.add_parser("download", help="Download 3D assets")
    download_parser.add_argument("--source", type=str,
                                 help="Only download from specific source")
    download_parser.add_argument("--limit", type=int,
                                 help="Limit number of downloads")
    download_parser.add_argument("--yes", "-y", action="store_true",
                                 help="Skip confirmation prompt")

    # storage command
    subparsers.add_parser("storage", help="Show storage statistics")

    # verify command
    subparsers.add_parser("verify", help="Verify downloaded file integrity")

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
    elif args.command == "download":
        cmd_download(args)
    elif args.command == "storage":
        cmd_storage(args)
    elif args.command == "verify":
        cmd_verify(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
