#!/usr/bin/env python3
import subprocess, os, sys, time, socket

proc = subprocess.Popen(
    [sys.executable, 'web_server.py'],
    stdout=open('/tmp/server.log', 'w'),
    stderr=open('/tmp/server.err', 'w'),
    start_new_session=True,
)
pid = proc.pid
with open('/tmp/server.pid', 'w') as f:
    f.write(str(pid))
print(f'Server started (PID: {pid})')

for i in range(60):
    time.sleep(2)
    try:
        s = socket.socket()
        s.settimeout(1)
        s.connect(('localhost', 8000))
        s.close()
        print(f'Server ready after {i*2+2}s')
        sys.exit(0)
    except:
        pass
    with open('/tmp/server.err') as f:
        err = f.read()
    if err:
        print(f'Error: {err[:200]}')
        sys.exit(1)
print('Server failed to start in 120s')
sys.exit(1)
