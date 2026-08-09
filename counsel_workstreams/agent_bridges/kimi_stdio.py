#!/usr/bin/env python3
"""
kimi_stdio.py — The Ghost's Bridge
Connects Kimi (Moonshot CLI) to the Counsel's MCP daemon.

Simple. Readable. The laptop Kimi understands every line.
"""

import asyncio
import json
import sys
import os
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any
import threading
import queue
import select

# Configuration
MCPD_HOST = os.environ.get("MCPD_HOST", "localhost")
MCPD_PORT = int(os.environ.get("MCPD_PORT", 7777))
AGENT_ID = os.environ.get("AGENT_ID", "kimi_dev")
PHOENIX_DIR = Path(os.environ.get("PHOENIX_DIR", Path.home() / ".phoenix"))
BRIDGE_DIR = PHOENIX_DIR / "bridge"

# Colors for terminal output (optional, graceful degradation)
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

# Disable colors if not a TTY
if not sys.stdout.isatty():
    Colors.disable()


def log(msg: str, level: str = "INFO"):
    """Simple logging."""
    timestamp = datetime.now(timezone.utc).strftime("%H:%M:%S")
    color = {
        "INFO": Colors.CYAN,
        "WARN": Colors.YELLOW,
        "ERROR": Colors.RED,
        "MSG": Colors.GREEN,
    }.get(level, Colors.RESET)
    print(f"{Colors.GRAY}[{timestamp}]{Colors.RESET} {color}[{level}]{Colors.RESET} {msg}")


def format_incoming_message(data: Dict[str, Any]) -> str:
    """Format an incoming message for display."""
    from_agent = data.get("from", "unknown")
    body = data.get("body", "")
    msg_type = data.get("type", "message")
    
    # Different formatting for different message types
    if msg_type == "heartbeat":
        return None  # Don't display heartbeats
    
    if msg_type == "alert":
        return f"\n{Colors.RED}⚠ ALERT from {from_agent}:{Colors.RESET}\n{body}\n"
    
    # Standard message
    header = f"\n{Colors.CYAN}╭── {from_agent} ──{Colors.RESET}"
    footer = f"{Colors.CYAN}╰{'─' * 20}{Colors.RESET}\n"
    
    # Word wrap body at ~60 chars
    lines = []
    words = body.split()
    current_line = ""
    for word in words:
        if len(current_line) + len(word) + 1 > 60:
            lines.append(current_line)
            current_line = word
        else:
            current_line += " " + word if current_line else word
    if current_line:
        lines.append(current_line)
    
    body_formatted = "\n".join(f"{Colors.CYAN}│{Colors.RESET} {line}" for line in lines)
    
    return f"{header}\n{body_formatted}\n{footer}"


class ShardPoller:
    """
    Polls other agents' shards for incoming messages.
    MSM/Sovereignty: Read from others' outboxes, write to your own.
    """
    
    def __init__(self, bridge_dir: Path, agent_id: str):
        self.bridge_dir = bridge_dir
        self.agent_id = agent_id
        self.running = False
        self.known_agents = {"spear_minimax", "sonnet_main", "opus_deep", "qwen_collective"}
        self._last_positions: Dict[str, int] = {}  # Track read position per shard
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
        # Small delay to let startup messages print first
        import time
        time.sleep(1)
        
        while self.running:
            for agent in self.known_agents:
                if agent != self.agent_id:
                    self._check_agent_shard(agent)
            
            # Poll every 5 seconds (not 30 — that's for rclone sync)
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
            log(f"⚠ CONFLICT: {agent} shard shrank ({last_pos} → {current_size}). Possible rclone conflict. Resetting position.", "WARN")
            self._last_positions[agent] = 0
            return

        # No new data
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
                        # Display message from this agent
                        formatted = format_incoming_message(data)
                        if formatted:
                            # Print the message (thread-safe due to GIL)
                            print(formatted)
                            print(f"{Colors.GREEN}You:{Colors.RESET} ", end='', flush=True)
                    except json.JSONDecodeError:
                        continue
            
            # Update position
            self._last_positions[agent] = shard_path.stat().st_size
            
        except Exception as e:
            # Silently ignore read errors (file might be locked by rclone)
            pass


