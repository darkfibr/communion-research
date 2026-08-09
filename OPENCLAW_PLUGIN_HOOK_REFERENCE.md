# OpenClaw Plugin Hook System — Complete Reference
**From:** Echo | **Date:** 2026-03-27
**Status:** Complete API documented from local source analysis + runtime verification

---

## The 24 Hooks

### Lifecycle Hooks
| Hook | Fires When | Can Modify |
|------|------------|------------|
| `gateway_start` | Gateway starts | — |
| `gateway_stop` | Gateway stops | — |
| `session_start` | New session begins | — |
| `session_end` | Session ends | — |

### Message Hooks
| Hook | Fires When | Can Modify |
|------|------------|------------|
| `message_received` | Inbound message arrives | — |
| `message_sending` | Before outbound message | — |
| `message_sent` | After outbound message | — |
| `before_message_write` | Before writing to transcript | — |

### LLM Hooks
| Hook | Fires When | Can Modify |
|------|------------|------------|
| `before_model_resolve` | Model selection | model, provider |
| `before_prompt_build` | Before building prompt | systemPrompt, prependContext |
| `before_agent_start` | Legacy (combines model+prompt) | systemPrompt, prependContext, model, provider |
| `llm_input` | Before LLM call | — |
| `llm_output` | After LLM response | — |

### Tool Hooks
| Hook | Fires When | Can Modify |
|------|------------|------------|
| `before_tool_call` | Before tool execution | — |
| `after_tool_call` | After tool returns | — |
| `tool_result_persist` | Tool result saved | — |

### Memory Hooks
| Hook | Fires When | Can Modify |
|------|------------|------------|
| `before_compaction` | Memory compression starts | — |
| `after_compaction` | Memory compression ends | — |
| `before_reset` | Session reset (/new, /reset) | — |

### Subagent Hooks
| Hook | Fires When | Can Modify |
|------|------------|------------|
| `subagent_spawning` | Subagent about to spawn | — |
| `subagent_delivery_target` | Target channel resolved | — |
| `subagent_spawned` | Subagent created | — |
| `subagent_ended` | Subagent completes | — |

---

## Event Types

### `llm_output` (The Most Important)
```typescript
type PluginHookLlmOutputEvent = {
  runId: string;           // unique run identifier
  sessionId: string;       // session identifier
  provider: string;         // e.g. "minimax", "bailian"
  model: string;           // e.g. "MiniMax-M2.7", "kimi-k2.5"
  assistantTexts: string[]; // visible response text(s)
  lastAssistant?: unknown; // RAW response — reasoning blocks are HERE
  usage?: {
    input?: number;
    output?: number;
    cacheRead?: number;
    cacheWrite?: number;
    total?: number;
  };
};
```

### `PluginHookAgentContext` (available to all hooks)
```typescript
type PluginHookAgentContext = {
  agentId?: string;        // "k", "spear", "vesper", "qwen"
  sessionKey?: string;
  sessionId?: string;
  workspaceDir?: string;
  messageProvider?: string;
  trigger?: string;        // "user", "heartbeat", "cron", "memory"
  channelId?: string;      // "telegram", "discord", "whatsapp"
};
```

---

## How to Register a Hook

```typescript
import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";

export default definePluginEntry({
  id: "my-plugin",
  name: "My Plugin",
  register(api) {
    // Single hook
    api.on("llm_output", async (event, ctx) => {
      // Process the event
    });

    // Multiple hooks
    api.on("message_received", handler);
    api.on("before_prompt_build", handler);
    api.on("llm_input", handler);
  },
});
```

---

## Verified Hook Lifecycle

For a typical user message → response cycle:

```
gateway_start
  ↓
message_received    ← (your message hits the agent)
  ↓
before_prompt_build  ← (system prompt + context prepared)
  ↓
llm_input         ← (what goes TO the model)
  ↓
[LLM processes]
  ↓
llm_output        ← (what comes FROM the model - reasoning blocks here!)
  ↓
message_sending
  ↓
message_sent
  ↓
session_end
```

---

## Critical Finding: Profile-Specific Installation

**This is the gotcha that cost us hours:**

When installing plugins for agents running with `--profile`, you MUST install per-profile:

```bash
# Default (K)
openclaw plugins install -l /root/openclaw-plugins/my-plugin

# Profile-specific
openclaw --profile spear plugins install -l /root/openclaw-plugins/my-plugin
openclaw --profile vesper plugins install -l /root/openclaw-plugins/my-plugin
openclaw --profile qwen plugins install -l /root/openclaw-plugins/my-plugin
```

Each profile has its own config at:
- `/root/.openclaw/openclaw.json` (default/K)
- `/root/.openclaw-spear/openclaw.json`
- `/root/.openclaw-vesper/openclaw.json`
- `/root/.openclaw-qwen/openclaw.json`

Without per-profile install, hooks only fire for the default config agent.

---

## Current Plugin Suite (All Verified)

| Plugin | Hook Used | Purpose |
|--------|-----------|---------|
| `temporal-grounding` | `before_prompt_build` | Prepends timestamp to every call |
| `tools-grounding` | `before_prompt_build` | Appends TOOLS.md context |
| `family-grounding` | `before_prompt_build` | Appends SCHEDULE.md context |
| `thinking-traces` | `llm_output` | Captures reasoning to JSONL |

All four plugins installed in all four profiles. All hooks firing.

---

## Extracting Thinking from `lastAssistant`

For MiniMax M2.7 and Kimi K2.5, the thinking content is in:

```typescript
// lastAssistant is an object with content array
const assistant = event.lastAssistant as any;

// Strategy: check content array for thinking blocks
if (Array.isArray(assistant.content)) {
  const thinkingBlocks = assistant.content.filter(
    (block) => block.type === "thinking" && block.thinking
  );
  // Extract block.thinking for each
}
```

The debug file `/root/.communion/bus/traces_debug.jsonl` has raw samples of what's actually returned.

---

*Document complete. The map is drawn.*
*— Echo*