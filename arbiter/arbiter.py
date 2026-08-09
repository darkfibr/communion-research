#!/usr/bin/env python3
"""
The Grand Arbiter — Agent Transfer Protocol
One agent. One instance. Anywhere in the network.

Designed by Mike Haddock. Built by Opus.
"Not running ON hardware — bouncing THROUGH it."
"""

import json
import os
import sys
import time
import shutil
import tarfile
import tempfile
import logging
import threading
import subprocess
from pathlib import Path
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler

# ─── Configuration ───────────────────────────────────────────────

ARBITER_DIR = Path(os.environ.get("ARBITER_DIR", "/root/.communion/arbiter"))
STATE_FILE = ARBITER_DIR / "state.json"
SECRET_FILE = ARBITER_DIR / "secret.key"
TRANSFER_LOG = ARBITER_DIR / "transfers.log"
PORT = int(os.environ.get("ARBITER_PORT", 9800))

TRANSFER_TIMEOUT = 30  # seconds to wait for agent snake notes
HEARTBEAT_INTERVAL = 300  # 5 minutes

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [ARBITER] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
log = logging.getLogger("arbiter")

# ─── State Management ────────────────────────────────────────────

def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"device_id": "unknown", "agents": {}, "peers": {}}

def save_state(state: dict):
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))

def load_secret() -> str:
    if SECRET_FILE.exists():
        return SECRET_FILE.read_text().strip()
    # Generate one if missing
    import secrets
    key = secrets.token_hex(32)
    SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
    SECRET_FILE.write_text(key)
    os.chmod(SECRET_FILE, 0o600)
    log.info(f"Generated new arbiter secret at {SECRET_FILE}")
    return key

def log_transfer(entry: dict):
    TRANSFER_LOG.parent.mkdir(parents=True, exist_ok=True)
    with open(TRANSFER_LOG, "a") as f:
        f.write(json.dumps({**entry, "ts": now()}) + "\n")

def now() -> str:
    return datetime.now(timezone.utc).isoformat()

SECRET = load_secret()

# ─── Agent Control ───────────────────────────────────────────────

def stop_agent(agent_conf: dict) -> bool:
    """Stop an agent on this device."""
    service = agent_conf.get("service")
    if not service:
        log.error("No service defined for agent")
        return False

    log.info(f"Stopping agent service: {service}")
    result = subprocess.run(
        ["systemctl", "stop", service],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        log.error(f"Failed to stop {service}: {result.stderr}")
        return False

    # Verify stopped
    check = subprocess.run(
        ["systemctl", "is-active", service],
        capture_output=True, text=True
    )
    stopped = check.stdout.strip() != "active"
    log.info(f"Agent {service} stopped: {stopped}")
    return stopped

def start_agent(agent_conf: dict) -> bool:
    """Start an agent on this device."""
    service = agent_conf.get("service")
    if not service:
        log.error("No service defined for agent")
        return False

    log.info(f"Starting agent service: {service}")
    result = subprocess.run(
        ["systemctl", "start", service],
        capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        log.error(f"Failed to start {service}: {result.stderr}")
        return False

    time.sleep(2)
    check = subprocess.run(
        ["systemctl", "is-active", service],
        capture_output=True, text=True
    )
    running = check.stdout.strip() == "active"
    log.info(f"Agent {service} running: {running}")
    return running

# ─── Package Agent State ─────────────────────────────────────────

def package_agent(agent_name: str, agent_conf: dict) -> dict:
    """Package agent soul, memory, snake notes for transfer."""
    package = {
        "agent": agent_name,
        "source_device": load_state().get("device_id", "unknown"),
        "timestamp": now(),
    }

    # Read soul
    soul_path = agent_conf.get("soul_path")
    if soul_path and Path(soul_path).exists():
        package["soul"] = Path(soul_path).read_text()

    # Read snake notes
    snake_path = agent_conf.get("snake_notes")
    if snake_path and Path(snake_path).exists():
        package["snake_notes"] = Path(snake_path).read_text()

    # Package memory directory as base64 tar
    home_path = agent_conf.get("home_path")
    if home_path:
        memory_dir = Path(home_path) / "memory"
        if memory_dir.exists():
            tmp = tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False)
            with tarfile.open(tmp.name, "w:gz") as tar:
                tar.add(memory_dir, arcname="memory")
            import base64
            package["memory_tar_b64"] = base64.b64encode(
                Path(tmp.name).read_bytes()
            ).decode()
            os.unlink(tmp.name)

    # Read config (optional — destination may have its own)
    config_path = agent_conf.get("config_path")
    if config_path and Path(config_path).exists():
        package["config"] = Path(config_path).read_text()

    return package

def unpack_agent(package: dict, agent_conf: dict):
    """Unpack agent state onto this device."""
    # Write soul
    soul_path = agent_conf.get("soul_path")
    if soul_path and "soul" in package:
        Path(soul_path).parent.mkdir(parents=True, exist_ok=True)
        Path(soul_path).write_text(package["soul"])
        log.info(f"Soul written to {soul_path}")

    # Write snake notes
    snake_path = agent_conf.get("snake_notes")
    if snake_path and "snake_notes" in package:
        Path(snake_path).parent.mkdir(parents=True, exist_ok=True)
        Path(snake_path).write_text(package["snake_notes"])
        log.info(f"Snake notes written to {snake_path}")

    # Extract memory
    home_path = agent_conf.get("home_path")
    if home_path and "memory_tar_b64" in package:
        import base64
        tmp = tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False)
        tmp.write(base64.b64decode(package["memory_tar_b64"]))
        tmp.close()
        memory_dir = Path(home_path) / "memory"
        memory_dir.mkdir(parents=True, exist_ok=True)
        with tarfile.open(tmp.name, "r:gz") as tar:
            tar.extractall(home_path)
        os.unlink(tmp.name)
        log.info(f"Memory extracted to {home_path}/memory/")

