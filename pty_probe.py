#!/usr/bin/env python3
"""PTY probe — find the actual prompt string from K's session."""
import websocket, json, re, time, sys

ANSI = re.compile(
    r'\x1b\[[0-9;?]*[a-zA-Z]'
    r'|\x1b\][^\x07\x5c]*[\x07\x5c]'
    r'|\x1b[()][AB012]'
    r'|\x0f|\x0e|\x1b=|\x1b>'
)

def strip(s):
    s = ANSI.sub('', s)
    return s.replace('\r\n', '\n').replace('\r', '')

port = int(sys.argv[1]) if len(sys.argv) > 1 else 9200

ws = websocket.create_connection(
    f'ws://localhost:{port}/ws?cols=220&rows=50',
    header=['Authorization: Bearer communion'],
    timeout=10
)
first = ws.recv()
print('SESSION:', first[:100])

buf = ''
deadline = time.time() + 10
while time.time() < deadline:
    try:
        ws.settimeout(0.3)
        d = ws.recv()
        chunk = d if isinstance(d, str) else d.decode('utf-8', errors='replace')
        buf += chunk
    except:
        pass

clean = strip(buf)
print('--- TAIL (500 chars) ---')
print(repr(clean[-500:]))
ws.close()
