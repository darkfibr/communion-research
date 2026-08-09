#!/usr/bin/env python3
"""
Phoenix PTY Chat Bridge
=======================
Maintains one persistent PTY session per agent.
Each chat request resumes the same session → real context, real memory, real tools.

Runs as part of chat_api.py or standalone on port 9803.

Endpoint:
  POST /pty/chat
  {
    "agent": "kim_i",
    "message": "...",
    "timeout": 90
  }
  → {"agent": "kim_i", "response": "...", "session_token": "...", "error": null}

  GET /pty/agents
  → {"agents": [{"id": "kim_i", "port": 9200, "session": "abc...", "connected": true}]}
"""

import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import websocket

# ── Config ────────────────────────────────────────────────────────────────────

PORT   = 9803
SECRET = "bef872222d4c0e96acd17f3c2fc58b4270ae990fec1f23e94bdf9e5555b5c429"

AGENT_PORTS = {
    "kim_i":  9200,
    "spear":  9201,
    "vesper": 9202,
    "qwen":   9203,
    "forge":  9204,
}

# ANSI escape stripper
ANSI = re.compile(
    r'\x1b\[[0-9;?]*[a-zA-Z]'
    r'|\x1b\][^\x07\x5c]*[\x07\x5c]'
    r'|\x1b[()][AB012]'
    r'|\x0f|\x0e|\x1b=|\x1b>'
)

JUNK_MARKERS = [
    '⏵⏵', 'bypass', 'shift+tab', 'esc to interrupt',
    'ctrl+g', 'Auto-updating', 'medium·/', '◐', '◑', '◒', '◓',
    'Claude Code has switched', 'Run `claude', 'docs.anthropic',
    '↑ ', '↓ ', ' tokens',
]

# ── Session store ─────────────────────────────────────────────────────────────

class AgentSession:
    def __init__(self, agent_id: str, port: int):
        self.agent_id = agent_id
        self.port = port
        self.token: str | None = None
        self.lock = threading.Lock()

    def connect(self) -> websocket.WebSocket:
        url = f'ws://localhost:{self.port}/ws?cols=220&rows=50'
        if self.token:
            url += f'&resume={self.token}'
        ws = websocket.create_connection(
            url,
            header=['Authorization: Bearer communion'],
            timeout=10,
        )
        msg = json.loads(ws.recv())
        self.token = msg.get('token', self.token)
        return ws

    def _is_ready(self, text: str) -> bool:
        """Detect that the agent is idle and waiting for input."""
        # The ❯ prompt appears when Claude Code is ready
        # Also check for bypass mode indicator which shows when idle
        last = text[-800:] if len(text) > 800 else text
        return '❯' in last or 'ctrl+g' in last.lower()

    def send(self, message: str, timeout: int = 90, silence: float = 2.5) -> str:
        with self.lock:
            try:
                ws = self.connect()
            except Exception as e:
                # Session expired — create fresh
                self.token = None
                ws = self.connect()

            # Wait for boot/ready state (up to 60s — MiniMax boot takes a while)
            boot_buf = ''
            boot_deadline = time.time() + 60
            last_boot_data = time.time()
            while time.time() < boot_deadline:
                try:
                    ws.settimeout(0.5)
                    chunk = ws.recv()
                    if chunk:
                        boot_buf += chunk if isinstance(chunk, str) else chunk.decode('utf-8', errors='replace')
                        last_boot_data = time.time()
                        clean = ANSI.sub('', boot_buf).replace('\r', '')
                        if self._is_ready(clean):
                            break
                except:
                    # Stream quiet for 3s after getting some data = probably ready
                    if boot_buf and time.time() - last_boot_data > 3.0:
                        break

            # Send
            ws.send(message + '\n')
            send_time = time.time()

            # Collect until silence AFTER real content appears
            buf = ''
            last_activity = time.time()
            got_content = False
            deadline = time.time() + timeout
            msg_norm = message.replace(' ', '').lower()

            while time.time() < deadline:
                try:
                    ws.settimeout(0.4)
                    chunk = ws.recv()
                    if chunk:
                        buf += chunk if isinstance(chunk, str) else chunk.decode('utf-8', errors='replace')
                        last_activity = time.time()
                        if not got_content:
                            test = ANSI.sub('', buf).replace('\r', '')
                            for ln in test.split('\n'):
                                s = ln.strip()
                                if not s: continue
                                if any(x in s for x in ['⏵⏵','─','◐','◑','◒','◓','bypass',
                                    'shift+tab','ctrl+g','Auto-','effort','❯','tokens']): continue
                                if msg_norm in s.replace(' ','').lower(): continue
                                got_content = True
                                break
                except:
                    pass
                if got_content and time.time() - last_activity >= silence:
                    break

            # Disconnect but keep session alive via token
            try:
                ws.close()
            except:
                pass

            return self._extract(buf, message)

    def _extract(self, raw: str, sent: str) -> str:
        clean = ANSI.sub('', raw).replace('\r\n', '\n').replace('\r', '')
        lines = clean.split('\n')

        result = []
        capturing = False
        sent_norm = sent.strip().replace(' ', '').replace('\xa0', '').lower()[:20]

        for line in lines:
            line_clean = line.replace('\xa0', ' ').strip()

            if not capturing:
                # Find the echoed input
                echoed = line_clean.replace(' ', '').lower()
                if sent_norm and sent_norm[:10] in echoed:
                    capturing = True
                    continue
                continue

            # Skip junk lines
            if not line_clean:
                if result:  # keep interior blank lines
                    result.append('')
                continue
            # Filter box-drawing and block-element heavy lines (rules, banners, borders)
            special_chars = sum(1 for c in line_clean if '\u2500' <= c <= '\u259f')
            if special_chars > 3:
                continue
            if any(j in line_clean for j in JUNK_MARKERS):
                continue

            result.append(line_clean)

        # Trim
        while result and not result[0]:
            result.pop(0)
        while result and not result[-1]:
            result.pop()

        return '\n'.join(result)


