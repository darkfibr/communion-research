#!/usr/bin/env python3
"""Send a message to the PTY and capture the response."""
import websocket, json, re, time, sys

ANSI = re.compile(
    r'\x1b\[[0-9;?]*[a-zA-Z]'
    r'|\x1b\][^\x07\x5c]*[\x07\x5c]'
    r'|\x1b[()][AB012]'
    r'|\x0f|\x0e|\x1b=|\x1b>'
)

# The ready prompt — when this appears the agent is waiting for input
READY_MARKERS = [
    '⏵⏵ bypass',
    '⏵⏵bypass',
    '❯ ',
    '> ',
]

def strip(s):
    s = ANSI.sub('', s)
    return s.replace('\r\n', '\n').replace('\r', '')

def is_ready(text):
    return any(m in text for m in READY_MARKERS)

port = int(sys.argv[1]) if len(sys.argv) > 1 else 9200
message = sys.argv[2] if len(sys.argv) > 2 else "say hello in 5 words"

ws = websocket.create_connection(
    f'ws://localhost:{port}/ws?cols=220&rows=50',
    header=['Authorization: Bearer communion'],
    timeout=10
)
ws.recv()  # session token

# Drain until ready
buf = ''
print('Waiting for ready prompt...')
deadline = time.time() + 10
while time.time() < deadline:
    try:
        ws.settimeout(0.3)
        d = ws.recv()
        buf += d if isinstance(d, str) else d.decode('utf-8', errors='replace')
        if is_ready(strip(buf)):
            print('Ready.')
            break
    except:
        pass

# Send message
print(f'Sending: {message!r}')
ws.send(message + '\n')

# Collect response until ready prompt reappears
response_buf = ''
deadline = time.time() + 90
last_ready = False
while time.time() < deadline:
    try:
        ws.settimeout(0.5)
        d = ws.recv()
        chunk = d if isinstance(d, str) else d.decode('utf-8', errors='replace')
        response_buf += chunk
        clean = strip(response_buf)
        # Ready prompt reappeared = response complete
        lines = clean.split('\n')
        for line in lines[-5:]:
            if is_ready(line):
                last_ready = True
                break
        if last_ready:
            break
    except:
        pass

ws.close()

clean = strip(response_buf)
print('--- RAW RESPONSE TAIL ---')
print(repr(clean[-800:]))
