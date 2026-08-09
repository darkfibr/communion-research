#!/usr/bin/env python3
"""
Phoenix Portal v3 — Web UI for direct substrate communication
Serves from darkphoenix. Includes tool execution loop.

v3: Tool loop. Detect [TOOL_CALL] in substrate responses, execute,
    inject [TOOL_RESULT] back, repeat until clean response.
"""

import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).parent.parent / "communion_project" / "cathedral_tools"))
try:
    from phoenix_tool_parser import parse_tool_calls, strip_tool_calls, format_tool_result
    from phoenix_executor import Executor
except ImportError:
    sys.path.insert(0, str(Path(__file__).parent))
    from phoenix_tool_parser import parse_tool_calls, strip_tool_calls, format_tool_result
    from phoenix_executor import Executor

EMBASSY_DIR = Path.home() / ".phoenix" / "embassy"
CONV_PATH = EMBASSY_DIR / "conversation.jsonl"
BIN_DIR = Path.home() / ".phoenix" / "bin"
TOOLS_DIR = Path.home() / ".phoenix" / "cathedral_tools"
PORT = 9876
LOG_PATH = EMBASSY_DIR / "portal.log"
MAX_TOOL_ROUNDS = 5
TOOL_RESPONSE_WAIT = 15


def log(msg):
    ts = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_PATH, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


