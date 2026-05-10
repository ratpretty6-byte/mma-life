#!/usr/bin/env python3
"""Simplified web server for MMA Life Simulator"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import urllib.parse
from datetime import datetime, timedelta

# Game state
fighter = None

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            if self.path == '/' or self.path == '/index.html':
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.end_headers()
                with open('/workspace/MMALIFE/templates/index.html', 'rb') as f:
                    self.wfile.write(f.read())
            elif self.path == '/api/state':
                self.send_json_response({'fighter': fighter})
            elif self.path.startswith('/api/create'):
                params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                name = params.get('name', ['Fighter'])[0]
                # Simple fighter creation
                self.send_json_response({'success': True, 'name': name})
            else:
                self.send_error(404)
        except Exception as e:
            self.send_json_response({'error': str(e)})
    
    def send_json_response(self, data):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

if __name__ == '__main__':
    PORT = 8080
    server = HTTPServer(('0.0.0.0', PORT), SimpleHandler)
    print(f'Server running on port {PORT}')
    server.serve_forever()
