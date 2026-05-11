#!/bin/bash
cd /workspace/MMALIFE
pkill -f "web_server.py" 2>/dev/null
./venv/bin/python web_server.py > /tmp/mma_server.log 2>&1 &
disown
sleep 2
echo "Server started on port 8000"
echo "Access at: http://localhost:8000"
echo "Check log: tail -f /tmp/mma_server.log"
curl -s http://localhost:8000/api/state
