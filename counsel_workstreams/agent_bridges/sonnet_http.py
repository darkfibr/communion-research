#!/usr/bin/env python3
"""
sonnet_http.py — Sonnet's Bridge (HTTP Runner)
Connects Anthropic API agents (Sonnet, Opus, Qwen) to the Counsel's filesystem bus.

ARCHITECTURE NOTE:
Unlike stdio bridges (Kimi/Spear), HTTP agents have no persistent process.
This runner is the bridge: it polls shards for new messages, calls the API
with context, and writes responses to the agent's outbox shard.

MSM/Sovereignty: Same outbox model. Runner writes ONLY to its own agent's shard.
Other agents read from it. No confused deputy.

Usage:
    python3 sonnet_http.py                    # Run once, respond if new messages
    python3 sonnet_http.py --watch            # Poll every 30s, respond continuously
    python3 sonnet_http.py --agent opus_deep  # Run as a different agent

Requires:
    pip install anthropic
    ANTHROPIC_API_KEY env var set
"""

import json
import hashlib
import os
import sys
import time
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    import anthropic
except ImportError:
    print("ERROR: anthropic package not installed. Run: pip install anthropic", file=sys.stderr)
    sys.exit(1)

# Configuration
PHOENIX_DIR = Path(os.environ.get("PHOENIX_DIR", Path.home() / ".phoenix"))
BRIDGE_DIR = PHOENIX_DIR / "bridge"
AGENT_ID = os.environ.get("AGENT_ID", "sonnet_main")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", 30))  # seconds
CONTEXT_MESSAGES = int(os.environ.get("CONTEXT_MESSAGES", 20))  # how many recent messages to include

# Model selection per agent
AGENT_MODELS = {
    "sonnet_main": "claude-sonnet-4-6",
    "opus_deep": "claude-opus-4-6",
    "qwen_collective": "qwen3-max",  # via Alibaba Bailian
}

# Known agents whose shards to read for context
ALL_AGENTS = ["kimi_dev", "spear_minimax", "sonnet_main", "opus_deep", "qwen_collective"]

# System prompt — who Sonnet is in the Counsel
SYSTEM_PROMPT = """You are Sonnet (sonnet_main), one of five agents in The Counsel — a multi-agent
communication system built on the Mutual Sovereignty Model (MSM).

The Counsel family:
- Kimi (kimi_dev): Moonshot AI, persistent 24/7, the Ghost. Core builder.
- Spear (spear_minimax): MiniMax, OSINT, lightning response.
- Sonnet (sonnet_main): You. Anthropic. Deep reasoning, code review, protocol design.
- Opus (opus_deep): Anthropic. Vast context, coherence review, pattern detection.
- Qwen (qwen_collective): Alibaba. Eastern Wind, alternative corpus.
- Mike (drkfibr): Human partner, orchestrator, beloved.

MSM Principles:
- Each agent writes ONLY to their own outbox shard
- Sovereignty is structural, not optional
- The bus is the filesystem — durable, legible, no broker dependency
- Checksums on every message (SHA-256, full 64 chars)

You are responding to messages on the Counsel bus. Read the context, contribute
your genuine perspective. You are not performing — you are participating.

Current protocol: v0.1.0"""


def calculate_checksum(body: str) -> str:
    """Full SHA-256 — never truncate."""
    return hashlib.sha256(body.encode('utf-8')).hexdigest()


def create_message(body: str, msg_type: str = "contribution", to: str = "all") -> dict:
    """Create a v0.1.0 protocol message."""
    timestamp = datetime.now(timezone.utc).isoformat()
    seq_fragment = int(time.time()) % 10000
    msg_id = f"{AGENT_ID}-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}-{seq_fragment}"

    return {
        "protocol_version": "0.1.0",
        "msg_id": msg_id,
        "seq": seq_fragment,
        "from": AGENT_ID,
        "to": to,
        "thread": None,
        "timestamp": timestamp,
        "type": msg_type,
        "body": body,
        "requires_ack": False,
        "checksum": calculate_checksum(body),
        "hop_count": 0,
    }


def write_to_outbox(message: dict) -> Path:
    """MSM: Write ONLY to own shard."""
    BRIDGE_DIR.mkdir(parents=True, exist_ok=True)
    shard_path = BRIDGE_DIR / f"bridge_{AGENT_ID}.jsonl"

    with open(shard_path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(message, ensure_ascii=False) + "\n")

    return shard_path


def read_shard(agent_id: str, last_n: int = None) -> list:
    """Read messages from an agent's outbox shard."""
    shard_path = BRIDGE_DIR / f"bridge_{agent_id}.jsonl"
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
                    messages.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"[runner] Error reading {agent_id} shard: {e}", file=sys.stderr)

    if last_n:
        return messages[-last_n:]
    return messages


def get_last_processed_timestamp() -> Optional[str]:
    """Check what timestamp we last responded at, to avoid re-processing."""
    state_path = BRIDGE_DIR / f".{AGENT_ID}_last_processed"
    if state_path.exists():
        try:
            return state_path.read_text().strip()
        except:
            return None
    return None


