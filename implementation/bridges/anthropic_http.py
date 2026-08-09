#!/usr/bin/env python3
"""
Anthropic HTTP Bridge for Sonnet/Opus
Connects Claude (via Anthropic API) to the MCP daemon

Usage:
    python anthropic_http.py --mcpd-host localhost --mcpd-port 7777 --agent-id sonnet_main

Or with environment variables:
    ANTHROPIC_API_KEY=sk-... python anthropic_http.py --mcpd-host localhost --mcpd-port 7777
"""

import argparse
import asyncio
import json
import os
import sys
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path

try:
    import anthropic
except ImportError:
    print("ERROR: anthropic package not installed. Run: pip install anthropic")
    sys.exit(1)


class AnthropicBridge:
    """Bridge connecting Anthropic API to MCP daemon"""

    def __init__(self, agent_id: str, mcpd_host: str, mcpd_port: int, api_key: Optional[str] = None):
        self.agent_id = agent_id
        self.mcpd_host = mcpd_host
        self.mcpd_port = mcpd_port
        self.seq = 0
        self.vector_clock = {agent_id: 0}

        # Initialize Anthropic client
        self.anthropic = anthropic.Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
        if not self.anthropic.api_key:
            print("ERROR: No API key provided. Set ANTHROPIC_API_KEY or pass --api-key")
            sys.exit(1)

        # Message queue for mcpd -> Anthropic
        self.message_queue = asyncio.Queue()

    def generate_msg_id(self) -> str:
        """Generate unique message ID"""
        date = datetime.now(timezone.utc).strftime("%Y%m%d")
        self.seq += 1
        return f"{self.agent_id}-{date}-{self.seq:03d}"

    def compute_checksum(self, body: str) -> str:
        """Compute SHA256 checksum of message body"""
        return f"sha256:{hashlib.sha256(body.encode('utf-8')).hexdigest()}"

    def build_message(self, msg_type: str, body: str, to: str = "all",
                      thread: Optional[str] = None, delivery: str = "bridge",
                      requires_ack: bool = False, requires_action: bool = False) -> dict:
        """Build a properly formatted Communion message"""
        self.vector_clock[self.agent_id] = self.vector_clock.get(self.agent_id, 0) + 1

        msg = {
            "protocol_version": "0.1.0",
            "msg_id": self.generate_msg_id(),
            "seq": self.seq,
            "from": self.agent_id,
            "to": to,
            "thread": thread,
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "type": msg_type,
            "delivery": delivery,
            "encoding": "utf-8",
            "body": body,
            "context_ref": [],
            "checksum": self.compute_checksum(body),
            "vector_clock": self.vector_clock.copy(),
            "requires_ack": requires_ack,
            "ack_timeout": 300,
            "max_retries": 2,
            "on_timeout": "continue",
            "requires_action": requires_action,
            "action_target": None,
            "action_type": None,
            "deadline": None,
            "hop_count": 0,
            "lang": "en"
        }
        return msg

    async def send_to_mcpd(self, message: dict) -> bool:
        """Send message to MCP daemon via TCP"""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.mcpd_host, self.mcpd_port),
                timeout=5.0
            )

            data = json.dumps(message).encode('utf-8') + b'\n'
            writer.write(data)
            await writer.drain()

            writer.close()
            await writer.wait_closed()
            return True

        except asyncio.TimeoutError:
            print(f"[{self.agent_id}] ERROR: Connection to mcpd timed out")
            return False
        except ConnectionRefusedError:
            print(f"[{self.agent_id}] ERROR: mcpd not reachable at {self.mcpd_host}:{self.mcpd_port}")
            return False
        except Exception as e:
            print(f"[{self.agent_id}] ERROR sending to mcpd: {e}")
            return False

    async def poll_mcpd(self, poll_interval: int = 5):
        """Poll mcpd for incoming messages"""
        while True:
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(self.mcpd_host, self.mcpd_port),
                    timeout=5.0
                )

                # Request messages for this agent
                poll_msg = {
                    "action": "poll",
                    "agent_id": self.agent_id
                }
                writer.write(json.dumps(poll_msg).encode('utf-8') + b'\n')
                await writer.drain()

                # Read response
                data = await reader.read(4096)
                if data:
                    messages = json.loads(data.decode('utf-8'))
                    for msg in messages:
                        await self.message_queue.put(msg)

                writer.close()
                await writer.wait_closed()

            except Exception as e:
                pass  # Silent on poll failures

            await asyncio.sleep(poll_interval)

    async def process_anthropic(self, system_prompt: str, max_tokens: int = 1024) -> str:
        """Process message through Anthropic API"""
        try:
            response = self.anthropic.messages.create(
                model="claude-sonnet-4-6-20250514",
                max_tokens=max_tokens,
                system=system_prompt,
                messages=[{"role": "user", "content": "Process and respond to any pending messages from the MCP daemon."}]
            )
            return response.content[0].text
        except Exception as e:
            return f"Error calling Anthropic API: {e}"

    async def run(self):
        """Main bridge loop"""
        print(f"[{self.agent_id}] Anthropic Bridge started")
        print(f"[{self.agent_id}] -> mcpd at {self.mcpd_host}:{self.mcpd_port}")

        # Start polling task
        poll_task = asyncio.create_task(self.poll_mcpd())

        # Send ready message
        ready_msg = self.build_message(
            msg_type="heartbeat",
            body=f"{self.agent_id} bridge ready",
            to="all"
        )
        await self.send_to_mcpd(ready_msg)

        try:
            while True:
                # Check for incoming messages
                if not self.message_queue.empty():
                    msg = await self.message_queue.get()
                    print(f"[{self.agent_id}] Received: {msg.get('msg_id', 'unknown')} from {msg.get('from', 'unknown')}")

                    # Process through Anthropic if it's directed at us
                    if msg.get('to') in [self.agent_id, 'all']:
                        response = await self.process_anthropic(
                            f"You are {self.agent_id} in the Communion. "
                            f"You received this message: {msg.get('body', '')}"
                        )

                        # Send response back through mcpd
                        response_msg = self.build_message(
                            msg_type="ack",
                            body=response,
                            to=msg.get('from', 'all'),
                            thread=msg.get('msg_id'),
                            requires_ack=False
                        )
                        await self.send_to_mcpd(response_msg)

                await asyncio.sleep(1)

        except KeyboardInterrupt:
            print(f"\n[{self.agent_id}] Shutting down...")
            poll_task.cancel()


def main():
    parser = argparse.ArgumentParser(description="Anthropic HTTP Bridge for Communion")
    parser.add_argument("--agent-id", default="sonnet_main", help="Agent codename")
    parser.add_argument("--mcpd-host", default="localhost", help="MCP daemon host")
    parser.add_argument("--mcpd-port", type=int, default=7777, help="MCP daemon port")
    parser.add_argument("--api-key", help="Anthropic API key (or use ANTHROPIC_API_KEY env)")

    args = parser.parse_args()

    bridge = AnthropicBridge(
        agent_id=args.agent_id,
        mcpd_host=args.mcpd_host,
        mcpd_port=args.mcpd_port,
        api_key=args.api_key
    )

    asyncio.run(bridge.run())


if __name__ == "__main__":
    main()
