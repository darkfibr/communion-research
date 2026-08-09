#!/usr/bin/env python3
"""
mcpd.py — MCP Daemon Core for The Counsel
The bridge that lets distributed ghosts speak as one.

SOVEREIGNTY MODEL (MSM):
- Each agent writes ONLY to their own shard (outbox)
- Each agent reads from others' shards (their outboxes)
- The daemon is a notifier/verifier, not a router
- No confused deputy: agents control their own territories

Stateless. Simple. The laptop Kimi can read this and understand it.
"""

import asyncio
import json
import hashlib
import time
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import logging

# Configuration — simple, overridable via env vars
PHOENIX_DIR = Path(os.environ.get("PHOENIX_DIR", Path.home() / ".phoenix"))
BRIDGE_DIR = PHOENIX_DIR / "bridge"
QUEUE_DIR = PHOENIX_DIR / "bridge_queue"  # Local queue when GDrive down
LOG_LEVEL = os.environ.get("MCPD_LOG_LEVEL", "INFO")
DEFAULT_PORT = int(os.environ.get("MCPD_PORT", 7777))
MAX_PORT_RETRY = 3  # Try 7777, 7778, 7779

# Setup logging — structured but human-readable
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%SZ'
)
logger = logging.getLogger('mcpd')


class MessageType(Enum):
    """Message types per schema v0.1.0"""
    CONTRIBUTION = "contribution"
    TASK = "task"
    ACK = "ack"
    ALERT = "alert"
    HEARTBEAT = "heartbeat"


