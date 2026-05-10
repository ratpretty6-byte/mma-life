#!/usr/bin/env python3
"""Start web server, wait for it, then optionally start tunnel"""
import subprocess, os, sys, time, socket, signal, threading

def start_server():
    proc = subprocess.Popen(
        [sys.executable, '-u', 'web_server.py'],
        stdout=open('/tmp/server_stdout.log', 'w'),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    print(f'Server PID: {proc.pid}')
    # Wait for server to be ready
    for i in range(60):
        time.sleep(1)
        try:
            s = socket.socket()
            s.settimeout(2)
            s.connect(('localhost', 8000))
            s.close()
            print(f'Server ready on port 8000 ({i+1}s)')
            return proc
        except:
            pass
    print('Server failed to start')
    return None

if __name__ == '__main__':
    proc = start_server()
    if not proc:
        sys.exit(1)
    # Keep running
    try:
        while True:
            time.sleep(10)
            if proc.poll() is not None:
                print('Server died')
                break
    except KeyboardInterrupt:
        print('Shutting down')
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
