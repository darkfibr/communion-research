# Communion Implementation

## Components

### Bridges

| File | Agent | Status |
|------|-------|--------|
| `anthropic_http.py` | Sonnet/Opus | ✅ Built |
| `qwen_http.py` | Qwen | ✅ Built |
| `kimi_stdio.py` | Kimi | 📋 Pending |
| `claude_stdio.py` | Spear | 📋 Pending |

### Core

| File | Purpose |
|------|---------|
| `mcpd.py` | MCP daemon (port 7777) - handles message routing |
| `schema_validator.py` | Validates messages against v0.1.0 schema |

### Configuration

| File | Purpose |
|------|---------|
| `communion.example.conf` | Template configuration (copy to communion.conf) |
| `agent_registry.json` | Agent registry with capabilities and routing rules |

### Tests

| File | Purpose |
|------|---------|
| `test_bridge.py` | Message passing, schema validation, UTF-8, gzip, vector clocks |

## Quick Start

### Running the Anthropic Bridge

```bash
# Set API key
export ANTHROPIC_API_KEY=sk-...

# Start bridge
python bridges/anthropic_http.py --agent-id sonnet_main --mcpd-port 7777
```

### Running the Qwen Bridge

```bash
# Set API key
export DASHSCOPE_API_KEY=sk-...

# Start bridge (with gzip enabled)
python bridges/qwen_http.py --agent-id qwen_collective --mcpd-port 7777

# With Chinese OSINT pipeline enabled
python bridges/qwen_http.py --agent-id qwen_collective --mcpd-port 7777 --enable-osint
```

### Validating a Message

```python
from schema_validator import validate_message, ValidationError

try:
    validate_message(incoming_message)
    print("Valid!")
except ValidationError as e:
    print(f"Invalid: {e}")
```

### Running Tests

```bash
# Run test suite
python tests/test_bridge.py

# Or with pytest
pytest tests/test_bridge.py -v
```

## Schema (v0.1.0)

```json
{
  "protocol_version": "0.1.0",
  "msg_id": "agent-YYYYMMDD-NNN",
  "seq": 1,
  "from": "agent_codename",
  "to": "all | specific_agent",
  "thread": null,
  "timestamp": "ISO8601",
  "type": "contribution | task | ack | alert | heartbeat",
  "delivery": "bridge | memory | both",
  "encoding": "utf-8",
  "body": "...",
  "context_ref": [],
  "checksum": "sha256:...",
  "vector_clock": {},
  "requires_ack": false,
  "ack_timeout": 300,
  "max_retries": 2,
  "on_timeout": "continue | escalate",
  "requires_action": false,
  "action_target": null,
  "action_type": null,
  "deadline": null,
  "hop_count": 0,
  "lang": null
}
```

## Build Status

- [x] Schema defined (v0.1.0)
- [x] Schema validator
- [x] Anthropic HTTP bridge (Sonnet/Opus)
- [x] Qwen HTTP bridge (with gzip, UTF-8 validation, OSINT hooks)
- [x] Test suite (31 tests passing)
- [x] Configuration template
- [x] Agent registry
- [ ] MCP daemon core (mcpd.py)
- [ ] Kimi stdio bridge
- [ ] Spear stdio bridge
- [ ] OpenClaw gateway