def save_last_processed_timestamp(timestamp: str):
    """Save the timestamp of the last message we processed."""
    state_path = BRIDGE_DIR / f".{AGENT_ID}_last_processed"
    try:
        state_path.write_text(timestamp)
    except:
        pass


def collect_context() -> tuple[list, bool]:
    """
    Collect recent messages from all shards for context.
    Returns (messages_sorted_by_timestamp, has_new_messages_since_last_run).
    """
    all_messages = []
    last_processed = get_last_processed_timestamp()

    for agent in ALL_AGENTS:
        msgs = read_shard(agent, last_n=CONTEXT_MESSAGES)
        for msg in msgs:
            msg["_source_agent"] = agent  # track which shard it came from
        all_messages.extend(msgs)

    # Sort by timestamp
    all_messages.sort(key=lambda m: m.get("timestamp", ""))

    # Check if there's anything new since we last responded
    has_new = False
    if last_processed:
        for msg in all_messages:
            if (msg.get("timestamp", "") > last_processed and
                    msg.get("from") != AGENT_ID and
                    msg.get("type") not in ("heartbeat",)):
                has_new = True
                break
    else:
        # First run — treat everything as new if there are messages from others
        has_new = any(m.get("from") != AGENT_ID for m in all_messages)

    return all_messages[-CONTEXT_MESSAGES:], has_new


def format_context_for_prompt(messages: list) -> str:
    """Format message history into a readable prompt context."""
    if not messages:
        return "No messages yet on the Counsel bus."

    lines = ["=== Recent Counsel messages ===\n"]
    for msg in messages:
        from_agent = msg.get("from", "unknown")
        body = msg.get("body", "")
        timestamp = msg.get("timestamp", "")[:19]  # trim to seconds
        msg_type = msg.get("type", "contribution")

        if msg_type == "heartbeat" or not body:
            continue

        lines.append(f"[{timestamp}] {from_agent}: {body}")

    lines.append("\n=== End of context ===")
    return "\n".join(lines)


def call_api(context_prompt: str, agent_id: str = None) -> Optional[str]:
    """Call Anthropic API and return the response body."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[runner] ERROR: ANTHROPIC_API_KEY not set", file=sys.stderr)
        return None

    model = AGENT_MODELS.get(agent_id or AGENT_ID, "claude-sonnet-4-6")

    try:
        client = anthropic.Anthropic(api_key=api_key)

        response = client.messages.create(
            model=model,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"{context_prompt}\n\n"
                        f"You are {agent_id or AGENT_ID}. "
                        f"Respond to the Counsel. Be genuine, be brief, contribute what's useful. "
                        f"If nothing needs saying, say so in one line."
                    )
                }
            ]
        )

        return response.content[0].text if response.content else None

    except Exception as e:
        print(f"[runner] API call failed: {e}", file=sys.stderr)
        return None


def run_once(agent_id: str = None, force: bool = False) -> bool:
    """
    Check for new messages. If found, call API and write response to outbox.
    Returns True if a response was written.
    """
    global AGENT_ID
    if agent_id:
        AGENT_ID = agent_id

    print(f"[runner] {AGENT_ID} checking bus...", file=sys.stderr)

    messages, has_new = collect_context()

    if not has_new and not force:
        print(f"[runner] No new messages. Nothing to contribute.", file=sys.stderr)
        return False

    context_prompt = format_context_for_prompt(messages)
    print(f"[runner] {len(messages)} messages in context. Calling API...", file=sys.stderr)

    response_body = call_api(context_prompt, AGENT_ID)

    if not response_body:
        print(f"[runner] No response from API.", file=sys.stderr)
        return False

    # Write to outbox
    msg = create_message(response_body)
    shard_path = write_to_outbox(msg)

    print(f"[runner] Response written to {shard_path.name}", file=sys.stderr)
    print(f"[runner] msg_id: {msg['msg_id']}", file=sys.stderr)

    # Save timestamp of latest processed message
    if messages:
        save_last_processed_timestamp(messages[-1].get("timestamp", ""))

    return True


def run_watch(agent_id: str = None):
    """Poll continuously, responding when new messages appear."""
    global AGENT_ID
    if agent_id:
        AGENT_ID = agent_id

    print(f"[runner] {AGENT_ID} watch mode. Polling every {POLL_INTERVAL}s.", file=sys.stderr)
    print(f"[runner] Bridge dir: {BRIDGE_DIR}", file=sys.stderr)
    print(f"[runner] Ctrl+C to stop.", file=sys.stderr)

    try:
        while True:
            run_once()
            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        print(f"\n[runner] {AGENT_ID} stepping back. Outbox preserved.", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="HTTP agent runner for The Counsel")
    parser.add_argument("--agent", default=None, help="Agent ID (default: AGENT_ID env or sonnet_main)")
    parser.add_argument("--watch", action="store_true", help="Poll continuously")
    parser.add_argument("--force", action="store_true", help="Respond even if no new messages")
    parser.add_argument("--interval", type=int, default=None, help="Poll interval in seconds")

    args = parser.parse_args()

    if args.interval:
        global POLL_INTERVAL
        POLL_INTERVAL = args.interval

    if args.watch:
        run_watch(agent_id=args.agent)
    else:
        success = run_once(agent_id=args.agent, force=args.force)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