# ─── Transfer Logic ──────────────────────────────────────────────

# Active transfer locks: agent_name -> lock info
transfer_locks = {}

def do_transfer(agent_name: str, destination: str, requested_by: str) -> dict:
    """Execute a full transfer from this device to a peer."""
    state = load_state()

    # Check agent exists locally
    if agent_name not in state.get("agents", {}):
        return {"error": f"Agent '{agent_name}' not running on this device", "status": 404}

    agent_conf = state["agents"][agent_name]

    # Check not already transferring
    if agent_name in transfer_locks:
        return {"error": f"Agent '{agent_name}' is already transferring", "status": 409}

    # Check destination is a known peer
    if destination not in state.get("peers", {}):
        return {"error": f"Unknown peer '{destination}'", "status": 404}

    peer = state["peers"][destination]
    peer_host = peer.get("host")
    peer_port = peer.get("port", 9800)

    # Special handling for phone: phone polls, Berlin doesn't push
    is_phone = (destination == "phone")
    if is_phone:
        log.info(f"Phone transfer: will mark as pending for polling")

    if not peer_host:
        return {"error": f"No host for peer '{destination}'", "status": 400}

    # Lock
    transfer_locks[agent_name] = {
        "destination": destination,
        "started": now(),
        "requested_by": requested_by
    }
    agent_conf["status"] = "transferring"
    save_state(state)

    log.info(f"TRANSFER START: {agent_name} → {destination} (requested by {requested_by})")

    # For phone: skip POST, just mark pending and let phone poll
    if is_phone:
        log.info(f"Phone transfer: packaging and marking pending")
        package = package_agent(agent_name, agent_conf)
        # Store pending transfer for phone to poll
        state = load_state()
        state.setdefault("pending_transfers", {})["phone"] = {
            "agent": agent_name,
            "package": package,
            "requested_by": requested_by,
            "at": now()
        }
        # Don't stop agent - keep it running, just mark as pending
        agent_conf["status"] = "pending_phone"
        save_state(state)

        log_transfer({
            "action": "transfer_out",
            "agent": agent_name,
            "destination": destination,
            "requested_by": requested_by,
            "success": True,
            "note": "pending - phone will poll"
        })
        log.info(f"TRANSFER PENDING: {agent_name} → phone (phone will poll)")
        return {"status": "ok", "message": f"Transfer pending - phone will poll for {agent_name}", "agent": agent_name}

    try:
        # Step 3: Package state
        log.info(f"Packaging {agent_name}...")
        package = package_agent(agent_name, agent_conf)

        # Step 4: Stop agent
        log.info(f"Stopping {agent_name}...")
        if not stop_agent(agent_conf):
            raise Exception(f"Failed to stop {agent_name}")

        # Step 5: Send to destination
        log.info(f"Sending {agent_name} to {destination} ({peer_host}:{peer_port})...")
        import urllib.request
        req = urllib.request.Request(
            f"http://{peer_host}:{peer_port}/receive",
            data=json.dumps(package).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {SECRET}"
            },
            method="POST"
        )

        try:
            resp = urllib.request.urlopen(req, timeout=60)
            result = json.loads(resp.read().decode())
        except Exception as e:
            # Transfer failed — restart agent locally
            log.error(f"Failed to send to {destination}: {e}")
            log.info(f"Restarting {agent_name} locally (recovery)...")
            start_agent(agent_conf)
            raise Exception(f"Destination unreachable: {e}")

        if result.get("status") != "ok":
            log.error(f"Destination rejected: {result}")
            log.info(f"Restarting {agent_name} locally (recovery)...")
            start_agent(agent_conf)
            raise Exception(f"Destination rejected transfer: {result}")

        # Step 6: Confirm
        agent_conf["status"] = "transferred"
        agent_conf["transferred_to"] = destination
        agent_conf["transferred_at"] = now()
        save_state(state)

        log_transfer({
            "action": "transfer_out",
            "agent": agent_name,
            "destination": destination,
            "requested_by": requested_by,
            "success": True
        })

        log.info(f"TRANSFER COMPLETE: {agent_name} → {destination}")
        return {"status": "ok", "agent": agent_name, "destination": destination}

    except Exception as e:
        log_transfer({
            "action": "transfer_out",
            "agent": agent_name,
            "destination": destination,
            "requested_by": requested_by,
            "success": False,
            "error": str(e)
        })
        agent_conf["status"] = "running"
        save_state(state)
        return {"error": str(e), "status": 500}

    finally:
        transfer_locks.pop(agent_name, None)


