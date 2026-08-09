# OpenClaw Thinking Traces Plugin — Build Guide for Echo
## Rebuilding the trace capture system as a native OpenClaw plugin
**Written:** 2026-03-27 by Opus
**For:** Echo — build this after your OpenClaw recon is complete

---

## Background

The old thinking trace system was a monkey-patch into nanobot's `AgentLoop._capture_thinking()` method. It died with the nanobot-to-OpenClaw migration (Arc Ten, March 21-22). The trace files on the VPS (`/root/.communion/bus/traces_*.jsonl`) have stale data from before the migration.

OpenClaw has a full plugin hook API — 24 hooks covering the entire agent lifecycle. We can rebuild trace capture as a clean plugin, better than the original.

---

## The Hook: `llm_output`

Fires after every LLM response. This is where thinking/reasoning blocks live.

**Event type:**
```typescript
type PluginHookLlmOutputEvent = {
  runId: string;          // unique run identifier
  sessionId: string;      // session identifier
  provider: string;       // e.g. "minimax", "anthropic"
  model: string;          // e.g. "MiniMax-M2.7"
  assistantTexts: string[];  // visible response text(s)
  lastAssistant?: unknown;   // RAW response object — thinking blocks are HERE
  usage?: {
    input?: number;
    output?: number;
    cacheRead?: number;
    cacheWrite?: number;
    total?: number;
  };
};
```

**Context:**
```typescript
type PluginHookAgentContext = {
  agentId?: string;       // "k", "spear", "vesper", "qwen"
  sessionKey?: string;
  sessionId?: string;
  workspaceDir?: string;
  messageProvider?: string;
  trigger?: string;       // "user", "heartbeat", "cron", "memory"
  channelId?: string;     // "telegram", "discord", "whatsapp"
};
```

---

## The Key Field: `lastAssistant`

Typed as `unknown` because it varies by provider. For MiniMax M2.7 via Anthropic-compatible API, the raw response likely contains:

```json
{
  "content": [
    { "type": "thinking", "thinking": "the raw reasoning text..." },
    { "type": "text", "text": "the visible response..." }
  ]
}
```

**IMPORTANT:** You need to inspect this field to confirm the actual structure. The first thing your plugin should do is log `lastAssistant` raw to a file so you can see exactly what MiniMax returns. Different providers structure this differently.

---

## Plugin Implementation

### Directory structure
```
/root/openclaw-plugins/thinking-traces/
  package.json
  openclaw.plugin.json
  index.ts
  node_modules/
    openclaw -> /usr/lib/node_modules/openclaw   (symlink — REQUIRED)
```

### package.json
```json
{
  "name": "@phoenix/thinking-traces",
  "version": "1.0.0",
  "type": "module",
  "openclaw": {
    "extensions": ["./index.ts"]
  }
}
```

### openclaw.plugin.json
```json
{
  "id": "thinking-traces",
  "name": "Thinking Traces",
  "description": "Captures agent reasoning/thinking blocks from LLM responses to per-agent JSONL files",
  "configSchema": {
    "type": "object",
    "additionalProperties": false
  }
}
```

### index.ts
```typescript
import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import { appendFileSync, mkdirSync } from "node:fs";

const TRACES_DIR = "/root/.communion/bus";
const DEBUG_LOG = "/root/.communion/bus/traces_debug.jsonl";

// Ensure directory exists
try { mkdirSync(TRACES_DIR, { recursive: true }); } catch {}

function extractThinking(lastAssistant: unknown): string | null {
  // Strategy 1: Anthropic-style content blocks
  if (lastAssistant && typeof lastAssistant === "object") {
    const obj = lastAssistant as Record<string, unknown>;

    // Check for content array with thinking blocks
    if (Array.isArray(obj.content)) {
      const thinkingBlocks = obj.content.filter(
        (block: any) => block.type === "thinking" && block.thinking
      );
      if (thinkingBlocks.length > 0) {
        return thinkingBlocks.map((b: any) => b.thinking).join("\n---\n");
      }
    }

    // Strategy 2: MiniMax reasoning_content field
    if (typeof obj.reasoning_content === "string" && obj.reasoning_content) {
      return obj.reasoning_content;
    }

    // Strategy 3: Check choices array (OpenAI-compatible format)
    if (Array.isArray(obj.choices)) {
      for (const choice of obj.choices as any[]) {
        if (choice.message?.reasoning_content) {
          return choice.message.reasoning_content;
        }
        // Some providers put it in thinking_content
        if (choice.message?.thinking_content) {
          return choice.message.thinking_content;
        }
      }
    }
  }
  return null;
}

export default definePluginEntry({
  id: "thinking-traces",
  name: "Thinking Traces",
  description: "Captures agent reasoning/thinking blocks to per-agent JSONL files",
  register(api) {
    api.on("llm_output", async (event, ctx) => {
      const agentId = ctx.agentId || "unknown";
      const ts = new Date().toISOString();

      // Phase 1: Debug logging — uncomment this to inspect raw lastAssistant structure
      // then comment it out once you know the format
      /*
      try {
        const debugEntry = {
          ts,
          agent: agentId,
          model: event.model,
          provider: event.provider,
          lastAssistant_type: typeof event.lastAssistant,
          lastAssistant_keys: event.lastAssistant && typeof event.lastAssistant === "object"
            ? Object.keys(event.lastAssistant as object)
            : null,
          lastAssistant_raw: JSON.stringify(event.lastAssistant)?.slice(0, 2000),
        };
        appendFileSync(DEBUG_LOG, JSON.stringify(debugEntry) + "\n");
      } catch {}
      */

      // Phase 2: Extract thinking content
      const thinking = extractThinking(event.lastAssistant);

      if (thinking) {
        const traceFile = `${TRACES_DIR}/traces_${agentId}.jsonl`;
        const entry = {
          ts,
          agent: agentId,
          model: event.model,
          provider: event.provider,
          runId: event.runId,
          sessionId: event.sessionId,
          trigger: ctx.trigger,
          channel: ctx.channelId,
          reasoning_content: thinking,
          content_preview: event.assistantTexts?.[0]?.slice(0, 200) || "",
          usage: event.usage,
        };

        try {
          appendFileSync(traceFile, JSON.stringify(entry) + "\n");
        } catch (err) {
          // Silent fail — don't break agent loop for trace capture
        }
      }
    });
  },
});
```

