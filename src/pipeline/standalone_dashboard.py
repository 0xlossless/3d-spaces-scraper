#!/usr/bin/env python3
"""Standalone dashboard server - no imports from src/ needed."""

import http.server
import json
import os
import sys
from pathlib import Path

PORT = 8765
ASSETS_DIR = Path(__file__).parent.parent.parent / "data/assets"


def get_stats():
    """Get storage stats without importing src modules."""
    total_used = 0
    total_files = 0
    per_type = {}

    if not ASSETS_DIR.exists():
        return {"total_used": 0, "total_files": 0, "per_type": {}}

    for file_path in ASSETS_DIR.rglob("*"):
        if file_path.is_file():
            size = file_path.stat().st_size
            total_used += size
            total_files += 1

            # Get asset type from path (data/assets/{type}/...)
            rel = file_path.relative_to(ASSETS_DIR)
            parts = rel.parts
            if len(parts) >= 2:
                asset_type = parts[1]
                if asset_type not in per_type:
                    per_type[asset_type] = {"size": 0, "files": 0}
                per_type[asset_type]["size"] += size
                per_type[asset_type]["files"] += 1

    return {"total_used": total_used, "total_files": total_files, "per_type": per_type}


class DashboardHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/progress':
            self.send_progress()
        elif self.path == '/api/assets':
            self.send_assets()
        elif self.path == '/viewer' or self.path == '/3d-viewer.html':
            self.serve_viewer()
        elif self.path == '/':
            self.serve_html()
        else:
            self.send_error(404)

    def serve_viewer(self):
        viewer_path = Path(__file__).parent.parent.parent / '3d-viewer.html'
        try:
            with open(viewer_path) as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(content.encode())
        except FileNotFoundError:
            self.send_error(404)

    def send_assets(self):
        """List all downloadable assets with metadata."""
        try:
            asset_list = []
            
            if ASSETS_DIR.exists():
                for file_path in ASSETS_DIR.rglob("*"):
                    if file_path.is_file():
                        rel = file_path.relative_to(ASSETS_DIR)
                        parts = rel.parts
                        
                        if len(parts) >= 3:
                            source = parts[0]
                            asset_type = parts[1]
                            filename = parts[2]
                            
                            # Clean up name
                            name = filename.rsplit('.', 1)[0]
                            name = name.replace('_', ' ').title()
                            
                            asset_list.append({
                                "id": str(file_path),
                                "name": name,
                                "type": asset_type.rstrip('s'),  # hdris -> hdri, etc.
                                "source": source,
                                "size": file_path.stat().st_size,
                                "path": str(file_path),
                            })
            
            # Sort by name
            asset_list.sort(key=lambda x: x["name"])
            
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(asset_list).encode())
            
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode())

    def serve_html(self):
        html_path = Path(__file__).parent.parent.parent / 'dashboard.html'
        try:
            with open(html_path) as f:
                content = f.read()
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(content.encode())
        except FileNotFoundError:
            self.send_error(404)

    def send_progress(self):
        try:
            stats = get_stats()
            max_bytes = 50 * 1024**3  # 50GB

            used_gb = stats["total_used"] / (1024**3)
            remaining_gb = (max_bytes - stats["total_used"]) / (1024**3)
            usage_pct = (stats["total_used"] / max_bytes) * 100

            by_type = {}
            for atype, info in stats["per_type"].items():
                by_type[atype] = {
                    "files": info["files"],
                    "size_gb": round(info["size"] / (1024**3), 2),
                }

            data = {
                "used_gb": round(used_gb, 2),
                "remaining_gb": round(remaining_gb, 2),
                "usage_pct": round(usage_pct, 1),
                "total_files": stats["total_files"],
                "by_type": by_type,
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
    server = http.server.HTTPServer(('0.0.0.0', PORT), DashboardHandler)
    print(f"🌐 Dashboard running at http://localhost:{PORT}")
    print(f"   Open in browser: http://localhost:{PORT}")
    sys.stdout.flush()
    server.serve_forever()