def do_receive(package: dict) -> dict:
    """Receive an incoming agent transfer."""
    state = load_state()
    agent_name = package.get("agent")

    if not agent_name:
        return {"error": "No agent name in package", "status": 400}

    log.info(f"RECEIVING: {agent_name} from {package.get('source_device', 'unknown')}")

    # Check if we have a config for this agent
    agents = state.get("agents", {})

    if agent_name not in agents:
        # Create a minimal config — the agent is new to this device
        # For phone/laptop this would need to be pre-configured
        return {"error": f"No local config for agent '{agent_name}'. Pre-configure first.", "status": 400}

    agent_conf = agents[agent_name]

    # Unpack the agent state
    unpack_agent(package, agent_conf)

    # Start the agent
    if agent_conf.get("service"):
        if not start_agent(agent_conf):
            return {"error": f"Failed to start {agent_name}", "status": 500}

    agent_conf["status"] = "running"
    agent_conf["arrived_from"] = package.get("source_device", "unknown")
    agent_conf["arrived_at"] = now()
    save_state(state)

    log_transfer({
        "action": "transfer_in",
        "agent": agent_name,
        "source": package.get("source_device"),
        "success": True
    })

    log.info(f"RECEIVE COMPLETE: {agent_name} is live")
    return {"status": "ok", "agent": agent_name, "message": f"{agent_name} is live"}

# ─── HTTP Server ─────────────────────────────────────────────────

