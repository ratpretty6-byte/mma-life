#!/usr/bin/env python3
"""Start web server, wait for it, then start tunnel"""
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

def start_tunnel():
    """Start localhost.run tunnel and print URL"""
    try:
        proc = subprocess.Popen(
            ['ssh', '-o', 'StrictHostKeyChecking=no', '-o', 'ServerAliveInterval=30',
             '-R', '80:localhost:8000', 'nokey@localhost.run'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        time.sleep(5)
        import select
        url = None
        for _ in range(40):
            r, _, _ = select.select([proc.stdout], [], [], 1)
            if r:
                line = proc.stdout.readline().decode(errors='ignore').strip()
                print(f'TUNNEL: {line}')
                if 'localhost.run' in line or 'lhr.life' in line:
                    for word in line.split():
                        if 'localhost.run' in word or 'lhr.life' in word:
                            url = word.strip().rstrip(',;')
                            break
            if url:
                break
        if url:
            print(f'\n*** PUBLIC URL: {url} ***\n')
        else:
            print('\nCould not establish tunnel')
        return proc
    except Exception as e:
        print(f'Tunnel error: {e}')
        return None

if __name__ == '__main__':
    proc = start_server()
    if not proc:
        sys.exit(1)
    tunnel_proc = start_tunnel()
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
        if tunnel_proc:
            tunnel_proc.terminate()
