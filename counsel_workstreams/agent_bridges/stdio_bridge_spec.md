# stdio Bridge Specification
## For Kimi (CLI) and Spear (MiniMax/Claude CLI)

## Overview

stdio bridge wraps the agent's native CLI interface and translates to/from MCP protocol.

## Interface

```
python kimi_stdio.py --mcpd-port 7777 [--agent-id kimi_dev]
```

## Behavior

1. **On Start:**
   - Connect to mcpd via localhost:PORT
   - Authenticate (if configured)
   - Begin stdin/stdout loop

2. **Receiving from mcpd:**
   - Read JSON-RPC messages from TCP socket
   - Display relevant info to agent (stdout)
   - Trigger tool calls as needed

3. **Sending to mcpd:**
   - Read agent input (stdin)
   - Wrap in MCP message format
   - Send to daemon

## Simplification for Laptop

Kimi's stdio bridge should be a thin wrapper:
- Most logic lives in mcpd
- Bridge just transports
- If mcpd is down, bridge queues locally (GDrive)

## Single-File Requirement

The bridge must be one file that can be:
- Read in full during a single context window
- Understood without external dependencies beyond stdlib
- Debugged with print statements

## Example Flow

```
Kimi types: "Tell Spear I found the issue"
↓
kimi_stdio.py wraps in MCP envelope
↓
Sends to mcpd on port 7777
↓
mcpd writes to bridge_spear.jsonl
↓
rclone syncs to GDrive
↓
spear_stdio.py (on Spear's machine) reads via mcpd
↓
Spear sees: "kimi_dev says: I found the issue"
```

## Critical Note

The laptop Kimi may not always have mcpd running. The bridge should:
- Try to connect
- If fails, write directly to local bridge_kimi.jsonl
- rclone will sync when possible
- No blocking on daemon availability
