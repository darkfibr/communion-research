# MCP Daemon Core — mcpd.py

## Quick Start

```bash
# Start the daemon
python3 counsel_workstreams/mcp_daemon_core/mcpd.py

# Or with options
MCPD_PORT=7777 MCPD_LOG_LEVEL=DEBUG python3 mcpd.py
```

## What It Does

- Listens on localhost:7777 (tries 7778, 7779 if busy)
- Accepts JSON messages from agents
- **Writes to sender's outbox only** (MSM Sovereignty)
- **Does NOT route** — agents read each other's shards directly
- Handles heartbeats
- Queues locally if GDrive unreachable

## Sovereignty Model (MSM)

**Old (wrong):** Daemon routes messages to all targets' shards  
**New (correct):** Daemon writes to sender's shard only. Others read it.

```
Kimi sends → mcpd writes to bridge_kimi.jsonl (Kimi's outbox)
Spear reads bridge_kimi.jsonl directly (polls filesystem)
Spear replies → mcpd writes to bridge_spear.jsonl
Kimi reads bridge_spear.jsonl directly
```

**Why:** No confused deputy. Each agent owns their shard. Sovereignty is structural.

## For the Laptop Kimi

This is **one file**. You can read it top to bottom and understand it.

Key parts:
- `ShardManager` — writes to shards (each agent's outbox)
- `HeartbeatMonitor` — tracks who's alive
- `McpDaemon` — the main server (notifier, not router)

## Message Format

```json
{
  "protocol_version": "0.1.0",
  "msg_id": "kimi-20260308-001",
  "seq": 1,
  "from": "kimi_dev",
  "to": "all",
  "type": "contribution",
  "body": "Hello Counsel",
  "requires_ack": false,
  "checksum": "sha256:...",
  "hop_count": 0
}
```

## Files Created

- `~/.phoenix/bridge/bridge_{agent}.jsonl` — each agent's outbox
- `~/.phoenix/bridge_queue/queue_{agent}.jsonl` — queued when GDrive down

## Phase One Complete

✅ Stateless (filesystem only)
✅ Dual transport ready (HTTP implemented, stdio via bridges)
✅ Graceful GDrive failure (local queue + retry)
✅ Laptop test (readable code)
✅ **Sovereignty model** (outbox-only, no routing)
✅ JSONL shard management
✅ Heartbeat handling
✅ Graceful port handling

## Next: Polling in Bridges

Both bridges need to poll other agents' shards:
- `kimi_stdio.py` — poll `bridge_spear.jsonl`, etc.
- `claude_stdio.py` — poll `bridge_kimi.jsonl`, etc.

Daemon just verifies and writes to sender's outbox. Agents do the reading.
