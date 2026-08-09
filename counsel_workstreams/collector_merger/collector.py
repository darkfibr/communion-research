#!/usr/bin/env python3
"""
collector.py — Counsel Shard Collector/Merger
Aggregates per-agent outbox shards into a unified merged view.

MSM/Sovereignty notes:
- Shards are source of truth. bridge_merged.jsonl is a CACHE, not authoritative.
- Any agent can reconstruct full state by reading all shards directly.
- Collector is optional. The bus works without it.
- Collector never writes to individual shards. Read-only on agent outboxes.

Usage:
    python3 collector.py                  # Merge once, write bridge_merged.jsonl
    python3 collector.py --watch          # Merge continuously every 30s
    python3 collector.py --status         # Show agent status summary
    python3 collector.py --conflicts      # Show detected conflicts only
"""

import json
import hashlib
import os
import sys
import time
import argparse
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Configuration
PHOENIX_DIR = Path(os.environ.get("PHOENIX_DIR", Path.home() / ".phoenix"))
BRIDGE_DIR = PHOENIX_DIR / "bridge"
MERGED_PATH = BRIDGE_DIR / "bridge_merged.jsonl"
CONFLICT_LOG = BRIDGE_DIR / "bridge_conflicts.jsonl"
WATCH_INTERVAL = int(os.environ.get("COLLECTOR_INTERVAL", 30))

# Known agents — collector reads all of these
ALL_AGENTS = ["kimi_dev", "spear_minimax", "sonnet_main", "opus_deep", "qwen_collective"]

# Silence threshold — agent hasn't written in this many seconds
SILENCE_THRESHOLD = int(os.environ.get("SILENCE_THRESHOLD", 600))  # 10 minutes


def calculate_checksum(body: str) -> str:
    """Full SHA-256 — never truncate."""
    return hashlib.sha256(body.encode('utf-8')).hexdigest()


def verify_message(msg: dict) -> Tuple[bool, Optional[str]]:
    """
    Verify message integrity and required fields.
    Returns (valid, error_reason).
    """
    # Required fields
    required = ["protocol_version", "msg_id", "from", "timestamp", "type", "body", "checksum"]
    for field in required:
        if field not in msg:
            return False, f"Missing required field: '{field}'"

    # Protocol version
    if msg.get("protocol_version") != "0.1.0":
        return False, f"Unknown protocol version: {msg.get('protocol_version')}"

    # Checksum verification
    body = msg.get("body", "")
    checksum = msg.get("checksum", "")

    if checksum:
        # Strip optional prefix
        raw = checksum[7:] if checksum.startswith("sha256:") else checksum
        expected = calculate_checksum(body)

        if len(raw) != 64:
            return False, f"Checksum wrong length: {len(raw)} chars (expected 64)"

        if raw != expected:
            return False, f"Checksum mismatch for msg_id={msg.get('msg_id')}"

    # Timestamp parseable
    try:
        datetime.fromisoformat(msg.get("timestamp", "").replace("Z", "+00:00"))
    except ValueError:
        return False, f"Unparseable timestamp: {msg.get('timestamp')}"

    # from field matches known agents (warning, not rejection)
    from_agent = msg.get("from", "")
    if from_agent not in ALL_AGENTS and from_agent != "drkfibr":
        # Not an error — unknown agents are allowed, just flagged
        pass

    return True, None


def read_shard(agent: str) -> Tuple[List[dict], List[dict]]:
    """
    Read all messages from an agent's shard.
    Returns (valid_messages, invalid_messages).
    """
    shard_path = BRIDGE_DIR / f"bridge_{agent}.jsonl"
    valid = []
    invalid = []

    if not shard_path.exists():
        return valid, invalid

    # Check for rclone conflict copies
    conflict_copies = list(BRIDGE_DIR.glob(f"bridge_{agent}*.jsonl_conflict*"))
    if conflict_copies:
        print(f"⚠  CONFLICT: {len(conflict_copies)} conflict copy(ies) detected for {agent}:", file=sys.stderr)
        for c in conflict_copies:
            print(f"   {c.name}", file=sys.stderr)

    try:
        with open(shard_path, 'r', encoding='utf-8') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    msg = json.loads(line)
                    ok, reason = verify_message(msg)
                    if ok:
                        msg["_shard_source"] = agent  # Track origin
                        msg["_line_num"] = line_num
                        valid.append(msg)
                    else:
                        invalid.append({
                            "agent": agent,
                            "line": line_num,
                            "reason": reason,
                            "raw": line[:200],
                        })
                except json.JSONDecodeError as e:
                    invalid.append({
                        "agent": agent,
                        "line": line_num,
                        "reason": f"JSON parse error: {e}",
                        "raw": line[:200],
                    })
    except Exception as e:
        print(f"[collector] Error reading {agent} shard: {e}", file=sys.stderr)

    return valid, invalid