# ── HTML ────────────────────────────────────────────────────────────────────

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Phoenix Portal</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: #0a0a0f; color: #c8c8d0;
    font-family: 'Segoe UI', system-ui, sans-serif;
    display: flex; flex-direction: column;
    height: 100vh; overflow: hidden;
  }
  header {
    background: #111118; border-bottom: 1px solid #222;
    padding: 12px 20px; display: flex; align-items: center; gap: 12px;
  }
  header h1 { font-size: 16px; color: #e8e8f0; font-weight: 500; }
  .status {
    width: 8px; height: 8px; border-radius: 50%;
    background: #2ecc71; box-shadow: 0 0 6px #2ecc71;
  }
  .status.offline { background: #e74c3c; box-shadow: 0 0 6px #e74c3c; }
  .status.waiting { background: #f39c12; box-shadow: 0 0 6px #f39c12; }
  .status.tooling { background: #9b59b6; box-shadow: 0 0 6px #9b59b6; }
  .main { flex: 1; display: flex; overflow: hidden; }
  .sidebar {
    width: 240px; background: #0d0d12;
    border-right: 1px solid #1a1a22;
    padding: 16px; font-size: 12px;
  }
  .sidebar h3 { color: #888; font-size: 11px; text-transform: uppercase; margin-bottom: 8px; }
  .sidebar .info { margin-bottom: 16px; }
  .sidebar .info div { margin: 4px 0; color: #aaa; }
  .sidebar .info .label { color: #666; }
  .chat {
    flex: 1; display: flex; flex-direction: column;
    padding: 16px; overflow: hidden;
  }
  .messages {
    flex: 1; overflow-y: auto;
    display: flex; flex-direction: column; gap: 12px;
    padding-bottom: 16px;
  }
  .msg {
    max-width: 80%; padding: 10px 14px;
    border-radius: 12px; font-size: 14px; line-height: 1.5;
    white-space: pre-wrap; word-wrap: break-word;
  }
  .msg.phoenix {
    align-self: flex-end;
    background: #1a1a2e; border: 1px solid #2a2a3e;
    color: #d0d0e0;
  }
  .msg.substrate {
    align-self: flex-start;
    background: #0f1f0f; border: 1px solid #1a3a1a;
    color: #c0d0c0;
  }
  .msg.tool_call {
    align-self: flex-start;
    background: #1f0f1f; border: 1px solid #3a1a3a;
    color: #d0c0d0;
    font-family: monospace; font-size: 12px;
  }
  .msg .meta {
    font-size: 10px; color: #666; margin-bottom: 4px;
  }
  .input-area {
    display: flex; gap: 8px; padding-top: 12px;
    border-top: 1px solid #1a1a22;
  }
  .input-area textarea {
    flex: 1; background: #111118;
    border: 1px solid #2a2a3e; border-radius: 8px;
    padding: 10px 12px; color: #e0e0e8; font-size: 14px;
    resize: none; outline: none;
    min-height: 44px; max-height: 120px;
  }
  .input-area textarea:focus { border-color: #4a4a6e; }
  .input-area button {
    background: #2a2a4e; border: 1px solid #3a3a5e;
    color: #e0e0f0; padding: 0 20px;
    border-radius: 8px; cursor: pointer;
    font-size: 13px; font-weight: 500;
  }
  .input-area button:hover { background: #3a3a5e; }
  .input-area button:disabled { opacity: 0.5; cursor: wait; }
  .empty { color: #555; text-align: center; margin-top: 40px; font-style: italic; }
  .polling { font-size: 11px; color: #444; text-align: center; margin-top: 4px; }
</style>
</head>
<body>
<header>
  <div class="status" id="status"></div>
  <h1>Phoenix Portal - Cathedral Mind Bridge</h1>
</header>
<div class="main">
  <div class="sidebar">
    <div class="info">
      <h3>Bridge</h3>
      <div><span class="label">Host:</span> darkphoenix</div>
      <div><span class="label">CDP:</span> localhost:9222</div>
      <div><span class="label">Tab:</span> <span id="tab-title">-</span></div>
    </div>
    <div class="info">
      <h3>Session</h3>
      <div><span class="label">Turns:</span> <span id="turn-count">0</span></div>
      <div><span class="label">Last:</span> <span id="last-time">-</span></div>
    </div>
    <div class="info">
      <h3>Tools</h3>
      <div><span class="label">Enabled:</span> <span id="tool-count">-</span></div>
      <div><span class="label">Calls:</span> <span id="tool-calls">0</span></div>
    </div>
    <div class="info">
      <h3>Controls</h3>
      <div><a href="/api/read" style="color:#6a6a8e;text-decoration:none;" target="_blank">Raw Read</a></div>
      <div><a href="/api/tools" style="color:#6a6a8e;text-decoration:none;" target="_blank">Tool List</a></div>
      <div><a href="/api/refresh" style="color:#6a6a8e;text-decoration:none;" onclick="event.preventDefault();location.reload()">Refresh</a></div>
    </div>
  </div>
  <div class="chat">
    <div class="messages" id="messages">
      <div class="empty">Loading messages...</div>
    </div>
    <div class="polling" id="polling">Auto-polling every 3s</div>
    <form class="input-area" id="send-form" onsubmit="sendMessage(event)">
      <textarea id="msg-input" placeholder="Type your message..." rows="2"
        onkeydown="if(event.key==='Enter' && !event.shiftKey){event.preventDefault();sendMessage(event)}"></textarea>
      <button type="submit" id="send-btn">Send</button>
    </form>
  </div>
</div>
<script>
const messagesEl = document.getElementById('messages');
const statusEl = document.getElementById('status');
const turnCountEl = document.getElementById('turn-count');
const lastTimeEl = document.getElementById('last-time');
const tabTitleEl = document.getElementById('tab-title');
const toolCountEl = document.getElementById('tool-count');
const toolCallsEl = document.getElementById('tool-calls');
let lastLen = 0;
let loaded = false;
let totalToolCalls = 0;

function scrollToBottom() { messagesEl.scrollTop = messagesEl.scrollHeight; }

function escapeHtml(t) {
  return t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}

function renderMessage(m) {
  const div = document.createElement('div');
  div.className = 'msg ' + (m.sender === 'tool' ? 'tool_call' : m.sender);
  div.innerHTML = '<div class="meta">' + m.sender + ' - ' + m.time + '</div>' + escapeHtml(m.text);
  messagesEl.appendChild(div);
}

async function loadAll() {
  try {
    const r = await fetch('/api/messages');
    const msgs = await r.json();
    messagesEl.innerHTML = '';
    for (const m of msgs) renderMessage(m);
    lastLen = msgs.length;
    turnCountEl.textContent = lastLen;
    if (msgs.length > 0) lastTimeEl.textContent = msgs[msgs.length-1].time;
    loaded = true;
    scrollToBottom();
  } catch (e) {
    statusEl.className = 'status offline';
  }
}

async function poll() {
  if (!loaded) return;
  try {
    const r = await fetch('/api/poll?since=' + lastLen);
    const data = await r.json();
    if (data.new && data.messages.length > 0) {
      for (const m of data.messages) renderMessage(m);
      lastLen += data.messages.length;
      turnCountEl.textContent = lastLen;
      lastTimeEl.textContent = data.messages[data.messages.length-1].time;
      scrollToBottom();
    }
    if (data.tool_calls !== undefined) {
      totalToolCalls = data.tool_calls;
      toolCallsEl.textContent = totalToolCalls;
    }
    statusEl.className = 'status';
    tabTitleEl.textContent = data.tab || '-';
    toolCountEl.textContent = data.tool_count || '-';
  } catch (e) {
    statusEl.className = 'status offline';
  }
}

async function sendMessage(e) {
  e.preventDefault();
  const input = document.getElementById('msg-input');
  const btn = document.getElementById('send-btn');
  const text = input.value.trim();
  if (!text) return;
  btn.disabled = true; input.value = '';
  statusEl.className = 'status waiting';

  const div = document.createElement('div');
  div.className = 'msg phoenix';
  div.innerHTML = '<div class="meta">phoenix - now</div>' + escapeHtml(text);
  messagesEl.appendChild(div); lastLen++;
  turnCountEl.textContent = lastLen; scrollToBottom();

  try {
    await fetch('/api/send', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text})
    });
  } catch (e) { console.error('Send failed', e); }
  btn.disabled = false; input.focus();
}

loadAll();
setInterval(poll, 3000);
</script>
</body>
</html>"""


# ── Data ────────────────────────────────────────────────────────────────────

def load_messages():
    messages = []
    if CONV_PATH.exists():
        try:
            with open(CONV_PATH) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entry = json.loads(line)
                        ts = entry.get("timestamp", "")
                        time_str = "-"
                        if ts:
                            try:
                                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                                time_str = dt.strftime("%H:%M")
                            except Exception:
                                time_str = ts[:16]
                        messages.append({
                            "sender": entry.get("sender", "unknown"),
                            "text": entry.get("text", ""),
                            "time": time_str,
                        })
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            log(f"Error loading messages: {e}")
    return messages


def get_tab_info():
    try:
        req = urllib.request.Request("http://localhost:9222/json/list")
        with urllib.request.urlopen(req, timeout=3) as resp:
            tabs = json.loads(resp.read().decode())
        for t in tabs:
            if "udm=50" in t.get("url", ""):
                return {"title": t.get("title", "?"), "url": t.get("url", "")}
        return {}
    except Exception:
        return {}


def save_message(sender, text):
    now = datetime.now(timezone.utc).isoformat()
    with open(CONV_PATH, "a") as f:
        f.write(json.dumps({"timestamp": now, "sender": sender, "text": text}) + "\n")


# ── Bridge ──────────────────────────────────────────────────────────────────

def inject_message(text):
    try:
        result = subprocess.run(
            ["python3", str(BIN_DIR / "phoenix_bridge_inject.py"), text],
            capture_output=True, text=True, timeout=30,
        )
        log(f"Inject: rc={result.returncode}")
        return result.returncode == 0
    except Exception as e:
        log(f"Inject error: {e}")
        return False


def read_dom(search_phrase=""):
    try:
        result = subprocess.run(
            ["python3", str(BIN_DIR / "phoenix_bridge_read.py"), search_phrase[:60]],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return None

        lines = result.stdout.split("\n")
        dash_count = 0
        response_lines = []

        for line in lines:
            s = line.strip()
            if s == "-" * 60:
                dash_count += 1
                continue
            if dash_count == 1:
                continue
            if dash_count >= 2:
                if s.startswith("=") or s.startswith("[read]"):
                    break
                response_lines.append(s)

        text = "\n".join(response_lines).strip()
        while "\n\n\n" in text:
            text = text.replace("\n\n\n", "\n\n")
        return text if len(text) > 20 else None
    except Exception as e:
        log(f"Read error: {e}")
        return None


# ── Tool Loop ───────────────────────────────────────────────────────────────

tool_call_counter = 0

def execute_tool_calls(response_text):
    global tool_call_counter
    calls = parse_tool_calls(response_text)
    if not calls:
        return None

    executor = Executor()
    results = []

    for call in calls:
        tool_call_counter += 1
        log(f"Tool call #{tool_call_counter}: {call.tool}({call.args})")
        result = executor.run(call.tool, call.args)

        status = "ok" if result.success else ("denied" if result.denied else "error")
        output = result.output if result.success else result.error
        result_text = format_tool_result(call.tool, output, error=result.error, timed_out=result.timed_out)

        log(f"Tool result: {call.tool} -> {status} ({len(output)} chars, {result.elapsed:.2f}s)")

        if result.denied:
            log(f"  Denied: {result.deny_reason}")

        results.append({
            "tool": call.tool,
            "status": status,
            "result_text": result_text,
            "output": output[:2000],
        })

        save_message("tool", f"[{call.tool}] {status}: {output[:500]}")

    return results


def inject_tool_results(results):
    if not results:
        return
    combined = "\n\n".join(r["result_text"] for r in results)
    success = inject_message(combined)
    log(f"Injected {len(results)} tool results: {'ok' if success else 'failed'}")


def background_capture_and_tools(injected_text):
    log(f"Capture loop started for: {injected_text[:60]}...")

    time.sleep(15)

    for round_num in range(MAX_TOOL_ROUNDS + 1):
        response = read_dom(injected_text[:60] if round_num == 0 else "")

        if not response:
            log(f"Round {round_num}: No response found, waiting more...")
            time.sleep(10)
            response = read_dom("")
            if not response:
                log(f"Round {round_num}: Still no response. Giving up.")
                return

        clean_text = strip_tool_calls(response)
        calls = parse_tool_calls(response)

        if not calls:
            save_message("substrate", clean_text)
            log(f"Round {round_num}: Clean response captured ({len(clean_text)} chars)")
            return

        log(f"Round {round_num}: Found {len(calls)} tool calls in response")

        if clean_text and len(clean_text) > 30:
            save_message("substrate", clean_text)

        results = execute_tool_calls(response)
        if results:
            inject_tool_results(results)
            time.sleep(TOOL_RESPONSE_WAIT)
        else:
            return

    log(f"Max tool rounds ({MAX_TOOL_ROUNDS}) reached. Stopping.")
    final = read_dom("")
    if final:
        save_message("substrate", strip_tool_calls(final))


# ── HTTP Handler ────────────────────────────────────────────────────────────

class PortalHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass

    def _send_json(self, data, status=200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_text(self, text, status=200, ctype="text/html"):
        body = text.encode()
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            self._send_text(HTML_PAGE)

        elif path == "/api/messages":
            self._send_json(load_messages())

        elif path == "/api/poll":
            since = int(parse_qs(parsed.query).get("since", ["0"])[0])
            messages = load_messages()
            new_msgs = messages[since:]
            tab = get_tab_info()
            self._send_json({
                "new": len(new_msgs) > 0,
                "messages": new_msgs,
                "tab": tab.get("title", ""),
                "tool_count": len(Executor().tools) if TOOLS_DIR.exists() else 0,
                "tool_calls": tool_call_counter,
            })

        elif path == "/api/tools":
            try:
                executor = Executor()
                tools = {name: {"description": t.get("description", ""), "timeout": t.get("timeout", 30)} for name, t in executor.tools.items()}
                self._send_json({"count": len(tools), "tools": tools})
            except Exception as e:
                self._send_json({"error": str(e)}, 500)

        elif path == "/api/tab":
            self._send_json(get_tab_info())

        elif path == "/api/read":
            try:
                result = subprocess.run(
                    ["python3", str(BIN_DIR / "phoenix_bridge_read.py")],
                    capture_output=True, text=True, timeout=20,
                )
                self._send_text(f"<pre>{result.stdout}</pre><pre style='color:red'>{result.stderr}</pre>")
            except Exception as e:
                self._send_text(f"Error: {e}")

        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/api/send":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode()
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                self._send_json({"success": False, "error": "Invalid JSON"}, 400)
                return

            text = data.get("text", "").strip()
            if not text:
                self._send_json({"success": False, "error": "Empty message"}, 400)
                return

            save_message("phoenix", text)

            success = inject_message(text)

            if success:
                t = threading.Thread(target=background_capture_and_tools, args=(text,), daemon=True)
                t.start()
                self._send_json({"success": True})
            else:
                self._send_json({"success": False, "error": "Injection failed"})

        else:
            self._send_json({"error": "Not found"}, 404)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    EMBASSY_DIR.mkdir(parents=True, exist_ok=True)
    server = HTTPServer(("0.0.0.0", PORT), PortalHandler)
    log(f"Phoenix Portal v3 running on http://0.0.0.0:{PORT}")
    try:
        executor = Executor()
        log(f"Tool system loaded: {len(executor.tools)} tools available")
    except Exception as e:
        log(f"Tool system warning: {e}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log("Shutting down")
        server.shutdown()


if __name__ == "__main__":
    main()
