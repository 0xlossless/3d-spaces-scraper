#!/usr/bin/env python3
"""Simple dashboard server using Python's built-in http.server."""

import http.server
import json
import os
import sys
from pathlib import Path

PORT = 8765
PROJECT_ROOT = Path(__file__).parent.parent.parent


class DashboardHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/progress':
            self.send_progress()
        elif self.path == '/':
            self.serve_dashboard()
        else:
            self.send_error(404)

    def serve_dashboard(self):
        dashboard_path = PROJECT_ROOT / 'dashboard.html'
        try:
            with open(dashboard_path) as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(content.encode())
        except FileNotFoundError:
            self.send_error(404, "dashboard.html not found")

    def send_progress(self):
        try:
            from src.pipeline.storage import StorageManager, StorageConfig

            storage = StorageConfig(
                base_path=PROJECT_ROOT / "data/assets",
                max_total_bytes=50 * 1024**3,
            )
            manager = StorageManager(storage)
            stats = manager.get_stats()

            used_gb = stats.total_used_bytes / (1024**3)
            remaining_gb = (storage.max_total_bytes - stats.total_used_bytes) / (1024**3)
            usage_pct = (stats.total_used_bytes / storage.max_total_bytes) * 100

            by_type = {}
            for atype, size in stats.per_type_bytes.items():
                type_files = sum(1 for f in (PROJECT_ROOT / "data/assets").rglob("*")
                               if f.is_file() and len(f.parts) > 2 and f.parts[-2] == atype)
                by_type[atype] = {
                    "files": type_files,
                    "size_gb": round(size / (1024**3), 2),
                }

            data = {
                "used_gb": round(used_gb, 2),
                "remaining_gb": round(remaining_gb, 2),
                "usage_pct": round(usage_pct, 1),
                "total_files": stats.total_files,
                "by_type": by_type,
                "recent": [],
            }

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def log_message(self, format, *args):
        pass  # Suppress logs


if __name__ == '__main__':
    # Add project root to path
    sys.path.insert(0, str(PROJECT_ROOT))

    server = http.server.HTTPServer(('0.0.0.0', PORT), DashboardHandler)
    print(f"🌐 Dashboard running at http://localhost:{PORT}")
    print(f"   Open in browser: http://localhost:{PORT}")
    sys.stdout.flush()
    server.serve_forever()
