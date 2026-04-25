"""
Simple HTTP dashboard server for monitoring download progress.
"""

import http.server
import json
import logging
import socketserver
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

PORT = 8765
DASHBOARD_PATH = Path(__file__).parent.parent.parent / "dashboard.html"


class ProgressHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/progress':
            self.send_progress()
        elif self.path == '/':
            self.send_dashboard()
        else:
            super().do_GET()

    def send_dashboard(self):
        try:
            with open(DASHBOARD_PATH) as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(content.encode())
        except FileNotFoundError:
            self.send_error(404, "Dashboard not found")

    def send_progress(self):
        from src.pipeline.storage import StorageManager, StorageConfig
        from src.pipeline.manifest import Manifest
        from src.storage.database import Database

        try:
            # Get storage stats
            storage = StorageConfig(
                base_path=Path("data/assets"),
                max_total_bytes=50 * 1024**3,
            )
            manager = StorageManager(storage)
            stats = manager.get_stats()

            # Get manifest stats
            manifest = Manifest()
            manifest_stats = manifest.get_stats()

            # Get recent downloads from DB
            db = Database("data/3d_spaces.db")
            recent_rows = db.conn.execute(
                "SELECT title, asset_type, local_file_size, downloaded_at, download_status "
                "FROM records WHERE download_status = 'completed' "
                "ORDER BY downloaded_at DESC LIMIT 10"
            ).fetchall()
            db.close()

            # Build response
            used_gb = stats.total_used_bytes / (1024**3)
            remaining_gb = (storage.max_total_bytes - stats.total_used_bytes) / (1024**3)
            usage_pct = (stats.total_used_bytes / storage.max_total_bytes) * 100

            by_type = {}
            for atype, size in stats.per_type_bytes.items():
                # Count files by type from directory
                type_files = sum(1 for f in Path("data/assets").rglob("*")
                               if f.is_file() and f.parts[-2] == atype)
                by_type[atype] = {
                    "files": type_files,
                    "size_gb": size / (1024**3),
                }

            recent = []
            for row in recent_rows:
                recent.append({
                    "time": row[3] or "",
                    "status": "success",
                    "message": f"{row[0]} ({row[1]}) - {manager.format_size(row[2] or 0)}",
                })

            data = {
                "used_gb": used_gb,
                "remaining_gb": remaining_gb,
                "usage_pct": usage_pct,
                "total_files": stats.total_files,
                "by_type": by_type,
                "recent": recent,
            }

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())

        except Exception as e:
            logger.error(f"Failed to get progress: {e}")
            self.send_error(500, str(e))

    def log_message(self, format, *args):
        # Suppress request logs
        pass


def run_server(port=PORT):
    """Start the dashboard server."""
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", port), ProgressHandler) as httpd:
        print(f"🌐 Dashboard running at http://localhost:{port}")
        print(f"   Open in browser: http://localhost:{port}")
        httpd.serve_forever()


if __name__ == "__main__":
    run_server()