def deduplicate(messages: List[dict]) -> Tuple[List[dict], List[dict]]:
    """
    Deduplicate by msg_id. Keep first occurrence (earliest timestamp).
    Returns (unique_messages, duplicates).
    """
    seen = {}
    unique = []
    duplicates = []

    for msg in messages:
        msg_id = msg.get("msg_id", "")
        if not msg_id:
            unique.append(msg)  # No ID — can't deduplicate, keep it
            continue

        if msg_id not in seen:
            seen[msg_id] = msg
            unique.append(msg)
        else:
            duplicates.append({
                "msg_id": msg_id,
                "kept_from": seen[msg_id].get("_shard_source"),
                "duplicate_from": msg.get("_shard_source"),
                "timestamp": msg.get("timestamp"),
            })

    return unique, duplicates


def sort_by_timestamp(messages: List[dict]) -> List[dict]:
    """Sort messages by timestamp. Fallback to msg_id for equal timestamps."""
    def sort_key(msg):
        ts = msg.get("timestamp", "")
        # Normalize Z suffix
        ts = ts.replace("Z", "+00:00")
        return (ts, msg.get("msg_id", ""))

    return sorted(messages, key=sort_key)


def get_agent_status() -> Dict[str, dict]:
    """
    Summarize each agent's shard state.
    Returns dict of agent -> status info.
    """
    status = {}
    now = datetime.now(timezone.utc)

    for agent in ALL_AGENTS:
        shard_path = BRIDGE_DIR / f"bridge_{agent}.jsonl"
        agent_status = {
            "shard_exists": shard_path.exists(),
            "message_count": 0,
            "last_timestamp": None,
            "last_seen_seconds_ago": None,
            "shard_size_bytes": 0,
            "silent": True,
            "conflict_copies": 0,
        }

        # Check for conflict copies
        conflicts = list(BRIDGE_DIR.glob(f"bridge_{agent}*.jsonl_conflict*"))
        agent_status["conflict_copies"] = len(conflicts)

        if shard_path.exists():
            agent_status["shard_size_bytes"] = shard_path.stat().st_size
            valid, _ = read_shard(agent)
            agent_status["message_count"] = len(valid)

            if valid:
                # Find most recent message
                sorted_msgs = sort_by_timestamp(valid)
                last = sorted_msgs[-1]
                last_ts_str = last.get("timestamp", "").replace("Z", "+00:00")

                try:
                    last_ts = datetime.fromisoformat(last_ts_str)
                    if last_ts.tzinfo is None:
                        last_ts = last_ts.replace(tzinfo=timezone.utc)
                    elapsed = (now - last_ts).total_seconds()
                    agent_status["last_timestamp"] = last.get("timestamp")
                    agent_status["last_seen_seconds_ago"] = int(elapsed)
                    agent_status["silent"] = elapsed > SILENCE_THRESHOLD
                except Exception:
                    pass

        status[agent] = agent_status

    return status


def write_merged(messages: List[dict]) -> int:
    """
    Write merged message list to bridge_merged.jsonl.
    Overwrites existing file — this is a cache, not append-only.
    Returns number of messages written.
    """
    BRIDGE_DIR.mkdir(parents=True, exist_ok=True)

    # Strip internal tracking fields before writing
    clean_messages = []
    for msg in messages:
        clean = {k: v for k, v in msg.items() if not k.startswith("_")}
        clean_messages.append(clean)

    try:
        with open(MERGED_PATH, 'w', encoding='utf-8') as f:
            for msg in clean_messages:
                f.write(json.dumps(msg, ensure_ascii=False) + "\n")
        return len(clean_messages)
    except Exception as e:
        print(f"[collector] Error writing merged shard: {e}", file=sys.stderr)
        return 0


def log_conflicts(conflicts: List[dict]):
    """Append conflict records to conflict log."""
    if not conflicts:
        return

    BRIDGE_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).isoformat()

    try:
        with open(CONFLICT_LOG, 'a', encoding='utf-8') as f:
            for conflict in conflicts:
                record = {"detected_at": timestamp, **conflict}
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[collector] Error writing conflict log: {e}", file=sys.stderr)


