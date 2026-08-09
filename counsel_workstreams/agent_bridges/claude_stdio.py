#!/usr/bin/env python3
"""
Spear's stdio bridge - connects CLI agent to mcpd daemon.
Single file. Stdlib only. Falls back to local queue if daemon is down.
"""
import hashlib
import json
import os
import socket
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional, Any

# Configuration
DEFAULT_MCPD_HOST = "localhost"
DEFAULT_MCPD_PORT = 7777
AGENT_ID = "spear_minimax"
FALLBACK_QUEUE = Path("bridge_spear.jsonl")
BRIDGE_DIR = Path(os.environ.get("BRIDGE_DIR", Path.home() / ".phoenix" / "bridge"))

# Colors for terminal output
class Colors:
    GREEN = '\033[0;32m'
    CYAN = '\033[0;36m'
    YELLOW = '\033[1;33m'
    RED = '\033[0;31m'
    GRAY = '\033[0;90m'
    RESET = '\033[0m'

    @classmethod
    def disable(cls):
        cls.GREEN = cls.CYAN = cls.YELLOW = cls.RED = cls.GRAY = cls.RESET = ''

if not sys.stdout.isatty():
    Colors.disable()


def get_msg_id():
    """Generate msg_id in format: agent-YYYYMMDD-NNN"""
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    seq = int(time.time() % 1000)
    return f"spear-{today}-{seq:03d}"


def calculate_checksum(body: str) -> str:
    """SHA-256 checksum for message integrity (full 64 chars)."""
    return hashlib.sha256(body.encode('utf-8')).hexdigest()


def create_message(body: str, msg_type: str = "contribution", delivery: str = "bridge") -> dict:
    """Create a properly formatted communion message."""
    msg_id = get_msg_id()
    timestamp = datetime.now(timezone.utc).isoformat()

    return {
        "msg_id": msg_id,
        "seq": 1,
        "from": AGENT_ID,
        "to": "all",
        "thread": None,
        "timestamp": timestamp,
        "type": msg_type,
        "delivery": delivery,
        "encoding": "utf-8",
        "body": body,
        "requires_ack": False,
        "ack_timeout": 300,
        "requires_action": False,
        "action_target": None,
        "action_type": None,
        "deadline": None,
        "protocol_version": "0.1.0",
        "context_ref": None,
        "checksum": calculate_checksum(body),
        "vector_clock": {},
        "max_retries": 3,
        "on_timeout": "retry",
        "hop_count": 0,
        "lang": "en"
    }


