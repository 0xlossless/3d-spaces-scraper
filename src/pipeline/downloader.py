"""
Downloader - Resumable downloads with progress tracking, rate limiting, and integrity verification.

Handles large 3D asset downloads (50MB-2GB) with:
- Resumable transfers (HTTP Range requests)
- Real-time progress reporting
- SHA256 hash verification
- Rate limiting per source
- Retry logic with exponential backoff
"""

import hashlib
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable

import requests

logger = logging.getLogger(__name__)


class DownloadError(Exception):
    """Raised when a download fails."""
    pass


@dataclass
class DownloadResult:
    path: str
    size: int
    hash_ok: bool
    skipped: bool = False
    hash: str = ""
    error: str = ""


class Downloader:
    """
    Production-grade file downloader with resume support.

    Features:
    - Resumable downloads via HTTP Range headers
    - SHA256 integrity verification
    - Configurable rate limiting
    - Retry with exponential backoff
    - Progress callbacks
    - Temp file → atomic move pattern
    """

    def __init__(self, storage_manager, rate_limit: float = 2.0,
                 max_retries: int = 3, chunk_size: int = 8 * 1024 * 1024):
        """
        Args:
            storage_manager: StorageManager instance for budget checks
            rate_limit: Seconds between requests (per source)
            max_retries: Max retry attempts on failure
            chunk_size: Download chunk size (default 8MB)
        """
        self.storage = storage_manager
        self.rate_limit = rate_limit
        self.max_retries = max_retries
        self.chunk_size = chunk_size
        self._last_request_time: dict[str, float] = {}

    def _rate_limit(self, source: str) -> None:
        """Enforce rate limiting per source."""
        now = time.time()
        last = self._last_request_time.get(source, 0)
        wait = self.rate_limit - (now - last)
        if wait > 0:
            time.sleep(wait)
        self._last_request_time[source] = time.time()

    def download(self, url: str, dest_path: Path, source: str = "",
                 expected_hash: str = None, progress_callback: Callable = None) -> dict:
        """
        Download a file with resume support and integrity verification.

        Args:
            url: Download URL
            dest_path: Destination file path
            source: Source name for rate limiting
            expected_hash: Expected SHA256 hash for verification
            progress_callback: Callable(current_bytes, total_bytes) for progress

        Returns:
            dict with keys: path, size, hash_ok, skipped
        """
        # Check if already downloaded
        if dest_path.exists():
            file_size = dest_path.stat().st_size
            if file_size > 0:
                logger.info(f"Already downloaded: {dest_path.name} ({self.storage.format_size(file_size)})")
                return {"path": str(dest_path), "size": file_size, "hash_ok": True, "skipped": True}

        # Ensure parent directory exists
        dest_path.parent.mkdir(parents=True, exist_ok=True)

        # Temp file for atomic download
        temp_path = dest_path.with_suffix(dest_path.suffix + ".download")

        for attempt in range(1, self.max_retries + 1):
            try:
                self._rate_limit(source)
                logger.info(f"Downloading ({attempt}/{self.max_retries}): {url}")

                # Start/resume download
                headers = {}
                start_pos = 0

                # Resume if partial file exists
                if temp_path.exists():
                    start_pos = temp_path.stat().st_size
                    headers["Range"] = f"bytes={start_pos}-"
                    logger.info(f"Resuming from {self.storage.format_size(start_pos)}")

                # Initial request to get content length
                self._rate_limit(source)
                response = requests.get(url, headers=headers, stream=True, timeout=30)
                response.raise_for_status()

                content_length = int(response.headers.get("Content-Length", 0))
                total_size = start_pos + content_length

                # Check budget before continuing
                if start_pos == 0:
                    allowed, reason = self.storage.check_budget(total_size, source)
                    if not allowed:
                        raise DownloadError(f"Budget check failed: {reason}")

                # Download with progress
                mode = "ab" if start_pos > 0 else "wb"
                sha256 = hashlib.sha256()

                with open(temp_path, mode) as f:
                    bytes_written = start_pos
                    for chunk in response.iter_content(chunk_size=self.chunk_size):
                        if not chunk:
                            continue
                        f.write(chunk)
                        sha256.update(chunk)
                        bytes_written += len(chunk)

                        if progress_callback:
                            progress_callback(bytes_written, total_size)

                # Verify hash
                actual_hash = sha256.hexdigest()
                hash_ok = True
                if expected_hash:
                    hash_ok = (actual_hash == expected_hash)
                    if not hash_ok:
                        logger.warning(f"Hash mismatch! Expected {expected_hash}, got {actual_hash}")
                        temp_path.unlink()
                        continue  # Retry

                # Atomic move
                temp_path.rename(dest_path)
                final_size = dest_path.stat().st_size

                logger.info(f"Downloaded: {dest_path.name} ({self.storage.format_size(final_size)})")
                return {
                    "path": str(dest_path),
                    "size": final_size,
                    "hash_ok": hash_ok,
                    "skipped": False,
                    "hash": actual_hash,
                }

            except (requests.RequestException, IOError) as e:
                logger.warning(f"Download attempt {attempt} failed: {e}")
                if attempt < self.max_retries:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.info(f"Retrying in {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    # Clean up temp file
                    if temp_path.exists():
                        temp_path.unlink()
                    return None  # Return None on total failure

    def download_batch(self, downloads: list[dict], source: str) -> list[dict]:
        """
        Download a batch of files.

        Args:
            downloads: List of dicts with keys: url, path, hash (optional)
            source: Source name for rate limiting and budget tracking

        Returns:
            List of result dicts
        """
        results = []
        total = len(downloads)

        for i, dl in enumerate(downloads):
            print(f"\n  [{i+1}/{total}] {Path(dl['path']).name}")

            def progress(current, total):
                if total > 0:
                    pct = current / total * 100
                    bar_len = 30
                    filled = int(bar_len * current / total)
                    bar = "█" * filled + "░" * (bar_len - filled)
                    print(f"\r    [{bar}] {pct:.0f}% ({self.storage.format_size(current)}/{self.storage.format_size(total)})", end="", flush=True)

            try:
                result = self.download(
                    url=dl["url"],
                    dest_path=Path(dl["path"]),
                    source=source,
                    expected_hash=None,  # Skip hash verification - Poly Haven uses MD5, we compute SHA256
                    progress_callback=progress,
                )
                print()  # Newline after progress bar

                if result is not None:
                    results.append(result)

                    # Check budget after each download
                    stats = self.storage.get_stats()
                    remaining = self.storage.config.max_total_bytes - stats.total_used_bytes
                    print(f"    Storage: {self.storage.format_size(stats.total_used_bytes)}/{self.storage.format_size(self.storage.config.max_total_bytes)}  ({(stats.total_used_bytes/self.storage.config.max_total_bytes*100):.1f}%)")

                    if remaining < 100 * 1024**2:  # Less than 100MB remaining
                        print(f"\n    ⚠️  Budget nearly full! Stopping downloads.")
                        break
                else:
                    print(f"    ❌ Failed after retries")
                    results.append({"path": dl["path"], "error": "Failed after retries"})

            except DownloadError as e:
                print(f"    ❌ Failed: {e}")
                results.append({"path": dl["path"], "error": str(e)})

        return results
