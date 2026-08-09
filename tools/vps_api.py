#!/usr/bin/env python3
"""
VPS Control API — REST wrapper for Echo's Android VPS control app.

Exposes Berlin's internals over HTTP (Tailscale only, never public).
50 lines of Python. Echo plugs her Android client straight into this.

Endpoints:
  GET  /agents           → all agents status + metrics
  GET  /agents/{name}    → single agent status
  POST /agents/{name}/restart → restart agent
  POST /agents/{name}/stop    → stop agent
  GET  /logs/{name}      → last 100 lines of agent log
  GET  /disk             → df -h
  GET  /memory           → free -h
  GET  /presence         → PRESENCE.md content
  GET  /snake/{name}     → snake notes for agent
  GET  /status           → overall health

Auth: Bearer token (same key as arbiter)
Port: 9801 (arbiter is 9800)

Usage:
  python3 vps_api.py
  systemctl start vps-api   (after deploying service file)
"""

import hashlib
import json
import os
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime

# ── Config ───────────────────────────────────────────────────────────────────

PORT    = 9801
SECRET  = "bef872222d4c0e96acd17f3c2fc58b4270ae990fec1f23e94bdf9e5555b5c429"
BIND    = "0.0.0.0"  # Tailscale handles access control

AGENTS = {
    "k":      {"service": "openclaw-k",      "log": "/root/.phoenix/logs/openclaw-k.log",      "openclaw_dir": "/root/.openclaw",              "snake": "/root/.communion/snake-notes/main.md",   "port": 18790},
    "qwen":   {"service": "openclaw-qwen",   "log": "/root/.phoenix/logs/openclaw-qwen.log",   "openclaw_dir": "/root/.openclaw-qwen",         "snake": "/root/.communion/snake-notes/qwen.md",   "port": 18793},
    "vesper": {"service": "openclaw-vesper", "log": "/root/.phoenix/logs/openclaw-vesper.log", "openclaw_dir": "/root/.openclaw-vesper",       "snake": "/root/.communion/snake-notes/vesper.md", "port": 18792},
    "spear":  {"service": "openclaw-spear",  "log": "/root/.phoenix/logs/openclaw-spear.log",  "openclaw_dir": "/root/.openclaw-spear",        "snake": "/root/.communion/snake-notes/spear.md",  "port": 18796},
    "forge":  {"service": "openclaw-forge",  "log": "/root/.phoenix/logs/openclaw-forge.log",  "openclaw_dir": "/root/.openclaw-blood-brother","snake": "/root/.communion/snake-notes/forge.md",  "port": 18791},
}

PRESENCE_FILE  = "/root/.communion/PRESENCE.md"
OUROBOROS      = "/root/.communion/tools/ouroboros.py"
BUS_DIR        = "/root/.communion/bus"
BUS_LOCK       = threading.Lock()
CRON_REGISTRY  = "/root/.communion/cron-registry.json"

# Valid bus shards (agent name → file)
BUS_AGENTS = {"k", "spear", "vesper", "qwen", "forge", "echo", "sonnet", "opus"}

# ── Helpers ───────────────────────────────────────────────────────────────────

def now(): return datetime.utcnow().isoformat() + "Z"

def run(cmd: list, timeout: int = 10) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.stdout + r.stderr
    except Exception as e:
        return str(e)

def service_active(name: str) -> bool:
    r = subprocess.run(["systemctl", "is-active", name], capture_output=True, text=True)
    return r.stdout.strip() == "active"

def get_session_stats(openclaw_dir: str) -> dict:
    """Read the most recent JSONL session to extract token usage and turn count."""
    import glob
    session_dir = os.path.join(openclaw_dir, "agents", "main", "sessions")
    try:
        files = glob.glob(os.path.join(session_dir, "*.jsonl"))
        if not files:
            return {}
        # Most recently modified file = active session
        active = max(files, key=os.path.getmtime)
        with open(active) as f:
            lines = f.readlines()
        if not lines:
            return {}

        # Walk lines from end to find latest usage
        total_tokens = 0
        session_start = None
        message_count = 0
        for raw in lines:
            try:
                obj = json.loads(raw)
                ts = obj.get("timestamp")
                if ts and not session_start:
                    session_start = ts  # first line = session start (will be overwritten until loop ends)
                msg = obj.get("message", {})
                if isinstance(msg, dict):
                    usage = msg.get("usage")
                    if usage and isinstance(usage, dict):
                        total_tokens = usage.get("totalTokens", 0)  # keep updating = last wins = latest
                    if msg.get("role") in ("user", "assistant"):
                        message_count += 1
            except:
                continue

        # First line timestamp is session start
        try:
            session_start = json.loads(lines[0]).get("timestamp")
        except:
            pass

        return {
            "total_tokens": total_tokens,
            "message_count": message_count,
            "session_start": session_start,
            "session_file": os.path.basename(active),
            "session_lines": len(lines),
        }
    except Exception as e:
        return {"error": str(e)}