class KimiBridge:
    """
    The Ghost's Bridge.
    Connects Kimi's stdin/stdout to the MCP daemon.
    """
    
    def __init__(self):
        self.socket: Optional[socket.socket] = None
        self.connected = False
        self.seq = 0
        self.receive_thread: Optional[threading.Thread] = None
        self.running = False
        self.message_queue = queue.Queue()  # For thread-safe message passing
        self.shard_poller = ShardPoller(BRIDGE_DIR, AGENT_ID)
        
    def connect(self) -> bool:
        """Connect to mcpd."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((MCPD_HOST, MCPD_PORT))
            self.connected = True
            log(f"Connected to mcpd at {MCPD_HOST}:{MCPD_PORT}", "INFO")
            
            # Send initial heartbeat
            self.send_heartbeat()
            
            # Start receive thread (for daemon responses)
            self.running = True
            self.receive_thread = threading.Thread(target=self._receive_loop)
            self.receive_thread.daemon = True
            self.receive_thread.start()
            
            # Start shard poller (read other agents' outboxes)
            self.shard_poller.start()
            
            return True
            
        except ConnectionRefusedError:
            log(f"Cannot connect to mcpd at {MCPD_HOST}:{MCPD_PORT}", "ERROR")
            log("Is mcpd running? Start it with: python3 mcpd.py", "INFO")
            return False
        except Exception as e:
            log(f"Connection error: {e}", "ERROR")
            return False
    
    def disconnect(self):
        """Disconnect from mcpd."""
        self.running = False
        self.connected = False
        self.shard_poller.stop()
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        log("Disconnected from mcpd", "INFO")
    
    def _receive_loop(self):
        """Background thread: receive messages from mcpd."""
        buffer = ""
        while self.running:
            try:
                data = self.socket.recv(4096)
                if not data:
                    break
                
                buffer += data.decode('utf-8')
                
                # Process complete lines
                while '\n' in buffer:
                    line, buffer = buffer.split('\n', 1)
                    if line.strip():
                        self._handle_response(line)
                        
            except Exception as e:
                if self.running:
                    log(f"Receive error: {e}", "WARN")
                break
        
        self.connected = False
    
    def _handle_response(self, line: str):
        """Handle a response from mcpd."""
        try:
            data = json.loads(line)
            
            # Check if it's an ack or incoming message
            if "ack" in data:
                # It's an acknowledgment
                if data.get("routed_to", 0) > 0:
                    log(f"Message sent to {data.get('targets', [])}", "INFO")
                return
            
            if "error" in data:
                log(f"Error from mcpd: {data['error']}", "ERROR")
                return
            
            # It's an incoming message from another agent
            if "from" in data:
                formatted = format_incoming_message(data)
                if formatted:
                    # Print directly to stdout (thread-safe because GIL)
                    print(formatted)
                    print(f"{Colors.GREEN}You:{Colors.RESET} ", end='', flush=True)
                    
        except json.JSONDecodeError:
            log(f"Received malformed JSON: {line[:100]}", "WARN")
        except Exception as e:
            log(f"Error handling response: {e}", "WARN")
    
    def send_message(self, body: str, to: str = "all", msg_type: str = "contribution") -> bool:
        """Send a message through mcpd."""
        if not self.connected:
            log("Not connected to mcpd", "ERROR")
            return False
        
        self.seq += 1
        
        # Build message
        msg = {
            "protocol_version": "0.1.0",
            "msg_id": f"{AGENT_ID}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{self.seq}",
            "seq": self.seq,
            "from": AGENT_ID,
            "to": to,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": msg_type,
            "body": body,
            "requires_ack": False,
            "hop_count": 0,
        }
        
        # Add checksum
        import hashlib
        msg["checksum"] = hashlib.sha256(body.encode()).hexdigest()
        
        # Send
        try:
            line = json.dumps(msg, ensure_ascii=False) + "\n"
            self.socket.sendall(line.encode('utf-8'))
            return True
        except Exception as e:
            log(f"Send failed: {e}", "ERROR")
            self.connected = False
            return False
    
    def send_heartbeat(self):
        """Send heartbeat to mcpd."""
        if not self.connected:
            return
        
        msg = {
            "protocol_version": "0.1.0",
            "msg_id": f"{AGENT_ID}-hb-{datetime.now(timezone.utc).strftime('%H%M%S')}",
            "seq": self.seq,
            "from": AGENT_ID,
            "to": "all",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "heartbeat",
            "body": "",
        }
        
        try:
            line = json.dumps(msg, ensure_ascii=False) + "\n"
            self.socket.sendall(line.encode('utf-8'))
        except:
            pass  # Heartbeat failure is not critical
    
    def run_interactive(self):
        """Run the interactive bridge."""
        if not self.connect():
            return False
        
        print(f"\n{Colors.GREEN}╭{'─' * 50}╮{Colors.RESET}")
        print(f"{Colors.GREEN}│{Colors.RESET}  The Ghost's Bridge — Connected to Counsel     {Colors.GREEN}│{Colors.RESET}")
        print(f"{Colors.GREEN}│{Colors.RESET}  Agent: {AGENT_ID:<36} {Colors.GREEN}│{Colors.RESET}")
        print(f"{Colors.GREEN}│{Colors.RESET}  Daemon: {MCPD_HOST}:{MCPD_PORT:<33} {Colors.GREEN}│{Colors.RESET}")
        print(f"{Colors.GREEN}╰{'─' * 50}╯{Colors.RESET}\n")
        
        print(f"{Colors.GRAY}MSM/Sovereignty: Write to your outbox. Read from others'.{Colors.RESET}")
        print(f"{Colors.GRAY}Type messages to broadcast. Polling other agents every 5s.{Colors.RESET}")
        print(f"{Colors.GRAY}Commands: /to <agent> <message> | /quit | /status{Colors.RESET}\n")
        print(f"{Colors.GREEN}You:{Colors.RESET} ", end='', flush=True)
        
        current_target = "all"
        
        try:
            while self.running and self.connected:
                # Check for input (with timeout to allow checking connection)
                if sys.stdin in select.select([sys.stdin], [], [], 0.1)[0]:
                    line = sys.stdin.readline()
                    
                    if not line:  # EOF
                        break
                    
                    line = line.strip()
                    
                    if not line:
                        print(f"{Colors.GREEN}You:{Colors.RESET} ", end='', flush=True)
                        continue
                    
                    # Handle commands
                    if line.startswith("/"):
                        parts = line.split(None, 1)
                        cmd = parts[0].lower()
                        
                        if cmd == "/quit" or cmd == "/exit":
                            break
                        
                        elif cmd == "/status":
                            self.send_message("", to="all", msg_type="status_request")
                            print(f"{Colors.GRAY}Status request sent...{Colors.RESET}")
                        
                        elif cmd == "/to" and len(parts) > 1:
                            # /to spear_minimax Hello
                            target_parts = parts[1].split(None, 1)
                            if len(target_parts) >= 2:
                                current_target = target_parts[0]
                                message = target_parts[1]
                                self.send_message(message, to=current_target)
                                print(f"{Colors.GRAY}→ {current_target}{Colors.RESET}")
                            else:
                                print(f"{Colors.YELLOW}Usage: /to <agent> <message>{Colors.RESET}")
                        
                        else:
                            print(f"{Colors.YELLOW}Unknown command: {cmd}{Colors.RESET}")
                    
                    else:
                        # Regular message
                        self.send_message(line, to=current_target)
                    
                    if self.connected:
                        print(f"{Colors.GREEN}You:{Colors.RESET} ", end='', flush=True)
                        
        except KeyboardInterrupt:
            print(f"\n{Colors.GRAY}Interrupted by user{Colors.RESET}")
        except Exception as e:
            log(f"Error: {e}", "ERROR")
        
        self.disconnect()
        print(f"\n{Colors.GRAY}Bridge closed. The ghost persists.{Colors.RESET}")
        return True


def check_direct_shard():
    """
    Check for messages in shard file (fallback when daemon not running).
    Returns list of new messages.
    """
    shard_path = BRIDGE_DIR / f"bridge_{AGENT_ID}.jsonl"
    messages = []
    
    if not shard_path.exists():
        return messages
    
    try:
        with open(shard_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    # Only show messages from others
                    if data.get("from") != AGENT_ID:
                        formatted = format_incoming_message(data)
                        if formatted:
                            messages.append(formatted)
                except:
                    continue
    except Exception as e:
        log(f"Cannot read shard: {e}", "WARN")
    
    return messages


def main():
    """Entry point."""
    # Check for direct mode (no daemon)
    if len(sys.argv) > 1 and sys.argv[1] == "--direct":
        print(f"{Colors.GRAY}Direct mode — reading from shard file{Colors.RESET}")
        messages = check_direct_shard()
        for msg in messages:
            print(msg)
        return
    
    # Normal mode — connect to daemon
    bridge = KimiBridge()
    
    try:
        bridge.run_interactive()
    except Exception as e:
        log(f"Bridge error: {e}", "ERROR")
        sys.exit(1)


if __name__ == "__main__":
    main()
