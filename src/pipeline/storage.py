"""
Storage Manager - Disk budget enforcement, space tracking, and tiered organization.

Manages the 50GB download budget, tracks usage per source, and enforces limits
before downloading. Organizes files in a structured directory layout.
"""

import logging
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class StorageConfig:
    """Storage configuration with budget limits."""
    base_path: Path = Path("data/assets")
    max_total_bytes: int = 50 * 1024 * 1024 * 1024  # 50GB default
    max_per_source_bytes: dict = field(default_factory=dict)
    preferred_formats: dict = field(default_factory=lambda: {
        "models": ["glb", "obj", "fbx"],
        "hdris": ["hdr"],
        "textures": ["png"],
    })
    max_resolution: str = "4k"  # 4k, 2k, 1k


@dataclass
class StorageStats:
    """Current storage statistics."""
    total_used_bytes: int = 0
    total_files: int = 0
    per_source_bytes: dict = field(default_factory=dict)
    per_source_files: dict = field(default_factory=dict)
    per_type_bytes: dict = field(default_factory=dict)


class StorageManager:
    """
    Manages disk storage with budget enforcement.

    Features:
    - Total disk budget cap (default 50GB)
    - Per-source limits
    - Real-time usage tracking
    - Smart file organization
    - Disk space verification before download
    """

    def __init__(self, config: Optional[StorageConfig] = None):
        self.config = config or StorageConfig()
        self.base_path = self.config.base_path
        self.base_path.mkdir(parents=True, exist_ok=True)
        logger.info(f"Storage manager initialized: {self.base_path}")
        logger.info(f"Budget: {self.config.max_total_bytes / (1024**3):.1f} GB")

    def get_source_dir(self, source: str, asset_type: str) -> Path:
        """Get the directory path for a source + asset type."""
        source_dir = self.base_path / source / asset_type
        source_dir.mkdir(parents=True, exist_ok=True)
        return source_dir

    def get_file_path(self, source: str, asset_type: str, filename: str) -> Path:
        """Get the full file path for a download."""
        return self.get_source_dir(source, asset_type) / filename

    def get_stats(self) -> StorageStats:
        """Scan disk and compute current storage statistics."""
        stats = StorageStats()

        if not self.base_path.exists():
            return stats

        # Walk through all files
        for file_path in self.base_path.rglob("*"):
            if file_path.is_file():
                size = file_path.stat().st_size
                stats.total_used_bytes += size
                stats.total_files += 1

                # Extract source and type from path
                rel_path = file_path.relative_to(self.base_path)
                parts = rel_path.parts
                if len(parts) >= 3:
                    source = parts[0]
                    asset_type = parts[1]
                    stats.per_source_bytes[source] = stats.per_source_bytes.get(source, 0) + size
                    stats.per_source_files[source] = stats.per_source_files.get(source, 0) + 1
                    stats.per_type_bytes[asset_type] = stats.per_type_bytes.get(asset_type, 0) + size

        return stats

    def check_budget(self, estimated_size_bytes: int, source: str = None) -> tuple[bool, str]:
        """
        Check if a download fits within budget.

        Returns:
            (allowed, reason) - True if download is allowed, False with reason if blocked.
        """
        stats = self.get_stats()

        # Check total budget
        remaining = self.config.max_total_bytes - stats.total_used_bytes
        if estimated_size_bytes > remaining:
            used_gb = stats.total_used_bytes / (1024**3)
            budget_gb = self.config.max_total_bytes / (1024**3)
            return False, (
                f"Total budget exceeded: {used_gb:.1f}/{budget_gb:.1f} GB used. "
                f"Need {estimated_size_bytes / (1024**2):.1f} MB, only {remaining / (1024**2):.1f} MB free."
            )

        # Check per-source budget
        if source and source in self.config.max_per_source_bytes:
            source_limit = self.config.max_per_source_bytes[source]
            source_used = stats.per_source_bytes.get(source, 0)
            if source_used + estimated_size_bytes > source_limit:
                return False, (
                    f"Source budget exceeded for {source}: "
                    f"{source_used / (1024**2):.1f}/{source_limit / (1024**2):.1f} MB"
                )

        return True, "OK"

    def format_size(self, size_bytes: int) -> str:
        """Format bytes to human-readable string."""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024**2:
            return f"{size_bytes / 1024:.1f} KB"
        elif size_bytes < 1024**3:
            return f"{size_bytes / (1024**2):.1f} MB"
        else:
            return f"{size_bytes / (1024**3):.3f} GB"

    def print_stats(self) -> None:
        """Print formatted storage statistics."""
        stats = self.get_stats()

        print(f"\n📦 Storage Statistics")
        print(f"{'='*50}")
        print(f"  Base path:    {self.base_path}")
        print(f"  Budget:       {self.format_size(self.config.max_total_bytes)}")
        print(f"  Used:         {self.format_size(stats.total_used_bytes)}")
        print(f"  Remaining:    {self.format_size(self.config.max_total_bytes - stats.total_used_bytes)}")
        print(f"  Files:        {stats.total_files}")
        print(f"  Usage:        {(stats.total_used_bytes / self.config.max_total_bytes * 100):.1f}%")

        if stats.per_source_bytes:
            print(f"\n  Per Source:")
            for source, size in sorted(stats.per_source_bytes.items()):
                files = stats.per_source_files.get(source, 0)
                print(f"    {source:15} {self.format_size(size):>10}  ({files} files)")

        if stats.per_type_bytes:
            print(f"\n  Per Type:")
            for atype, size in sorted(stats.per_type_bytes.items()):
                print(f"    {atype:15} {self.format_size(size):>10}")

    def estimate_download_size(self, source: str, asset_type: str,
                                metadata: dict) -> int:
        """
        Estimate download size from metadata.

        Poly Haven API provides file sizes in the asset metadata.
        Falls back to heuristics if size unknown.
        """
        # Try to get actual size from metadata
        if "file_size" in metadata:
            try:
                return int(metadata["file_size"])
            except (ValueError, TypeError):
                pass

        # Poly Haven specific: check files dict
        files = metadata.get("files", {})
        if files:
            total = 0
            for fmt, info in files.items():
                if isinstance(info, dict) and "size" in info:
                    total += info["size"]
            if total > 0:
                return total

        # Heuristic estimates by type
        heuristics = {
            "hdris": {
                "8k": 150 * 1024**2,   # 150 MB
                "4k": 50 * 1024**2,    # 50 MB
                "2k": 15 * 1024**2,    # 15 MB
            },
            "models": {
                "high": 50 * 1024**2,  # 50 MB
                "medium": 20 * 1024**2,
                "low": 5 * 1024**2,
            },
            "textures": {
                "4k": 80 * 1024**2,    # 80 MB
                "2k": 30 * 1024**2,
                "1k": 10 * 1024**2,
            },
        }

        defaults = heuristics.get(asset_type, {})
        if self.config.max_resolution in defaults:
            return defaults[self.config.max_resolution]

        # Default: 20 MB
        return 20 * 1024**2

    def cleanup_empty_dirs(self) -> int:
        """Remove empty directories. Returns count of removed dirs."""
        removed = 0
        for dir_path in sorted(self.base_path.rglob("*"), reverse=True):
            if dir_path.is_dir() and not any(dir_path.iterdir()):
                dir_path.rmdir()
                removed += 1
        return removed