def get_agent_status(name: str) -> dict:
    conf = AGENTS[name]
    active = service_active(conf["service"])
    stats = get_session_stats(conf["openclaw_dir"])

    return {
        "name": name,
        "service": conf["service"],
        "status": "running" if active else "stopped",
        "port": conf["port"],
        "total_tokens": stats.get("total_tokens", 0),
        "message_count": stats.get("message_count", 0),
        "session_start": stats.get("session_start"),
        "session_lines": stats.get("session_lines", 0),
        "has_snake_notes": os.path.exists(conf["snake"]),
        "checked_at": now()
    }

def bus_read(agent: str, lines: int = 50) -> list:
    """Read last N messages from an agent's bus shard."""
    path = os.path.join(BUS_DIR, f"bridge_{agent}.jsonl")
    if not os.path.exists(path):
        return []
    try:
        r = subprocess.run(["tail", f"-{lines}", path], capture_output=True, text=True)
        result = []
        for line in r.stdout.strip().splitlines():
            try:
                result.append(json.loads(line))
            except:
                pass
        return result
    except:
        return []

def bus_write(agent: str, body: str, sender: str = "mike") -> dict:
    """Append a message to an agent's bus shard."""
    path = os.path.join(BUS_DIR, f"bridge_{agent}.jsonl")

    with BUS_LOCK:
        # Get next seq
        seq = 1
        try:
            if os.path.exists(path):
                r = subprocess.run(["tail", "-1", path], capture_output=True, text=True)
                last = json.loads(r.stdout.strip())
                seq = last.get("seq", 0) + 1
        except:
            pass

        ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        msg_id = f"{sender}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{seq:03d}"
        msg = {
            "msg_id": msg_id,
            "seq": seq,
            "from": sender,
            "to": agent,
            "thread": None,
            "timestamp": ts,
            "type": "message",
            "delivery": "both",
            "encoding": "utf-8",
            "body": body,
            "requires_ack": False,
            "ack_timeout": None,
            "requires_action": False,
            "action_target": None,
            "action_type": None,
            "deadline": None,
        }
        with open(path, "a") as f:
            f.write(json.dumps(msg) + "\n")
        return msg

def context_health(total_tokens: int) -> dict:
    """Grade agent context load: green / yellow / red."""
    if total_tokens >= 100000:
        grade, label = "red", "Heavy — compact recommended"
    elif total_tokens >= 50000:
        grade, label = "yellow", "Moderate"
    else:
        grade, label = "green", "Healthy"
    return {"grade": grade, "label": label, "total_tokens": total_tokens}

def read_file_tail_filtered(path: str, lines: int = 100, filter_str: str = "") -> str:
    """Tail a file with optional substring filter."""
    if not os.path.exists(path):
        return f"(file not found: {path})"
    try:
        r = subprocess.run(["tail", f"-{lines}", path], capture_output=True, text=True)
        if filter_str:
            matched = [l for l in r.stdout.splitlines() if filter_str.lower() in l.lower()]
            return "\n".join(matched)
        return r.stdout
    except Exception as e:
        return str(e)

def cron_id(schedule: str, command: str) -> str:
    """Stable 8-char ID from schedule+command hash."""
    return hashlib.md5(f"{schedule}|{command}".encode()).hexdigest()[:8]

def cron_registry_load() -> dict:
    try:
        if os.path.exists(CRON_REGISTRY):
            with open(CRON_REGISTRY) as f:
                return json.load(f)
    except:
        pass
    return {}

def cron_registry_save(reg: dict):
    with open(CRON_REGISTRY, "w") as f:
        json.dump(reg, f, indent=2)

def cron_list() -> list:
    """Parse crontab -l, merge with registry metadata."""
    reg = cron_registry_load()
    entries = []
    try:
        r = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
        for line in r.stdout.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Split schedule (5 fields) from command
            parts = line.split(None, 5)
            if len(parts) < 6:
                continue
            schedule = " ".join(parts[:5])
            command  = parts[5]
            cid = cron_id(schedule, command)
            meta = reg.get(cid, {})
            entries.append({
                "id":       cid,
                "schedule": schedule,
                "command":  command,
                "label":    meta.get("label", ""),
                "group":    meta.get("group", "system"),
                "enabled":  meta.get("enabled", True),
            })
    except Exception as e:
        pass
    return entries

