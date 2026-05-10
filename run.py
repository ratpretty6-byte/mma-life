#!/usr/bin/env python3
"""Run the MMA web server with tunnel URL output"""
import sys, os, time, threading, socket, json, urllib.request
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Monkey-patch to skip slow AI fighter generation for testing
# We'll set up the server to run in a thread

from http.server import HTTPServer
import web_server

def start_tunnel():
    """Start localhost.run tunnel and return URL"""
    import subprocess
    try:
        proc = subprocess.Popen(
            ['ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'ServerAliveInterval=30',
             '-R', '80:localhost:8000', 'nokey@localhost.run'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        time.sleep(5)
        # Try to get URL from output
        import select
        url = None
        for _ in range(20):
            r, _, _ = select.select([proc.stdout], [], [], 1)
            if r:
                line = proc.stdout.readline().decode(errors='ignore')
                print(f'TUNNEL: {line.strip()}')
                if 'localhost.run' in line and ('https://' in line or 'http://' in line):
                    for word in line.split():
                        if 'localhost.run' in word:
                            url = word.strip()
                            break
            if url:
                break
        return url
    except Exception as e:
        print(f'Tunnel error: {e}')
        return None

if __name__ == '__main__':
    server = HTTPServer(('0.0.0.0', 8000), web_server.MMAHandler)
    print(f'Server starting on http://0.0.0.0:8000')
    
    # Start tunnel in background thread
    tunnel_url = [None]
    def tunnel_thread():
        tunnel_url[0] = start_tunnel()
        if tunnel_url[0]:
            print(f'\nPUBLIC URL: {tunnel_url[0]}\n')
        else:
            print('\nCould not establish tunnel')
    t = threading.Thread(target=tunnel_thread, daemon=True)
    t.start()
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nShutting down')
        server.shutdown()
