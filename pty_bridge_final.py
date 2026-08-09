#!/usr/bin/env python3
"""
PTY bridge — connects to a live Claude Code PTY session,
sends a message, waits for stream silence, returns clean response.

Detection strategy: stream goes quiet for 2s = response complete.
No status bar parsing needed.
"""
import websocket, re, time, sys

ANSI = re.compile(
    r'\x1b\[[0-9;?]*[a-zA-Z]'
    r'|\x1b\][^\x07\x5c]*[\x07\x5c]'
    r'|\x1b[()][AB012]'
    r'|\x0f|\x0e|\x1b=|\x1b>'
)

# Lines to strip from output
JUNK = [
    '⏵⏵', '──────', 'shift+tab', 'esc to interrupt',
    'ctrl+g', 'bypass', 'Auto-updating', '↑ tokens', '↓',
    'medium·/', 'effort', '◐', '◑', '◒', '◓',
    'Claude Code has switched',
    'Run `claude install`',
]

def strip_ansi(s):
    s = ANSI.sub('', s)
    return s.replace('\r\n', '\n').replace('\r', '')

def is_junk(line):
    stripped = line.strip()
    if not stripped:
        return True
    if sum(1 for c in stripped if ord(c) > 0x2500 and ord(c) < 0x2600) > 3:
        return True  # box-drawing heavy
    return any(j in stripped for j in JUNK)

def extract_response(raw, sent_message):
    clean = strip_ansi(raw)
    lines = clean.split('\n')
    result = []
    capturing = False
    sent_clean = sent_message.strip().replace(' ', '').lower()

    for line in lines:
        line_clean = line.strip().replace('\xa0', ' ').strip()
        # Find the echoed input line
        if not capturing:
            echoed = line_clean.replace(' ', '').lower()
            if sent_clean in echoed or sent_clean[:10] in echoed:
                capturing = True
                continue
            continue
        if is_junk(line):
            continue
        result.append(line_clean)

    # Trim empty lines
    while result and not result[0]:
        result.pop(0)
    while result and not result[-1]:
        result.pop()

    return '\n'.join(result)


def pty_send(port, message, timeout=90, silence=2.5):
    ws = websocket.create_connection(
        f'ws://localhost:{port}/ws?cols=220&rows=50',
        header=['Authorization: Bearer communion'],
        timeout=10
    )
    ws.recv()  # session token

    # Drain existing output
    for _ in range(40):
        try:
            ws.settimeout(0.2)
            ws.recv()
        except:
            break

    # Send message
    ws.send(message + '\n')
    send_time = time.time()

    # Collect until silence
    buf = ''
    last_activity = time.time()
    deadline = time.time() + timeout

    while time.time() < deadline:
        try:
            ws.settimeout(0.3)
            chunk = ws.recv()
            if chunk:
                buf += chunk if isinstance(chunk, str) else chunk.decode('utf-8', errors='replace')
                last_activity = time.time()
        except:
            pass
        # Must wait at least 3s before checking silence (avoid catching pre-response)
        elapsed = time.time() - send_time
        silent_for = time.time() - last_activity
        if elapsed > 3.0 and silent_for >= silence:
            break

    ws.close()
    return extract_response(buf, message)


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9200
    message = sys.argv[2] if len(sys.argv) > 2 else "say hi in 3 words"
    result = pty_send(port, message)
    print(result)