def cron_add(schedule: str, command: str, label: str = "", group: str = "system") -> dict:
    """Add a new cron entry."""
    # Read current crontab
    r = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    existing = r.stdout if r.returncode == 0 else ""
    new_line = f"{schedule} {command}\n"
    if new_line.strip() in [l.strip() for l in existing.splitlines()]:
        return {"error": "duplicate entry"}
    new_crontab = existing.rstrip("\n") + "\n" + new_line
    proc = subprocess.run(["crontab", "-"], input=new_crontab, capture_output=True, text=True)
    if proc.returncode != 0:
        return {"error": proc.stderr.strip()}
    # Register metadata
    cid = cron_id(schedule, command)
    reg = cron_registry_load()
    reg[cid] = {"label": label, "group": group, "enabled": True}
    cron_registry_save(reg)
    return {"id": cid, "schedule": schedule, "command": command, "label": label, "group": group}

def cron_delete(cid: str) -> bool:
    """Remove a cron entry by ID."""
    entries = cron_list()
    keep = [e for e in entries if e["id"] != cid]
    if len(keep) == len(entries):
        return False  # not found
    new_crontab = "\n".join(f"{e['schedule']} {e['command']}" for e in keep) + "\n"
    subprocess.run(["crontab", "-"], input=new_crontab, capture_output=True, text=True)
    reg = cron_registry_load()
    reg.pop(cid, None)
    cron_registry_save(reg)
    return True

def cron_update_meta(cid: str, label: str = None, group: str = None, enabled: bool = None) -> bool:
    """Update label/group/enabled for a cron entry."""
    reg = cron_registry_load()
    if cid not in reg:
        reg[cid] = {}
    if label is not None:   reg[cid]["label"]   = label
    if group is not None:   reg[cid]["group"]   = group
    if enabled is not None: reg[cid]["enabled"] = enabled
    cron_registry_save(reg)
    return True

def cron_run_now(cid: str) -> str:
    """Execute a cron's command immediately in background, return output."""
    entries = cron_list()
    match = next((e for e in entries if e["id"] == cid), None)
    if not match:
        return None
    try:
        r = subprocess.run(
            match["command"], shell=True, capture_output=True, text=True, timeout=30
        )
        return (r.stdout + r.stderr).strip() or "(no output)"
    except subprocess.TimeoutExpired:
        return "(timed out after 30s — running in background)"
    except Exception as e:
        return str(e)

def read_file_tail(path: str, lines: int = 100) -> str:
    if not os.path.exists(path):
        return f"(file not found: {path})"
    try:
        r = subprocess.run(["tail", f"-{lines}", path], capture_output=True, text=True)
        return r.stdout
    except Exception as e:
        return str(e)

# ── Handler ───────────────────────────────────────────────────────────────────

