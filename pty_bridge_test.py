#!/usr/bin/env python3
"""PTY bridge test — send message, wait for full response."""
import websocket, re, time, sys

ANSI = re.compile(
    r'\x1b\[[0-9;?]*[a-zA-Z]'
    r'|\x1b\][^\x07\x5c]*[\x07\x5c]'
    r'|\x1b[()][AB012]'
    r'|\x0f|\x0e|\x1b=|\x1b>'
)

# Idle state markers (shown in status bar when waiting for input)
IDLE_HINTS = [
    'shift+tab to cycle',   # bypass mode hint
    'esc to interrupt',
    'ctrl+g to edit',
]

# Active/thinking markers
THINKING_MARKERS = [
    'esc to interrupt',
    'Actioning',
    '↑ tokens',
]

def strip(s):
    s = ANSI.sub('', s)
    return s.replace('\r\n', '\n').replace('\r', '')

def is_idle(text):
    last500 = text[-500:]
    return any(m in last500 for m in IDLE_HINTS)

def extract_response(full_output, sent_message):
    """
    Extract just the assistant response from the PTY stream.
    Strips: echoed input, status bars, box-drawing chars, empty lines at start/end.
    """
    clean = strip(full_output)
    lines = clean.split('\n')

    result_lines = []
    capture = False
    # Find where the echoed input ends and response starts
    for line in lines:
        stripped = line.strip()
        # Skip the echoed input line
        if sent_message.strip() in stripped and not capture:
            capture = True
            continue
        if not capture:
            continue
        # Skip status bar lines
        if any(m in stripped for m in ['⏵⏵', '──────', 'shift+tab', 'esc to interrupt',
                                         'ctrl+g', 'bypass', 'Auto-updating', 'tokens']):
            continue
        # Skip box-drawing heavy lines
        if stripped and sum(1 for c in stripped if ord(c) > 0x2500 and ord(c) < 0x2600) > len(stripped) * 0.3:
            continue
        result_lines.append(line.rstrip())

    # Trim leading/trailing empty lines
    while result_lines and not result_lines[0].strip():
        result_lines.pop(0)
    while result_lines and not result_lines[-1].strip():
        result_lines.pop()

    return '\n'.join(result_lines)

port = int(sys.argv[1]) if len(sys.argv) > 1 else 9200
message = sys.argv[2] if len(sys.argv) > 2 else "say hi in 5 words"

ws = websocket.create_connection(
    f'ws://localhost:{port}/ws?cols=220&rows=50',
    header=['Authorization: Bearer communion'],
    timeout=10
)
ws.recv()  # session token

# Drain until idle
buf = ''
print('Waiting for idle...', file=sys.stderr)
deadline = time.time() + 12
while time.time() < deadline:
    try:
        ws.settimeout(0.3)
        d = ws.recv()
        buf += d if isinstance(d, str) else d.decode('utf-8', errors='replace')
        if is_idle(strip(buf)):
            print('Idle detected.', file=sys.stderr)
            break
    except:
        pass

# Send
print(f'Sending...', file=sys.stderr)
ws.send(message + '\n')
send_time = time.time()

# Wait for thinking to start (2s min), then wait for idle again
response_buf = ''
phase = 'waiting_start'
deadline = time.time() + 120
while time.time() < deadline:
    try:
        ws.settimeout(0.5)
        d = ws.recv()
        chunk = d if isinstance(d, str) else d.decode('utf-8', errors='replace')
        response_buf += chunk
        elapsed = time.time() - send_time
        clean = strip(response_buf)

        if phase == 'waiting_start' and elapsed > 2.0:
            phase = 'collecting'
            print('Collecting response...', file=sys.stderr)

        if phase == 'collecting' and elapsed > 3.0 and is_idle(clean):
            print('Response complete.', file=sys.stderr)
            break
    except:
        if time.time() - send_time > 5:
            pass  # keep waiting

ws.close()

response = extract_response(response_buf, message)
print(response)