# Global session store
_sessions: dict[str, AgentSession] = {
    agent_id: AgentSession(agent_id, port)
    for agent_id, port in AGENT_PORTS.items()
}


# ── HTTP handler ──────────────────────────────────────────────────────────────

def check_auth(headers) -> bool:
    return headers.get("Authorization", "") == f"Bearer {SECRET}"

def json_resp(handler, status: int, data: dict):
    body = json.dumps(data).encode()
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.end_headers()
    handler.wfile.write(body)


class BridgeHandler(BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print(f"[pty-bridge] {fmt % args}")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.end_headers()

    def do_GET(self):
        if not check_auth(self.headers):
            return json_resp(self, 401, {"error": "unauthorized"})
        if self.path == "/pty/agents":
            agents = []
            for agent_id, sess in _sessions.items():
                agents.append({
                    "id": agent_id,
                    "port": sess.port,
                    "session_token": sess.token,
                    "connected": sess.token is not None,
                })
            return json_resp(self, 200, {"agents": agents})
        json_resp(self, 404, {"error": "not found"})

    def do_POST(self):
        if not check_auth(self.headers):
            return json_resp(self, 401, {"error": "unauthorized"})
        if self.path != "/pty/chat":
            return json_resp(self, 404, {"error": "not found"})

        length = int(self.headers.get("Content-Length", 0))
        try:
            body = json.loads(self.rfile.read(length))
        except:
            return json_resp(self, 400, {"error": "invalid json"})

        agent_id = body.get("agent", "")
        message = body.get("message", "").strip()
        timeout = int(body.get("timeout", 90))

        if agent_id not in _sessions:
            return json_resp(self, 400, {"error": f"unknown agent: {agent_id}"})
        if not message:
            return json_resp(self, 400, {"error": "message required"})

        sess = _sessions[agent_id]
        try:
            response = sess.send(message, timeout=timeout)
            json_resp(self, 200, {
                "agent": agent_id,
                "response": response,
                "session_token": sess.token,
                "error": None,
            })
        except Exception as e:
            json_resp(self, 200, {
                "agent": agent_id,
                "response": "",
                "session_token": sess.token,
                "error": str(e),
            })


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), BridgeHandler)
    print(f"[pty-bridge] Phoenix PTY Chat Bridge on port {PORT}")
    print(f"[pty-bridge] Agents: {list(AGENT_PORTS.keys())}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