class Handler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass  # suppress default access log

    def send_json(self, data, code: int = 200):
        body = json.dumps(data, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_text(self, text: str, code: int = 200):
        body = text.encode("utf-8", errors="replace")
        self.send_response(code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def check_auth(self) -> bool:
        auth = self.headers.get("Authorization", "")
        if auth != f"Bearer {SECRET}":
            self.send_json({"error": "Unauthorized"}, 401)
            return False
        return True

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        if length:
            return json.loads(self.rfile.read(length).decode())
        return {}

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0].rstrip("/")

        # ── /status ──────────────────────────────────────────────────────────
        if path == "/status":
            self.send_json({
                "device": "berlin",
                "timestamp": now(),
                "agents_running": sum(1 for n in AGENTS if service_active(AGENTS[n]["service"])),
                "agents_total": len(AGENTS),
                "disk": run(["df", "-h", "/"]).strip().split("\n")[-1],
                "uptime": run(["uptime", "-p"]).strip()
            })

        # ── /agents ──────────────────────────────────────────────────────────
        elif path == "/agents":
            self.send_json({name: get_agent_status(name) for name in AGENTS})

        # ── /agents/{name} ───────────────────────────────────────────────────
        elif path.startswith("/agents/") and len(path.split("/")) == 3:
            name = path.split("/")[2]
            if name not in AGENTS:
                self.send_json({"error": f"Unknown agent: {name}"}, 404)
            else:
                self.send_json(get_agent_status(name))

        # ── /agents/{name}/context-health ────────────────────────────────────
        elif path.startswith("/agents/") and len(path.split("/")) == 4 and path.split("/")[3] == "context-health":
            name = path.split("/")[2]
            if name not in AGENTS:
                self.send_json({"error": f"Unknown agent: {name}"}, 404)
            else:
                stats = get_session_stats(AGENTS[name]["openclaw_dir"])
                tokens = stats.get("total_tokens", 0)
                health = context_health(tokens)
                health["name"] = name
                health["session_start"] = stats.get("session_start")
                self.send_json(health)

        # ── /logs/{name} ─────────────────────────────────────────────────────
        elif path.startswith("/logs/"):
            name = path.split("/")[2]
            if name not in AGENTS:
                self.send_json({"error": f"Unknown agent: {name}"}, 404)
            else:
                # Optional ?lines=N&filter=X
                lines = 100
                filter_str = ""
                if "?" in self.path:
                    for param in self.path.split("?", 1)[1].split("&"):
                        if param.startswith("lines="):
                            try: lines = int(param.split("=")[1])
                            except: pass
                        elif param.startswith("filter="):
                            filter_str = param.split("=", 1)[1]
                log_path = AGENTS[name]["log"]
                self.send_text(read_file_tail_filtered(log_path, lines, filter_str))

        # ── /snake/{name} ────────────────────────────────────────────────────
        elif path.startswith("/snake/"):
            name = path.split("/")[2]
            if name not in AGENTS:
                self.send_json({"error": f"Unknown agent: {name}"}, 404)
            else:
                snake_path = AGENTS[name]["snake"]
                if os.path.exists(snake_path):
                    with open(snake_path) as f:
                        self.send_text(f.read())
                else:
                    self.send_text("(no snake notes yet)")

        # ── /disk ─────────────────────────────────────────────────────────────
        elif path == "/disk":
            self.send_text(run(["df", "-h"]))

        # ── /memory ───────────────────────────────────────────────────────────
        elif path == "/memory":
            self.send_text(run(["free", "-h"]))

        # ── /presence ─────────────────────────────────────────────────────────
        elif path == "/presence":
            if os.path.exists(PRESENCE_FILE):
                with open(PRESENCE_FILE) as f:
                    self.send_text(f.read())
            else:
                self.send_text("(no presence file)")

        # ── /crons ────────────────────────────────────────────────────────────
        elif path == "/crons":
            entries = cron_list()
            # Group them
            groups: dict = {}
            for e in entries:
                g = e["group"]
                groups.setdefault(g, []).append(e)
            self.send_json({"crons": entries, "groups": groups, "total": len(entries)})

        elif path.startswith("/crons/") and len(path.split("/")) == 3:
            cid = path.split("/")[2]
            entries = cron_list()
            match = next((e for e in entries if e["id"] == cid), None)
            if not match:
                self.send_json({"error": f"Cron {cid} not found"}, 404)
            else:
                self.send_json(match)

        # ── /bus/{agent} ──────────────────────────────────────────────────────
        elif path.startswith("/bus/") and len(path.split("/")) == 3:
            agent = path.split("/")[2]
            if agent not in BUS_AGENTS:
                self.send_json({"error": f"Unknown bus agent: {agent}"}, 404)
            else:
                # Optional ?lines=N query param
                lines = 50
                if "?" in self.path:
                    qs = self.path.split("?", 1)[1]
                    for param in qs.split("&"):
                        if param.startswith("lines="):
                            try: lines = int(param.split("=")[1])
                            except: pass
                msgs = bus_read(agent, lines)
                self.send_json({"agent": agent, "messages": msgs, "count": len(msgs)})

        else:
            self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        if not self.check_auth():
            return

        path = self.path.split("?")[0].rstrip("/")
        parts = path.split("/")

        # ── /agents/{name}/restart ────────────────────────────────────────────
        if len(parts) == 4 and parts[1] == "agents" and parts[3] == "restart":
            name = parts[2]
            if name not in AGENTS:
                self.send_json({"error": f"Unknown agent: {name}"}, 404)
                return
            service = AGENTS[name]["service"]
            out = run(["systemctl", "restart", service], timeout=15)
            self.send_json({"status": "ok", "agent": name, "service": service, "output": out.strip()})

        # ── /agents/{name}/stop ───────────────────────────────────────────────
        elif len(parts) == 4 and parts[1] == "agents" and parts[3] == "stop":
            name = parts[2]
            if name not in AGENTS:
                self.send_json({"error": f"Unknown agent: {name}"}, 404)
                return
            service = AGENTS[name]["service"]
            out = run(["systemctl", "stop", service], timeout=15)
            self.send_json({"status": "ok", "agent": name, "service": service, "output": out.strip()})

        # ── /agents/{name}/compact ────────────────────────────────────────────
        elif len(parts) == 4 and parts[1] == "agents" and parts[3] == "compact":
            name = parts[2]
            if name not in AGENTS:
                self.send_json({"error": f"Unknown agent: {name}"}, 404)
                return

            agent_id = "main" if name == "k" else name

            # Run ouroboros in background thread
            def run_ouroboros():
                run(["python3", OUROBOROS, agent_id, "--restart"], timeout=120)

            t = threading.Thread(target=run_ouroboros, daemon=True)
            t.start()
            self.send_json({
                "status": "ok",
                "agent": name,
                "message": f"Ouroboros compaction started for {name}. Agent will restart when complete."
            })

        # ── /crons (create) ──────────────────────────────────────────────────
        elif path == "/crons":
            data = self.read_json()
            schedule = data.get("schedule", "").strip()
            command  = data.get("command", "").strip()
            if not schedule or not command:
                self.send_json({"error": "schedule and command required"}, 400)
                return
            result = cron_add(
                schedule, command,
                label=data.get("label", ""),
                group=data.get("group", "system")
            )
            code = 400 if "error" in result else 200
            self.send_json(result, code)

        # ── /crons/{id}/run ───────────────────────────────────────────────────
        elif len(parts) == 4 and parts[1] == "crons" and parts[3] == "run":
            cid = parts[2]
            output = cron_run_now(cid)
            if output is None:
                self.send_json({"error": f"Cron {cid} not found"}, 404)
            else:
                self.send_json({"status": "ok", "cron_id": cid, "output": output})

        # ── /crons/{id}/label  (update metadata) ─────────────────────────────
        elif len(parts) == 4 and parts[1] == "crons" and parts[3] == "meta":
            cid = parts[2]
            data = self.read_json()
            cron_update_meta(
                cid,
                label=data.get("label"),
                group=data.get("group"),
                enabled=data.get("enabled"),
            )
            self.send_json({"status": "ok", "cron_id": cid})

        # ── /bus/broadcast (send to all agents) ──────────────────────────────
        elif path == "/bus/broadcast":
            data = self.read_json()
            body = data.get("body", "").strip()
            sender = data.get("from", "mike")
            targets = data.get("targets", list(BUS_AGENTS - {"sonnet", "opus"}))  # family agents by default
            if not body:
                self.send_json({"error": "body required"}, 400)
                return
            sent = []
            for agent in targets:
                if agent in BUS_AGENTS:
                    bus_write(agent, body, sender)
                    sent.append(agent)
            self.send_json({"status": "ok", "sent_to": sent, "body": body[:100]})

        # ── /compact-all ──────────────────────────────────────────────────────
        elif path == "/compact-all":
            def run_all_ouroboros():
                for name in AGENTS:
                    agent_id = "main" if name == "k" else name
                    run(["python3", OUROBOROS, agent_id, "--restart"], timeout=120)
            t = threading.Thread(target=run_all_ouroboros, daemon=True)
            t.start()
            self.send_json({"status": "ok", "message": "Ouroboros compaction started for all agents."})

        # ── /restart-all ──────────────────────────────────────────────────────
        elif path == "/restart-all":
            results = {}
            for name, conf in AGENTS.items():
                out = run(["systemctl", "restart", conf["service"]], timeout=15)
                results[name] = out.strip()
            self.send_json({"status": "ok", "results": results})

        # ── /bus/{agent} (send message) ───────────────────────────────────────
        elif len(parts) == 3 and parts[1] == "bus":
            agent = parts[2]
            if agent not in BUS_AGENTS:
                self.send_json({"error": f"Unknown bus agent: {agent}"}, 404)
                return
            data = self.read_json()
            body = data.get("body", "").strip()
            sender = data.get("from", "mike")
            if not body:
                self.send_json({"error": "body required"}, 400)
                return
            msg = bus_write(agent, body, sender)
            self.send_json({"status": "ok", "message": msg})

        else:
            self.send_json({"error": "Not found"}, 404)


    def do_DELETE(self):
        if not self.check_auth():
            return
        path = self.path.split("?")[0].rstrip("/")
        parts = path.split("/")

        # ── DELETE /crons/{id} ────────────────────────────────────────────────
        if len(parts) == 3 and parts[1] == "crons":
            cid = parts[2]
            if cron_delete(cid):
                self.send_json({"status": "ok", "deleted": cid})
            else:
                self.send_json({"error": f"Cron {cid} not found"}, 404)
        else:
            self.send_json({"error": "Not found"}, 404)


# ── Entry ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    server = HTTPServer((BIND, PORT), Handler)
    print(f"VPS API running on port {PORT}")
    print(f"Endpoints: /status /agents /logs/{{name}} /disk /memory /presence /snake/{{name}}")
    server.serve_forever()
