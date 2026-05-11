#!/usr/bin/env python3
import sys, os, time, threading, urllib.request, subprocess, select, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import web_server

print("Initializing MMA world...", flush=True)
web_server.ensure_initialized()
print("World ready!", flush=True)

from http.server import HTTPServer
server = HTTPServer(('0.0.0.0', 8000), web_server.Handler)
print("Server on http://0.0.0.0:8000", flush=True)

def serve():
    server.serve_forever()
threading.Thread(target=serve, daemon=True).start()

time.sleep(1)
try:
    r = urllib.request.urlopen('http://localhost:8000/api/init', timeout=5)
    print("API test OK", flush=True)
except Exception as e:
    print("API test error:", e, flush=True)

print("Starting public tunnel...", flush=True)
tunnel_proc = subprocess.Popen(
    ['ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'ServerAliveInterval=30',
     '-R', '80:localhost:8000', 'nokey@localhost.run'],
    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    start_new_session=True,
)

found_url = None
output_lines = []
for _ in range(90):
    r, _, _ = select.select([tunnel_proc.stdout], [], [], 1)
    if r:
        line = tunnel_proc.stdout.readline().decode(errors='ignore').strip()
        output_lines.append(line)
        print(f"  {line}", flush=True)
        # Accept any https URL that contains a unique tunnel identifier
        m = re.search(r'https://([a-zA-Z0-9][a-zA-Z0-9-]*\.localhost\.run)', line)
        if m:
            found_url = m.group(0)
            break
        # Also look for the format ** https://xxxx **
        m2 = re.search(r'\*\*\s+(https?://\S+)\s+\*\*', line)
        if m2:
            url = m2.group(1)
            if 'localhost.run' not in url and 'admin' not in url:
                found_url = url
                break
    if found_url:
        break

if found_url:
    print(f"\n*** PUBLIC URL: {found_url} ***\n", flush=True)
else:
    print("\nTunnel URL not detected yet. Checking output...", flush=True)
    for l in output_lines[-5:]:
        print(f"  {l}", flush=True)

print("\nServer running. Press Ctrl+C to stop.", flush=True)
try:
    while True:
        time.sleep(10)
except KeyboardInterrupt:
    print("Shutting down...", flush=True)
    server.shutdown()
    tunnel_proc.terminate()