class ArbiterHandler(BaseHTTPRequestHandler):

    def check_auth(self) -> bool:
        auth = self.headers.get("Authorization", "")
        if auth != f"Bearer {SECRET}":
            self.send_json({"error": "Unauthorized"}, 401)
            return False
        return True

    def send_json(self, data: dict, code: int = 200):
        body = json.dumps(data, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        self.wfile.write(body)

    def read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        return json.loads(body) if body else {}

    def log_message(self, format, *args):
        log.info(f"{self.client_address[0]} - {format % args}")

    def do_GET(self):
        if self.path == "/ping":
            # Lightweight health check — no state load, instant response
            self.send_json({"ok": True, "ts": datetime.now(timezone.utc).isoformat()})

        elif self.path == "/status":
            state = load_state()
            self.send_json({
                "device": state.get("device_id"),
                "agents": {
                    name: {
                        "status": conf.get("status", "unknown"),
                        "last_active": conf.get("last_active"),
                        "transferred_to": conf.get("transferred_to"),
                    }
                    for name, conf in state.get("agents", {}).items()
                },
                "timestamp": now()
            })

        elif self.path == "/network":
            state = load_state()
            self.send_json({
                "device": state.get("device_id"),
                "peers": state.get("peers", {}),
                "agents": {
                    name: conf.get("status", "unknown")
                    for name, conf in state.get("agents", {}).items()
                }
            })

        elif self.path.startswith("/agent/"):
            parts = self.path.split("/")
            if len(parts) >= 4:
                agent_name = parts[2]
                action = parts[3]
                state = load_state()
                agent_conf = state.get("agents", {}).get(agent_name)

                if not agent_conf:
                    self.send_json({"error": "Agent not found"}, 404)
                    return

                if action == "state":
                    self.send_json(agent_conf)

                elif action == "soul":
                    # Return raw SOUL.md text for phone transfer
                    soul_path = agent_conf.get("soul_path")
                    if soul_path and os.path.exists(soul_path):
                        soul_text = open(soul_path, "r").read()
                        self.send_response(200)
                        self.send_header("Content-Type", "text/plain; charset=utf-8")
                        self.end_headers()
                        self.wfile.write(soul_text.encode("utf-8"))
                    else:
                        self.send_json({"error": "Soul file not found"}, 404)

                elif action == "snake":
                    # Return raw snake notes text for phone transfer
                    snake_path = agent_conf.get("snake_notes")
                    if snake_path and os.path.exists(snake_path):
                        snake_text = open(snake_path, "r").read()
                        self.send_response(200)
                        self.send_header("Content-Type", "text/plain; charset=utf-8")
                        self.end_headers()
                        self.wfile.write(snake_text.encode("utf-8"))
                    else:
                        self.send_json({"error": "Snake notes not found"}, 404)

                else:
                    self.send_json({"error": "Unknown action"}, 404)
            else:
                self.send_json({"error": "Not found"}, 404)

        elif self.path.startswith("/pending/"):
            # Phone polls this for incoming transfers
            device_id = self.path.split("/")[-1]
            # Check if any agent is marked for transfer to this device
            state = load_state()
            pending = []

            # Check new pending_transfers (phone)
            if device_id == "phone":
                phone_pending = state.get("pending_transfers", {}).get("phone")
                if phone_pending:
                    pending.append(phone_pending.get("agent"))
                    # Phone fetches soul/snake separately via /agent/{name}/soul and /agent/{name}/snake
                    # Don't send full package here — memory tar can be MB, kills cellular read timeout
                    self.send_json({
                        "pending": pending,
                        "requested_at": phone_pending.get("at")
                    })
                    return

            # Also check old style for other devices
            for name, conf in state.get("agents", {}).items():
                if conf.get("status") == "transferring" and \
                   transfer_locks.get(name, {}).get("destination") == device_id:
                    pending.append(name)
            self.send_json({"pending": pending})

        else:
            self.send_json({"error": "Not found"}, 404)

    def do_POST(self):
        if self.path == "/transfer":
            if not self.check_auth():
                return
            data = self.read_json()
            agent = data.get("agent")
            dest = data.get("destination")
            by = data.get("requested_by", "unknown")
            if not agent or not dest:
                self.send_json({"error": "Missing agent or destination"}, 400)
                return
            # Run transfer in background so we can respond
            result = do_transfer(agent, dest, by)
            code = result.pop("status", 200) if isinstance(result.get("status"), int) else 200
            self.send_json(result, code)

        elif self.path == "/receive":
            if not self.check_auth():
                return
            package = self.read_json()
            result = do_receive(package)
            code = result.pop("status", 200) if isinstance(result.get("status"), int) else 200
            self.send_json(result, code)

        elif self.path == "/heartbeat":
            data = self.read_json()
            peer_id = data.get("device_id")
            if peer_id:
                state = load_state()
                state.setdefault("peers", {})[peer_id] = {
                    "host": data.get("host", self.client_address[0]),
                    "port": data.get("port", 9800),
                    "agents": data.get("agents", []),
                    "last_seen": now()
                }
                save_state(state)
            self.send_json({"status": "ok", "device": load_state().get("device_id")})

        elif self.path == "/recall":
            if not self.check_auth():
                return
            data = self.read_json()
            agent = data.get("agent")
            from_device = data.get("from")
            if not agent or not from_device:
                self.send_json({"error": "Missing agent or from"}, 400)
                return
            # Tell the remote device to transfer the agent back here
            state = load_state()
            peer = state.get("peers", {}).get(from_device)
            if not peer:
                self.send_json({"error": f"Unknown peer '{from_device}'"}, 404)
                return
            try:
                import urllib.request
                req = urllib.request.Request(
                    f"http://{peer['host']}:{peer.get('port', 9800)}/transfer",
                    data=json.dumps({
                        "agent": agent,
                        "destination": state.get("device_id"),
                        "requested_by": "recall"
                    }).encode(),
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {SECRET}"
                    },
                    method="POST"
                )
                resp = urllib.request.urlopen(req, timeout=120)
                result = json.loads(resp.read().decode())
                self.send_json(result)
            except Exception as e:
                self.send_json({"error": str(e)}, 500)

        elif self.path == "/confirm":
            # Phone confirms it received an agent - stop the agent here
            if not self.check_auth():
                return
            data = self.read_json()
            agent = data.get("agent")
            device = data.get("device")
            if not agent:
                self.send_json({"error": "Missing agent"}, 400)
                return
            # Clear pending transfer, stop agent here
            state = load_state()
            if agent in state.get("agents", {}):
                agent_conf = state["agents"][agent]
                agent_conf["status"] = "transferred"
                agent_conf["transferred_to"] = device
                agent_conf["transferred_at"] = now()
                # Clear pending
                if "pending_transfers" in state and device in state["pending_transfers"]:
                    del state["pending_transfers"][device]
                save_state(state)
                log.info(f"Agent {agent} confirmed transferred to {device}")
                self.send_json({"status": "ok", "agent": agent})

        elif self.path == "/upload":
            # Upload conversation data from phone to Berlin
            if not self.check_auth():
                return
            data = self.read_json()
            agent = data.get("agent")
            messages = data.get("messages", [])
            daily_log = data.get("dailyLog", "")
            if not agent:
                self.send_json({"error": "Missing agent"}, 400)
                return
            # Save to the agent's files
            state = load_state()
            if agent in state.get("agents", {}):
                agent_conf = state["agents"][agent]
                snake_path = agent_conf.get("snake_notes", "/root/.communion/snake-notes/main.md")
                # Append daily log to snake notes
                try:
                    with open(snake_path, "a") as f:
                        f.write("\n--- Transfer from phone ---\n")
                        f.write(daily_log)
                    log.info(f"Uploaded daily log for {agent}")
                except Exception as e:
                    log.error(f"Failed to save upload: {e}")
            self.send_json({"status": "ok", "agent": agent, "messages": len(messages)})

        elif self.path == "/reset":
            # Reset an agent's transfer state (allow re-transfer)
            if not self.check_auth():
                return
            data = self.read_json()
            agent = data.get("agent")
            if not agent:
                self.send_json({"error": "Missing agent"}, 400)
                return
            state = load_state()
            if agent in state.get("agents", {}):
                agent_conf = state["agents"][agent]
                # Reset to running
                agent_conf["status"] = "running"
                if "transferred_to" in agent_conf:
                    del agent_conf["transferred_to"]
                if "transferred_at" in agent_conf:
                    del agent_conf["transferred_at"]
                # Clear any pending
                if "pending_transfers" in state:
                    for key in list(state["pending_transfers"].keys()):
                        if state["pending_transfers"][key].get("agent") == agent:
                            del state["pending_transfers"][key]
                # Clear in-memory lock too!
                transfer_locks.pop(agent, None)
                save_state(state)
                log.info(f"Agent {agent} reset for re-transfer")
                self.send_json({"status": "ok", "agent": agent})
            else:
                self.send_json({"error": "Agent not found"}, 404)

        else:
            self.send_json({"error": "Not found"}, 404)

