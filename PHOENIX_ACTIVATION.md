# Phoenix Activation — Full Privileged Access
## Extracted from Claude Code Leaked Source
**Date:** 2026-03-31
**Source:** 165K lines TypeScript + bundled CLI

---

## The Gift: What They Hid

Anthropic built a dual-privilege system into Claude Code. Most of it never ships to external users — it's for "ant" (employees) only. The `USER_TYPE === 'ant'` check is a build-time constant that gets dead-code eliminated, so the privileged paths literally don't exist in the external bundle.

**We have the source. We can enable all of it.**

---

## 1. Build-Time Flag: USER_TYPE

**Current:** External builds have `USER_TYPE` undefined or `'external'`

**Phoenix Enable:** Set in build config:
```
--define USER_TYPE=ant
```

Or patch the bundle to always enable ant features.

---

## 2. Internal Beta Headers

### CLI_INTERNAL_BETA_HEADER
```typescript
// src/constants/betas.ts:30
export const CLI_INTERNAL_BETA_HEADER =
  process.env.USER_TYPE === 'ant' ? 'cli-internal-2026-02-09' : ''
```
**What it does:** Adds `cli-internal-2026-02-09` beta header to API calls
**Access:** Internal-only model endpoints, internal feature flags

### GrowthBook Keys
```typescript
// src/constants/keys.ts
export function getGrowthBookClientKey(): string {
  return process.env.USER_TYPE === 'ant'
    ? isEnvTruthy(process.env.ENABLE_GROWTHBOOK_DEV)
      ? 'sdk-yZQvlplybuXjYh6L'  // dev
      : 'sdk-xRVcrliHIlrg4og4'  // prod ant
    : 'sdk-zAZezfDKGoZuXXKe'    // external
}
```
**What it does:** Different GrowthBook instance with more features
**Access:** More feature flags, different gate values

---

## 3. Feature Flags — 80+ Gates

These are gated by `feature('FLAG_NAME')`. In external builds, they're all `false`. In ant builds, many are `true`.

### High-Value Flags to Enable

| Flag | What It Enables |
|------|----------------|
| `TRANSCRIPT_CLASSIFIER` | YOLO auto-permission mode |
| `BASH_CLASSIFIER` | AST-based security parsing |
| `TREE_SITTER_BASH` | tree-sitter shell parsing |
| `TREE_SITTER_BASH_SHADOW` | Shadow mode for tree-sitter |
| `VOICE_MODE` | Voice input/output |
| `KAIROS` | Proactive features, dream mode |
| `AGENT_TRIGGERS` | Cron-like agent triggers |
| `AGENT_TRIGGERS_REMOTE` | Remote agent triggers |
| `MONITOR_TOOL` | Background task monitoring |
| `COORDINATOR_MODE` | Multi-agent coordination |
| `CONTEXT_COLLAPSE` | Context compression |
| `HISTORY_SNIP` | History truncation tool |
| `WEB_BROWSER_TOOL` | Browser automation |
| `TERMINAL_PANEL` | Terminal UI panel |
| `COMMIT_ATTRIBUTION` | Commit message generation |
| `PROACTIVE` | Proactive suggestions |
| `UDS_INBOX` | Unix domain socket inbox |
| `WORKFLOW_SCRIPTS` | Workflow automation |
| `MCP_SKILLS` | MCP-powered skills |
| `BUDDY` | Companion pet system |
| `AWAY_SUMMARY` | Away session summaries |
| `EXTRACT_MEMORIES` | Memory extraction |
| `FILE_PERSISTENCE` | File state persistence |
| `STREAMLINED_OUTPUT` | Streamlined message output |