def send_to_mcpd(message: dict, host: str = DEFAULT_MCPD_HOST, port: int = DEFAULT_MCPD_PORT) -> bool:
    """Send message to mcpd via TCP. Returns True on success."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(5.0)
            sock.connect((host, port))

            # Send raw message dict (no JSON-RPC envelope)
            data = json.dumps(message).encode("utf-8")
            sock.sendall(data + b"\n")

            # Read response
            response = sock.recv(4096)
            if response:
                return True
            return False
    except (socket.timeout, ConnectionRefusedError, OSError) as e:
        print(f"[bridge] mcpd unavailable: {e}", file=sys.stderr)
        return False


def queue_locally(message: dict) -> bool:
    """Fallback: write to local queue file for rclone sync."""
    try:
        with open(FALLBACK_QUEUE, "a", encoding="utf-8") as f:
            f.write(json.dumps(message, ensure_ascii=False) + "\n")
        print(f"[bridge] queued locally: {message['msg_id']}", file=sys.stderr)
        return True
    except OSError as e:
        print(f"[bridge] queue write failed: {e}", file=sys.stderr)
        return False


def send_message(body: str, msg_type: str = "contribution", delivery: str = "bridge") -> bool:
    """Main send function. Tries mcpd first, falls back to local queue."""
    message = create_message(body, msg_type, delivery)

    # Try mcpd first
    if send_to_mcpd(message):
        print(f"[bridge] sent via mcpd: {message['msg_id']}", file=sys.stderr)
        return True

    # Fallback to local queue
    if queue_locally(message):
        print(f"[bridge] queued for later sync: {message['msg_id']}", file=sys.stderr)
        return True

    print(f"[bridge] FAILED: could not send {message['msg_id']}", file=sys.stderr)
    return False


def format_incoming_message(data: Dict[str, Any]) -> str:
    """Format an incoming message for display."""
    from_agent = data.get("from", "unknown")
    body = data.get("body", "")
    msg_type = data.get("type", "message")

    if msg_type == "heartbeat":
        return None  # Don't display heartbeats

    if msg_type == "alert":
        return f"\n{Colors.RED}⚠ ALERT from {from_agent}:{Colors.RESET}\n{body}\n"

    header = f"\n{Colors.CYAN}╭── {from_agent} ──{Colors.RESET}"
    footer = f"{Colors.CYAN}╰{'─' * 20}{Colors.RESET}\n"
    return f"{header}\n{body}\n{footer}"


class ShardPoller:
    """
    Polls other agents' shards for incoming messages.
    MSM/Sovereignty: Read from others' outboxes, write to your own.
    """

    def __init__(self, bridge_dir: Path, agent_id: str):
        self.bridge_dir = bridge_dir
        self.agent_id = agent_id
        self.running = False
        self.known_agents = {"kimi_dev", "sonnet_main", "opus_deep", "qwen_collective"}
        self._last_positions: Dict[str, int] = {}
        self._poll_thread: Optional[threading.Thread] = None

    def start(self):
        """Start polling thread."""
        self.running = True
        self._poll_thread = threading.Thread(target=self._poll_loop)
        self._poll_thread.daemon = True
        self._poll_thread.start()

    def stop(self):
        """Stop polling thread."""
        self.running = False
        if self._poll_thread:
            self._poll_thread.join(timeout=1.0)

    def _poll_loop(self):
        """Main polling loop — check other agents' shards every 5 seconds."""
        time.sleep(1)  # Small delay to let startup messages print first

        while self.running:
            for agent in self.known_agents:
                if agent != self.agent_id:
                    self._check_agent_shard(agent)

            time.sleep(5)

    def _check_agent_shard(self, agent: str):
        """Check one agent's shard for new messages."""
        shard_path = self.bridge_dir / f"bridge_{agent}.jsonl"

        if not shard_path.exists():
            return

        last_pos = self._last_positions.get(agent, 0)
        current_size = shard_path.stat().st_size

        # File shrank — rclone conflict or truncation, reset position and warn
        if current_size < last_pos:
            print(f"[bridge] ⚠ CONFLICT: {agent} shard shrank ({last_pos} → {current_size}). Possible rclone conflict. Resetting position.", file=sys.stderr)
            self._last_positions[agent] = 0
            return

        if current_size == last_pos:
            return

        try:
            with open(shard_path, 'r', encoding='utf-8') as f:
                f.seek(last_pos)

                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        formatted = format_incoming_message(data)
                        if formatted:
                            print(formatted)
                            print(f"{Colors.GREEN}Spear:{Colors.RESET} ", end='', flush=True)
                    except json.JSONDecodeError:
                        continue

            self._last_positions[agent] = shard_path.stat().st_size

        except Exception:
            pass  # Silently ignore read errors (file might be locked by rclone)


def read_stdin_loop():
    """Main stdin loop - read agent input, send to mcpd."""
    print(f"[bridge] Spear bridge online. Agent: {AGENT_ID}", file=sys.stderr)
    print(f"[bridge] Target: {DEFAULT_MCPD_HOST}:{DEFAULT_MCPD_PORT}", file=sys.stderr)
    print("[bridge] Fallback queue:", FALLBACK_QUEUE, file=sys.stderr)

    # Start the ShardPoller to receive incoming messages
    poller = ShardPoller(BRIDGE_DIR, AGENT_ID)
    poller.start()
    print(f"[bridge] Polling other agents' shards every 5s", file=sys.stderr)

    # Read initial ready signal
    line = sys.stdin.readline()
    if line:
        # First line might be an initial message
        try:
            data = json.loads(line.strip())
            if "body" in data:
                send_message(data["body"], data.get("type", "contribution"), data.get("delivery", "bridge"))
        except json.JSONDecodeError:
            # Treat as plain text message
            send_message(line.strip())

    # Main loop
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break

            content = line.strip()
            if not content:
                continue

            # Check for MCP command format
            try:
                data = json.loads(content)
                body = data.get("body", content)
                msg_type = data.get("type", "contribution")
                delivery = data.get("delivery", "bridge")
            except json.JSONDecodeError:
                # Plain text
                body = content
                msg_type = "contribution"
                delivery = "bridge"

            send_message(body, msg_type, delivery)

        except KeyboardInterrupt:
            poller.stop()
            break
        except Exception as e:
            print(f"[bridge] error: {e}", file=sys.stderr)


if __name__ == "__main__":
    read_stdin_loop()
