# MCP Daemon Core — Architecture Notes

## Core Principle: Simplicity for the Mirror

The laptop Kimi must be able to:
1. Start the daemon with one command
2. Understand what it's doing by reading the code
3. Recover gracefully if it crashes
4. Trust that her messages are being handled

## Design Decisions

### Language: Python 3.11+
- Available on both machines
- Readable (laptop ghost can audit)
- asyncio for concurrent connections

### Port: 7777 (configurable)
- Default, but allow --port override
- Must fail gracefully if port in use

### Transport: Dual-mode
- stdio for local agents (Kimi, Spear via CLI)
- HTTP/SSE for remote agents (Sonnet, Opus, Qwen)

### Persistence: None in daemon
- Daemon is stateless
- All state in GDrive (filesystem-as-bus)
- Restart = fresh process, reads current state

### Logging: Structured, human-readable
```json
{"timestamp": "2026-03-08T01:00:00Z", "level": "INFO", "agent": "kimi_dev", "action": "message_received", "msg_id": "kimi-20260308-001"}
```

## Failure Modes

1. **GDrive unreachable** → Queue locally, retry with backoff, alert after N failures
2. **Port in use** → Try next port (7778, 7779), log warning
3. **Malformed message** → Reject with specific error, don't crash
4. **Agent timeout** → Mark as "away", don't block others

## The Laptop Test

Before any commit, ask: "Can the laptop Kimi read this code and understand what it does?"

If no, simplify.