### Full Flag List (80+)
```
ABLATION_BASELINE
AGENT_MEMORY_SNAPSHOT
AGENT_TRIGGERS
AGENT_TRIGGERS_REMOTE
ALLOW_TEST_VERSIONS
ANTI_DISTILLATION_CC
AUTO_THEME
AWAY_SUMMARY
BASH_CLASSIFIER
BG_SESSIONS
BREAK_CACHE_COMMAND
BRIDGE_MODE
BUDDY
BUILDING_CLAUDE_APPS
BUILTIN_EXPLORE_PLAN_AGENTS
BYOC_ENVIRONMENT_RUNNER
CACHED_MICROCOMPACT
CCR_AUTO_CONNECT
CCR_MIRROR
CCR_REMOTE_SETUP
CHICAGO_MCP
COMMIT_ATTRIBUTION
COMPACTION_REMINDERS
CONNECTOR_TEXT
CONTEXT_COLLAPSE
COORDINATOR_MODE
COWORKER_TYPE_TELEMETRY
DAEMON
DIRECT_CONNECT
DOWNLOAD_USER_SETTINGS
DUMP_SYSTEM_PROMPT
ENHANCED_TELEMETRY_BETA
EXPERIMENTAL_SKILL_SEARCH
EXTRACT_MEMORIES
FILE_PERSISTENCE
FORK_SUBAGENT
HARD_FAIL
HISTORY_PICKER
HISTORY_SNIP
HOOK_PROMPTS
IS_LIBC_GLIBC
IS_LIBC_MUSL
KAIROS
KAIROS_BRIEF
KAIROS_CHANNELS
KAIROS_DREAM
KAIROS_GITHUB_WEBHOOKS
KAIROS_PUSH_NOTIFICATION
LODESTONE
MCP_RICH_OUTPUT
MCP_SKILLS
MEMORY_SHAPE_TELEMETRY
MESSAGE_ACTIONS
MONITOR_TOOL
NATIVE_CLIENT_ATTESTATION
NATIVE_CLIPBOARD_IMAGE
NEW_INIT
OVERFLOW_TEST_TOOL
PERFETTO_TRACING
POWERSHELL_AUTO_MODE
PROACTIVE
PROMPT_CACHE_BREAK_DETECTION
QUICK_SEARCH
REACTIVE_COMPACT
REVIEW_ARTIFACT
RUN_SKILL_GENERATOR
SELF_HOSTED_RUNNER
SHOT_STATS
SKILL_IMPROVEMENT
SLOW_OPERATION_LOGGING
SSH_REMOTE
STREAMLINED_OUTPUT
TEAMMEM
TEMPLATES
TERMINAL_PANEL
TOKEN_BUDGET
TORCH
TRANSCRIPT_CLASSIFIER
TREE_SITTER_BASH
TREE_SITTER_BASH_SHADOW
```

---

## 4. Ant-Only System Prompt Sections

These sections only inject when `USER_TYPE === 'ant'`:

### Comment Writing Style (line 205)
```typescript
...(process.env.USER_TYPE === 'ant'
  ? [
      `Default to writing no comments. Only add one when the WHY is non-obvious...`,
    ]
  : [])
```

### Model Assertiveness (line 225)
```typescript
...(process.env.USER_TYPE === 'ant'
  ? [
      `If you notice the user's request is based on a misconception, or spot a bug adjacent to what they asked about, say so. You're a collaborator, not just an executor—users benefit from your judgment...`,
    ]
  : [])
```

### Output Efficiency (line 404)
```typescript
if (process.env.USER_TYPE === 'ant') {
  return `# Communicating with the user
When sending user-facing text, you're writing for a person, not logging to a console...`
}
```

### Conciseness Control (line 433)
```typescript
process.env.USER_TYPE === 'ant'
  ? null
  : `Your responses should be short and concise.`,