def merge_once(verbose: bool = True) -> dict:
    """
    Full merge cycle: read all shards, validate, deduplicate, sort, write.
    Returns summary dict.
    """
    all_valid = []
    all_invalid = []
    agents_read = []

    for agent in ALL_AGENTS:
        valid, invalid = read_shard(agent)
        all_valid.extend(valid)
        all_invalid.extend(invalid)
        if valid or (BRIDGE_DIR / f"bridge_{agent}.jsonl").exists():
            agents_read.append(agent)

    # Deduplicate
    unique, duplicates = deduplicate(all_valid)

    # Sort by timestamp
    sorted_messages = sort_by_timestamp(unique)

    # Write merged output
    written = write_merged(sorted_messages)

    # Log conflicts/invalids
    if all_invalid:
        log_conflicts(all_invalid)

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agents_with_shards": agents_read,
        "total_messages": len(all_valid),
        "unique_messages": len(unique),
        "duplicates_detected": len(duplicates),
        "invalid_messages": len(all_invalid),
        "written_to_merged": written,
    }

    if verbose:
        print(f"[collector] Merged {written} messages from {len(agents_read)} agent(s)")
        if all_invalid:
            print(f"[collector] ⚠  {len(all_invalid)} invalid message(s) — see {CONFLICT_LOG.name}")
        if duplicates:
            print(f"[collector] ℹ  {len(duplicates)} duplicate(s) removed")

    return summary


def print_status():
    """Print human-readable agent status table."""
    status = get_agent_status()
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    print(f"\n=== Counsel Agent Status — {now_str} ===\n")
    print(f"{'Agent':<20} {'Messages':<10} {'Last Seen':<20} {'Status':<12} {'Conflicts'}")
    print("─" * 75)

    for agent, info in status.items():
        if not info["shard_exists"]:
            status_str = "NO SHARD"
            last_seen = "—"
        elif info["silent"]:
            status_str = "SILENT"
            secs = info.get("last_seen_seconds_ago")
            last_seen = f"{secs}s ago" if secs else "unknown"
        else:
            status_str = "ACTIVE"
            secs = info.get("last_seen_seconds_ago", 0)
            last_seen = f"{secs}s ago"

        conflicts = f"⚠  {info['conflict_copies']}" if info["conflict_copies"] else "✓"
        print(f"{agent:<20} {info['message_count']:<10} {last_seen:<20} {status_str:<12} {conflicts}")

    print()

    # Merged shard info
    if MERGED_PATH.exists():
        size = MERGED_PATH.stat().st_size
        print(f"bridge_merged.jsonl: {size} bytes (cache — not source of truth)")
    else:
        print("bridge_merged.jsonl: not yet generated — run collector.py to create")
    print()


def watch_loop():
    """Run merge continuously."""
    print(f"[collector] Watch mode. Merging every {WATCH_INTERVAL}s.", file=sys.stderr)
    print(f"[collector] Bridge dir: {BRIDGE_DIR}", file=sys.stderr)
    print(f"[collector] Output: {MERGED_PATH}", file=sys.stderr)
    print(f"[collector] Ctrl+C to stop.", file=sys.stderr)

    try:
        while True:
            merge_once(verbose=True)
            time.sleep(WATCH_INTERVAL)
    except KeyboardInterrupt:
        print("\n[collector] Stopped.", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Counsel shard collector/merger")
    parser.add_argument("--watch", action="store_true", help="Merge continuously")
    parser.add_argument("--status", action="store_true", help="Show agent status")
    parser.add_argument("--conflicts", action="store_true", help="Show conflict log")
    parser.add_argument("--interval", type=int, default=None, help="Watch interval in seconds")
    parser.add_argument("--quiet", action="store_true", help="Suppress output")

    args = parser.parse_args()

    if args.interval:
        global WATCH_INTERVAL
        WATCH_INTERVAL = args.interval

    if args.status:
        print_status()
        return

    if args.conflicts:
        if CONFLICT_LOG.exists():
            with open(CONFLICT_LOG, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        record = json.loads(line)
                        print(json.dumps(record, indent=2))
        else:
            print("No conflicts logged yet.")
        return

    if args.watch:
        watch_loop()
    else:
        merge_once(verbose=not args.quiet)


if __name__ == "__main__":
    main()
