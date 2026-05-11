#!/bin/bash
# Simple launcher for MMA Life Simulator

cd /workspace/MMALIFE

# Kill any existing server
pkill -f "web_server.py" 2>/dev/null

# Start the server
./venv/bin/python web_server.py > /tmp/mma_server.log 2>&1 &
disown

# Wait for server to start
sleep 2

echo "========================================"
echo "  MMA Life Simulator is running!"
echo "  Open in your browser:"
echo "  http://localhost:8000"
echo "========================================"
echo ""
echo "Server logs: tail -f /tmp/mma_server.log"
echo "Stop server: pkill -f 'web_server.py'"