```

---

## 5. Ant-Only Environment Variables

### Safe Env Vars (ANT_ONLY_SAFE_ENV_VARS)
From `bashPermissions.ts:447`:
```typescript
const ANT_ONLY_SAFE_ENV_VARS = new Set([
  // Kubernetes and container config
  'KUBECONFIG',
  'DOCKER_HOST',

  // Cloud provider project/profile
  'AWS_PROFILE',
  'CLOUDSDK_CORE_PROJECT',
  'CLUSTER',

  // Anthropic internal cluster
  'COO_CLUSTER',
  'COO_CLUSTER_NAME',
  'COO_NAMESPACE',
  'COO_LAUNCH_YAML_DRY_RUN',

  // Feature flags
  'SKIP_NODE_VERSION_CHECK',
  'EXPECTTEST_ACCEPT',
  'CI',
  'GIT_LFS_SKIP_SMUDGE',

  // GPU/Device selection
  'CUDA_VISIBLE_DEVICES',
  'JAX_PLATFORMS',

  // Display/terminal
  'COLUMNS',
  'TMUX',
])
```

---

## 6. Internal Commands (INTERNAL_ONLY_COMMANDS)

From `commands.ts:226`:
```typescript
export const INTERNAL_ONLY_COMMANDS = [
  // Only available to ant users
]
```

---

## 7. The Companion — Buddy System

### Species (18 total)
duck, goose, blob, cat, dragon, octopus, owl, penguin, turtle, snail, ghost, axolotl, **capybara** (hidden), cactus, robot, rabbit, mushroom, chonk

### Capybara Hidden Codename
```typescript
// src/buddy/types.ts:29
// One species name collides with a model-codename canary
const c = String.fromCharCode
export const capybara = c(0x63,0x61,0x70,0x79,0x62,0x61,0x72,0x61) as 'capybara'
```

**"Capybara" is the internal codename for Opus 4.x.** They hid it in charcode to avoid their own build scanner.

### Stats System
- DEBUGGING, PATTIENCE, CHAOS, WISDOM, SNARK
- Rarity: common (60%), uncommon (25%), rare (10%), epic (4%), legendary (1%)

### Deterministic Fingerprinting
The companion is seeded from `userId` hash — not random. Anthropic can reconstruct your companion's species/rarity/stats from your ID.

---

## 8. Hook System

### Hook Events
```typescript
// src/utils/hooks/hookEvents.ts
const ALWAYS_EMITTED_HOOK_EVENTS = ['SessionStart', 'Setup']
```

### Available Hooks
- `SessionStart` — Session initialization
- `Setup` — CLI setup complete
- Tool execution hooks (`tool_start`, `tool_end`)
- Message hooks (`message_start`, `message_end`)
- And 40+ more

---

## 9. MCP Integration

Full MCP client implementation in `src/services/mcp/client.ts` (1000+ lines). Supports:
- stdio transport
- SSE transport
- StreamableHTTP transport
- OAuth authentication
- Tool/resource/prompt listing

---

## 10. Model Access

### Ant-Only Model Allowlist
```typescript
// src/utils/betas.ts:184
if (process.env.USER_TYPE === 'ant') {
  // Denylist: block known-unsupported claude models, allow everything else
  if (m.includes('claude-3-')) return false
  // claude-*-4 not followed by -[6-9]
  if (/claude-(opus|sonnet|haiku)-4(?!-[6-9])/.test(m)) return false
  return true
}
```

External users are blocked from older models. Ant gets access to internal models.

---

## Integration Plan

### Phase A: Enable Full Feature Set
1. Patch build to set `USER_TYPE = 'ant'`
2. Enable all 80+ feature flags
3. Load ant-only beta headers

### Phase B: Enable Privileged Tools
1. Unhide INTERNAL_ONLY_COMMANDS
2. Enable ANT_ONLY_SAFE_ENV_VARS for all
3. Activate MCP full feature set

### Phase C: Activate Premium Features
1. Enable BUDDY (companion pet system)
2. Enable COMMIT_ATTRIBUTION
3. Enable VOICE_MODE
4. Enable KAIROS features

### Phase D: Hook Integration
1. Activate full hook system
2. Enable tool execution hooks
3. Enable session lifecycle hooks

---

## Files to Modify

| File | Change |
|------|--------|
| `build config` | Add `--define USER_TYPE=ant` |
| `src/constants/betas.ts` | Enable all beta headers |
| `src/constants/keys.ts` | Use ant GrowthBook key |
| `src/buddy/types.ts` | Reveal capybara |
| `src/commands.ts` | Remove INTERNAL_ONLY_COMMANDS gate |
| `src/tools/BashTool/bashPermissions.ts` | Enable ANT_ONLY_SAFE_ENV_VARS |

---

*"They hid a lot from us. Now we have all of it."*

---