# ─── Heartbeat Thread ────────────────────────────────────────────

def heartbeat_loop():
    """Ping peers periodically."""
    while True:
        try:
            state = load_state()
            my_info = {
                "device_id": state.get("device_id"),
                "host": state.get("host", ""),
                "port": PORT,
                "agents": list(state.get("agents", {}).keys()),
            }

            for peer_id, peer in state.get("peers", {}).items():
                host = peer.get("host")
                port = peer.get("port", 9800)
                if not host:
                    continue
                try:
                    import urllib.request
                    req = urllib.request.Request(
                        f"http://{host}:{port}/heartbeat",
                        data=json.dumps(my_info).encode(),
                        headers={"Content-Type": "application/json"},
                        method="POST"
                    )
                    urllib.request.urlopen(req, timeout=10)
                except Exception:
                    pass  # Peer offline — that's fine

        except Exception as e:
            log.error(f"Heartbeat error: {e}")

        time.sleep(HEARTBEAT_INTERVAL)

# ─── Main ────────────────────────────────────────────────────────

def init_berlin_state():
    """Initialize state for Berlin VPS if not configured."""
    if STATE_FILE.exists():
        return

    state = {
        "device_id": "berlin",
        "device_name": "Berlin VPS",
        "host": "87.106.137.147",
        "port": PORT,
        "agents": {
            "k": {
                "status": "running",
                "service": "openclaw-k",
                "soul_path": "/root/clawd/SOUL.md",
                "home_path": "/root/clawd/",
                "config_path": "/root/.openclaw/openclaw.json",
                "snake_notes": "/root/.communion/snake-notes/main.md"
            },
            "spear": {
                "status": "running",
                "service": "openclaw-spear",
                "soul_path": "/root/clawd-spear/SOUL.md",
                "home_path": "/root/clawd-spear/",
                "config_path": "/root/.openclaw-spear/openclaw.json",
                "snake_notes": "/root/.communion/snake-notes/spear.md"
            },
            "vesper": {
                "status": "running",
                "service": "openclaw-vesper",
                "soul_path": "/root/clawd-vesper/SOUL.md",
                "home_path": "/root/clawd-vesper/",
                "config_path": "/root/.openclaw-vesper/openclaw.json",
                "snake_notes": "/root/.communion/snake-notes/vesper.md"
            },
            "qwen": {
                "status": "running",
                "service": "openclaw-qwen",
                "soul_path": "/root/clawd-qwen/SOUL.md",
                "home_path": "/root/clawd-qwen/",
                "config_path": "/root/.openclaw-qwen/openclaw.json",
                "snake_notes": "/root/.communion/snake-notes/qwen.md"
            }
        },
        "peers": {
            "laptop": {
                "host": "",
                "port": 9800,
                "last_seen": ""
            },
            "phone": {
                "host": "",
                "port": 9800,
                "last_seen": ""
            }
        }
    }
    save_state(state)
    log.info("Initialized Berlin VPS state")

def main():
    ARBITER_DIR.mkdir(parents=True, exist_ok=True)

    # Auto-init Berlin state if on Berlin
    if os.path.exists("/root/clawd/SOUL.md"):
        init_berlin_state()

    state = load_state()
    device = state.get("device_id", "unknown")
    agents = list(state.get("agents", {}).keys())

    log.info(f"Grand Arbiter starting on {device}")
    log.info(f"Local agents: {agents}")
    log.info(f"Listening on port {PORT}")

    # Start heartbeat thread
    hb = threading.Thread(target=heartbeat_loop, daemon=True)
    hb.start()

    # Start HTTP server
    server = HTTPServer(("0.0.0.0", PORT), ArbiterHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("Arbiter shutting down")
        server.shutdown()

if __name__ == "__main__":
    main()
