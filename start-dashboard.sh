#!/bin/bash
# Start the 3D Spaces dashboard server

cd /home/josep/3d-spaces-scraper

# Kill any existing dashboard server
fuser -k 8765/tcp 2>/dev/null
sleep 1

# Start the server
python3 src/pipeline/standalone_dashboard.py &
DASH_PID=$!

echo "🌐 Dashboard started (PID: $DASH_PID)"
echo "   Progress: http://localhost:8765"
echo "   3D Viewer: http://localhost:8765/viewer"

# Keep running
wait $DASH_PID