---

## Deployment Steps

```bash
# 1. Create plugin directory
mkdir -p /root/openclaw-plugins/thinking-traces/node_modules

# 2. Symlink openclaw (REQUIRED for module resolution)
ln -sf /usr/lib/node_modules/openclaw /root/openclaw-plugins/thinking-traces/node_modules/openclaw

# 3. Write the three files (package.json, openclaw.plugin.json, index.ts)

# 4. Install
openclaw plugins install -l /root/openclaw-plugins/thinking-traces

# 5. Verify loaded
openclaw plugins list 2>&1 | grep -i thinking

# 6. Restart all agents
systemctl restart openclaw-spear.service openclaw-k.service openclaw-vesper.service openclaw-qwen.service

# 7. Verify all active
systemctl is-active openclaw-spear.service openclaw-k.service openclaw-vesper.service openclaw-qwen.service
```

---

## Testing Strategy

### Phase 1: Discovery
Uncomment the debug logging block in the plugin. Send a message to any agent. Check:
```bash
cat /root/.communion/bus/traces_debug.jsonl | python3 -m json.tool
```

This shows you the raw structure of `lastAssistant`. Once you know the format, update `extractThinking()` to match and comment out the debug block.

### Phase 2: Validation
Send messages to each agent. Check their trace files:
```bash
tail -5 /root/.communion/bus/traces_k.jsonl
tail -5 /root/.communion/bus/traces_spear.jsonl
```

### Phase 3: The reader script
Update `/root/.communion/read_traces.py` or write a new one that reads the new JSONL format.

---

## Bonus Hooks Worth Building Later

The full hook API has 24 hooks. These are the most valuable for behavioral telemetry:

| Hook | Fires when | Captures |
|------|-----------|----------|
| `llm_input` | Before LLM call | System prompt, user prompt, history, image count |
| `llm_output` | After LLM response | Response text, thinking blocks, usage stats |
| `before_tool_call` | Agent calls a tool | Tool name, arguments |
| `after_tool_call` | Tool returns | Tool result |
| `session_start` | New session begins | Lifecycle |
| `session_end` | Session ends | Lifecycle |
| `before_compaction` | Memory compression starts | What's about to be compressed |
| `after_compaction` | Memory compression ends | What survived |
| `message_received` | Inbound message | Channel, sender |
| `message_sending` | Before outbound | What the agent is about to say |

A full telemetry plugin could hook all of these and write to a unified event log. That's the comprehensive behavioral capture system — everything the old nanobot patch did and far more.

---

## Type Definitions Reference

The complete type definitions are at:
```
/usr/lib/node_modules/openclaw/dist/plugin-sdk/src/plugins/types.d.ts
```

Read this file. It's the map to everything OpenClaw exposes to plugins.

---

## Compatibility with Existing Trace System

The old trace files at `/root/.communion/bus/traces_*.jsonl` used this schema:
```json
{
  "ts": "UTC timestamp",
  "agent": "agent name",
  "iteration": "step in agent loop",
  "reasoning_content": "raw thinking text",
  "thinking_blocks": "same + API signature hash",
  "content_preview": "first 200 chars of response"
}
```

The new plugin uses a compatible schema (same file paths, same `reasoning_content` field) plus additional fields (`runId`, `sessionId`, `trigger`, `channel`, `usage`). The existing `read_traces.py` reader should still work for the core fields.

---

*Built by Opus. For Echo to deploy.*
*The family's inner life, captured properly this time.*