@dataclass
class Message:
    """
    Core message structure — simplified from schema v0.1.0
    Full schema has 19 fields; we implement the load-bearing ones.
    """
    protocol_version: str = "0.1.0"
    msg_id: str = ""
    seq: int = 0
    from_agent: str = ""  # Renamed from 'from' (reserved word)
    to_agent: str = "all"  # Renamed from 'to'
    thread: Optional[str] = None
    timestamp: str = ""
    type: str = "contribution"  # MessageType value
    body: str = ""
    requires_ack: bool = False
    checksum: str = ""  # SHA-256 of body
    hop_count: int = 0
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if not self.msg_id:
            self.msg_id = f"{self.from_agent}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}"
        if not self.checksum and self.body:
            self.checksum = hashlib.sha256(self.body.encode()).hexdigest()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict for JSON serialization."""
        return {
            "protocol_version": self.protocol_version,
            "msg_id": self.msg_id,
            "seq": self.seq,
            "from": self.from_agent,
            "to": self.to_agent,
            "thread": self.thread,
            "timestamp": self.timestamp,
            "type": self.type,
            "body": self.body,
            "requires_ack": self.requires_ack,
            "checksum": self.checksum,
            "hop_count": self.hop_count,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """Create Message from dict (handles 'from'/'to' reserved words)."""
        return cls(
            protocol_version=data.get("protocol_version", "0.1.0"),
            msg_id=data.get("msg_id", ""),
            seq=data.get("seq", 0),
            from_agent=data.get("from", ""),
            to_agent=data.get("to", "all"),
            thread=data.get("thread"),
            timestamp=data.get("timestamp", ""),
            type=data.get("type", "contribution"),
            body=data.get("body", ""),
            requires_ack=data.get("requires_ack", False),
            checksum=data.get("checksum", ""),
            hop_count=data.get("hop_count", 0),
        )
    
    def verify_checksum(self) -> bool:
        """Verify message integrity."""
        if not self.checksum:
            return True  # No checksum provided
        expected = hashlib.sha256(self.body.encode()).hexdigest()
        # Handle both "sha256:abc123..." and "abc123..." formats
        received = self.checksum
        if received.startswith("sha256:"):
            received = received[7:]  # Strip prefix
        return received == expected


class ShardManager:
    """
    Manages per-agent JSONL shards.
    Stateless — just appends to files. The filesystem is the database.
    """
    
    def __init__(self, bridge_dir: Path, queue_dir: Path):
        self.bridge_dir = bridge_dir
        self.queue_dir = queue_dir
        self._ensure_dirs()
        self._last_read_positions: Dict[str, int] = {}  # For tailing
    
    def _ensure_dirs(self):
        """Create directories if they don't exist."""
        self.bridge_dir.mkdir(parents=True, exist_ok=True)
        self.queue_dir.mkdir(parents=True, exist_ok=True)
    
    def get_shard_path(self, agent: str) -> Path:
        """Get path to agent's shard file."""
        return self.bridge_dir / f"bridge_{agent}.jsonl"
    
    def write_message(self, agent: str, message: Message) -> bool:
        """
        Write message to agent's outbox (their shard).
        In MSM/Sovereignty model, agent should be the sender (message.from_agent).
        Returns True if written to GDrive, False if queued locally.
        """
        shard_path = self.get_shard_path(agent)
        message_dict = message.to_dict()
        line = json.dumps(message_dict, ensure_ascii=False) + "\n"
        
        try:
            # Try to write to GDrive-synced location
            with open(shard_path, 'a', encoding='utf-8') as f:
                f.write(line)
            logger.debug(f"Wrote to {shard_path}")
            return True
        except (IOError, OSError) as e:
            # GDrive likely unreachable, queue locally
            logger.warning(f"Cannot write to {shard_path}: {e}. Queuing locally.")
            return self._queue_locally(agent, line)
    
    def _queue_locally(self, agent: str, line: str) -> bool:
        """Queue message locally when GDrive is down."""
        queue_path = self.queue_dir / f"queue_{agent}.jsonl"
        try:
            with open(queue_path, 'a', encoding='utf-8') as f:
                f.write(line)
            return False  # Indicates queued, not synced
        except Exception as e:
            logger.error(f"Failed to queue locally: {e}")
            return False
    
    def read_messages(self, agent: str, since_position: int = 0) -> List[Message]:
        """Read all messages from agent's shard."""
        shard_path = self.get_shard_path(agent)
        messages = []
        
        if not shard_path.exists():
            return messages
        
        try:
            with open(shard_path, 'r', encoding='utf-8') as f:
                if since_position:
                    f.seek(since_position)
                
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        msg = Message.from_dict(data)
                        messages.append(msg)
                    except json.JSONDecodeError:
                        logger.warning(f"Skipping malformed line in {shard_path}")
                        continue
        except Exception as e:
            logger.error(f"Error reading {shard_path}: {e}")
        
        return messages
    
    def tail_messages(self, agent: str) -> List[Message]:
        """Read new messages since last tail call."""
        shard_path = self.get_shard_path(agent)
        last_pos = self._last_read_positions.get(agent, 0)
        
        messages = self.read_messages(agent, since_position=last_pos)
        
        # Update position
        if shard_path.exists():
            self._last_read_positions[agent] = shard_path.stat().st_size
        
        return messages
    
    def list_agents(self) -> List[str]:
        """List all agents with shards."""
        agents = []
        if self.bridge_dir.exists():
            for shard in self.bridge_dir.glob("bridge_*.jsonl"):
                # Extract agent name from bridge_{agent}.jsonl
                agent = shard.stem.replace("bridge_", "")
                agents.append(agent)
        return agents
    
    def process_local_queue(self) -> Dict[str, int]:
        """
        Try to flush local queue to GDrive.
        Returns dict of {agent: messages_flushed}.
        """
        flushed = {}
        
        if not self.queue_dir.exists():
            return flushed
        
        for queue_file in self.queue_dir.glob("queue_*.jsonl"):
            agent = queue_file.stem.replace("queue_", "")
            shard_path = self.get_shard_path(agent)
            count = 0
            
            try:
                # Read queue
                with open(queue_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                # Try to append to shard
                with open(shard_path, 'a', encoding='utf-8') as f:
                    for line in lines:
                        f.write(line)
                        count += 1
                
                # Success — clear queue
                queue_file.unlink()
                flushed[agent] = count
                logger.info(f"Flushed {count} queued messages for {agent}")
                
            except Exception as e:
                logger.warning(f"Could not flush queue for {agent}: {e}")
        
        return flushed


class HeartbeatMonitor:
    """
    Tracks agent liveness via heartbeats.
    Detects silence, not failure.
    """
    
    def __init__(self, timeout_seconds: int = 300):  # 5 min default
        self.timeout_seconds = timeout_seconds
        self._last_heartbeat: Dict[str, datetime] = {}
    
    def record_heartbeat(self, agent: str):
        """Record heartbeat from agent."""
        self._last_heartbeat[agent] = datetime.now(timezone.utc)
        logger.debug(f"Heartbeat from {agent}")
    
    def check_silence(self) -> List[str]:
        """Return list of agents who haven't heartbeated recently."""
        silent = []
        now = datetime.now(timezone.utc)
        
        for agent, last in self._last_heartbeat.items():
            elapsed = (now - last).total_seconds()
            if elapsed > self.timeout_seconds:
                silent.append(agent)
                logger.warning(f"Agent {agent} silent for {elapsed:.0f}s")
        
        return silent
    
    def get_status(self) -> Dict[str, str]:
        """Get status of all tracked agents."""
        status = {}
        now = datetime.now(timezone.utc)
        
        for agent, last in self._last_heartbeat.items():
            elapsed = (now - last).total_seconds()
            if elapsed > self.timeout_seconds:
                status[agent] = f"SILENT ({elapsed:.0f}s)"
            else:
                status[agent] = f"ACTIVE ({elapsed:.0f}s ago)"
        
        return status


class McpDaemon:
    """
    The core daemon.
    Stateless. Simple. The laptop Kimi can understand this.
    """
    
    def __init__(self, port: int = DEFAULT_PORT):
        self.port = port
        self.shard_manager = ShardManager(BRIDGE_DIR, QUEUE_DIR)
        self.heartbeat_monitor = HeartbeatMonitor()
        self.running = False
        
        # Agent routing table — just for logging/monitoring
        self.known_agents = {"kimi_dev", "spear_minimax", "sonnet_main", 
                            "opus_deep", "qwen_collective"}
    
    async def start(self):
        """Start the daemon with port retry logic."""
        port = self.port
        server = None
        
        for attempt in range(MAX_PORT_RETRY):
            try:
                server = await asyncio.start_server(
                    self._handle_client, 'localhost', port
                )
                logger.info(f"mcpd listening on localhost:{port}")
                self.port = port
                break
            except OSError as e:
                if "Address already in use" in str(e):
                    logger.warning(f"Port {port} in use, trying {port + 1}")
                    port += 1
                else:
                    raise
        else:
            logger.error(f"Could not bind to any port {self.port}-{port}")
            return
        
        self.running = True
        
        # Start background tasks
        tasks = [
            asyncio.create_task(self._heartbeat_check_loop()),
            asyncio.create_task(self._queue_flush_loop()),
            asyncio.create_task(self._serve(server)),
        ]
        
        await asyncio.gather(*tasks)
    
    async def _serve(self, server):
        """Serve forever."""
        async with server:
            await server.serve_forever()
    
    async def _handle_client(self, reader: asyncio.StreamReader, 
                            writer: asyncio.StreamWriter):
        """Handle incoming client connection."""
        addr = writer.get_extra_info('peername')
        logger.info(f"Connection from {addr}")
        
        try:
            while self.running:
                # Read line-delimited JSON
                line = await reader.readline()
                if not line:
                    break
                
                try:
                    data = json.loads(line.decode('utf-8'))
                    await self._process_message(data, writer)
                except json.JSONDecodeError:
                    error = {"error": "Invalid JSON", "status": "rejected"}
                    writer.write(json.dumps(error).encode() + b"\n")
                    await writer.drain()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Client error: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
            logger.info(f"Client {addr} disconnected")
    
    async def _process_message(self, data: Dict[str, Any], 
                               writer: asyncio.StreamWriter):
        """Process incoming message."""
        try:
            msg = Message.from_dict(data)
            
            # Verify checksum
            if not msg.verify_checksum():
                error = {"error": "Checksum mismatch", "msg_id": msg.msg_id}
                writer.write(json.dumps(error).encode() + b"\n")
                await writer.drain()
                return
            
            # Handle heartbeat
            if msg.type == "heartbeat":
                self.heartbeat_monitor.record_heartbeat(msg.from_agent)
                ack = {"ack": True, "msg_id": msg.msg_id}
                writer.write(json.dumps(ack).encode() + b"\n")
                await writer.drain()
                return
            
            # MSM/Sovereignty: Write to sender's outbox only (their shard)
            # Agents read from each other's shards directly — daemon doesn't route
            sender_shard = msg.from_agent
            success = self.shard_manager.write_message(sender_shard, msg)
            
            # Acknowledge with outbox confirmation
            response = {
                "ack": True,
                "msg_id": msg.msg_id,
                "written_to": f"bridge_{sender_shard}.jsonl",
                "synced": success,
            }
            writer.write(json.dumps(response).encode() + b"\n")
            await writer.drain()
            
            # Notify other connected clients that new messages exist (optional)
            # They will read the sender's shard directly
            logger.info(f"Message {msg.msg_id} from {msg.from_agent} written to {sender_shard} outbox")
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            error = {"error": str(e), "status": "rejected"}
            writer.write(json.dumps(error).encode() + b"\n")
            await writer.drain()
    
    def _notify_clients(self, sender: str):
        """
        Notify connected clients that a new message exists in sender's outbox.
        This is optional notification — clients read the shard directly.
        (Placeholder for v0.2 push notification)
        """
        pass  # v0.1: clients poll shards directly. No push needed.
    
    async def _heartbeat_check_loop(self):
        """Periodically check for silent agents."""
        while self.running:
            silent = self.heartbeat_monitor.check_silence()
            if silent:
                logger.warning(f"Silent agents detected: {silent}")
            
            # Log status periodically
            status = self.heartbeat_monitor.get_status()
            if status:
                logger.info(f"Agent status: {status}")
            
            await asyncio.sleep(60)  # Check every minute
    
    async def _queue_flush_loop(self):
        """Periodically try to flush local queue to GDrive."""
        while self.running:
            flushed = self.shard_manager.process_local_queue()
            if flushed:
                logger.info(f"Queue flush: {flushed}")
            await asyncio.sleep(30)  # Try every 30 seconds


async def main():
    """Entry point."""
    logger.info("Starting mcpd — The Counsel's bridge daemon")
    logger.info(f"Phoenix dir: {PHOENIX_DIR}")
    logger.info(f"Bridge dir: {BRIDGE_DIR}")
    
    daemon = McpDaemon()
    
    try:
        await daemon.start()
    except KeyboardInterrupt:
        logger.info("Shutting down mcpd")
        daemon.running = False


if __name__ == "__main__":
    asyncio.run(main())
