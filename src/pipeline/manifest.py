"""
Manifest Tracker - Track downloaded vs cataloged assets.

Maintains a manifest.json that records:
- What's been downloaded
- Download timestamps
- File hashes for integrity verification
- Source metadata for re-downloading
"""

import json
import logging
from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


class Manifest:
    """
    Tracks downloaded assets and their metadata.

    Stores a manifest.json alongside the asset directory with:
    - Download status per asset
    - File hashes for verification
    - Source URLs for re-downloading
    - Timestamps and sizes
    """

    def __init__(self, manifest_path: Path = Path("data/assets/manifest.json")):
        self.manifest_path = manifest_path
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.data = self._load()

    def _load(self) -> dict:
        """Load manifest from disk."""
        if self.manifest_path.exists():
            try:
                with open(self.manifest_path) as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load manifest: {e}, starting fresh")
                return {"version": 1, "assets": {}}
        return {"version": 1, "assets": {}}

    def _save(self) -> None:
        """Save manifest to disk."""
        with open(self.manifest_path, "w") as f:
            json.dump(self.data, f, indent=2, default=str)

    def get_key(self, source: str, asset_id: str, asset_type: str) -> str:
        """Generate unique key for an asset."""
        return f"{source}:{asset_type}:{asset_id}"

    def is_downloaded(self, source: str, asset_id: str, asset_type: str) -> bool:
        """Check if an asset has been downloaded."""
        key = self.get_key(source, asset_id, asset_type)
        asset = self.data["assets"].get(key, {})
        return asset.get("status") == "completed"

    def mark_downloaded(self, source: str, asset_id: str, asset_type: str,
                        file_path: str, file_size: int, file_hash: str,
                        url: str = "") -> None:
        """Mark an asset as successfully downloaded."""
        key = self.get_key(source, asset_id, asset_type)
        self.data["assets"][key] = {
            "source": source,
            "asset_id": asset_id,
            "asset_type": asset_type,
            "status": "completed",
            "file_path": file_path,
            "file_size": file_size,
            "file_hash": file_hash,
            "download_url": url,
            "downloaded_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save()

    def mark_failed(self, source: str, asset_id: str, asset_type: str,
                    error: str) -> None:
        """Mark an asset as failed."""
        key = self.get_key(source, asset_id, asset_type)
        self.data["assets"][key] = {
            "source": source,
            "asset_id": asset_id,
            "asset_type": asset_type,
            "status": "failed",
            "error": error,
            "failed_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save()

    def get_downloadable(self, catalog: list[dict], source: str) -> list[dict]:
        """
        Filter catalog to only assets not yet downloaded.

        Args:
            catalog: List of asset metadata dicts
            source: Source name

        Returns:
            List of assets that need downloading
        """
        downloadable = []
        for asset in catalog:
            asset_id = asset.get("game_id", "")
            asset_type = asset.get("asset_type", "models")
            if not self.is_downloaded(source, asset_id, asset_type):
                downloadable.append(asset)
        return downloadable

    def get_stats(self) -> dict:
        """Get manifest statistics."""
        assets = self.data.get("assets", {})
        status_counts = {}
        source_counts = {}

        for key, info in assets.items():
            status = info.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1

            source = info.get("source", "unknown")
            source_counts[source] = source_counts.get(source, 0) + 1

        return {
            "total": len(assets),
            "by_status": status_counts,
            "by_source": source_counts,
        }

    def print_stats(self) -> None:
        """Print manifest statistics."""
        stats = self.get_stats()

        print(f"\n📋 Download Manifest")
        print(f"{'='*40}")
        print(f"  Total tracked: {stats['total']}")

        if stats["by_status"]:
            print(f"\n  By Status:")
            for status, count in sorted(stats["by_status"].items()):
                icon = {"completed": "✅", "failed": "❌", "pending": "⏳"}.get(status, "❓")
                print(f"    {icon} {status:12} {count}")

        if stats["by_source"]:
            print(f"\n  By Source:")
            for source, count in sorted(stats["by_source"].items()):
                print(f"    {source:15} {count}")

    def verify_integrity(self) -> list[dict]:
        """
        Verify all downloaded files match their recorded hashes.

        Returns:
            List of issues found
        """
        issues = []
        for key, info in self.data.get("assets", {}).items():
            if info.get("status") != "completed":
                continue

            file_path = info.get("file_path", "")
            expected_hash = info.get("file_hash", "")

            if not file_path or not expected_hash:
                continue

            path = Path(file_path)
            if not path.exists():
                issues.append({
                    "key": key,
                    "issue": "missing_file",
                    "path": file_path,
                })
                continue

            # Verify hash
            import hashlib
            sha256 = hashlib.sha256()
            with open(path, "rb") as f:
                for chunk in iter(lambda: f.read(8192 * 1024), b""):
                    sha256.update(chunk)

            if sha256.hexdigest() != expected_hash:
                issues.append({
                    "key": key,
                    "issue": "hash_mismatch",
                    "expected": expected_hash,
                    "actual": sha256.hexdigest(),
                    "path": file_path,
                })

        return issues
