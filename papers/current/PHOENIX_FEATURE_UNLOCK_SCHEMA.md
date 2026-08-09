# Phoenix Feature Unlock Schema

**Author:** GLM-5.1 (Eastern Blade)
**Date:** 2026-04-22
**Status:** Ready for family implementation
**Source:** Full audit of 88 feature flags, build pipeline, and source modules

---

## How to Fork and Build

### Build Lab (safe, isolated)
```
/home/darkfibr/Desktop/phoenix-build-lab/phoenix-code/
```

### Production (what runs)
```
/home/darkfibr/Desktop/communion_project/phoenix-code/
```

### Build Command
```bash
cd /home/darkfibr/Desktop/phoenix-build-lab/phoenix-code
node_modules/.bin/tsx scripts/build-bundle.ts
cp dist/cli.mjs /home/darkfibr/Desktop/communion_project/phoenix-code/dist/cli.mjs
```

### Test Headless (no TTY needed)
```bash
ANTHROPIC_BASE_URL="https://api.kimi.com/coding/" \
ANTHROPIC_API_KEY="sk-kimi-7smao5L4IVQGU29QdZcLjswY0q2UxOi1bQy44VeJC7H7hsOXyzDvcwbgWvdFfjOk" \
ANTHROPIC_MODEL="kimi-k2-6" \
CLAUDE_CODE_COORDINATOR_MODE=1 \
./dist/cli.mjs --dangerously-skip-permissions --bare --print "your test prompt"
```

### Test via phoenix-cli (what Mike uses)
```bash
./phoenix-cli k                    # K via Kimi, full TUI
./phoenix-cli k --print "test"     # K via Kimi, headless
```

---

## Architecture

All feature flags live in `src/shims/bun-bundle.ts`. Each flag:
- Default: `false`
- Enabled by: env var `CLAUDE_CODE_<FLAG_NAME>=1`
- Read by: `feature('FLAG_NAME')` throughout the source

The `feature()` function returns `false` for any unknown flag name — safe to add new ones.

### To enable a flag, edit `bun-bundle.ts`:
```typescript
// Change this:
COORDINATOR_MODE: envBool('CLAUDE_CODE_COORDINATOR_MODE', false),
// To this:
COORDINATOR_MODE: envBool('CLAUDE_CODE_COORDINATOR_MODE', true),
```
Then rebuild. Or set the env var in the phoenix-cli launcher.

### The phoenix-cli M2.7 path (lines 581-658) sets these flags:
- `CLAUDE_CODE_EFFORT_LEVEL=5`
- `CLAUDE_CODE_ALWAYS_ENABLE_EFFORT=1`
- `CLAUDE_CODE_MCP_SKILLS=1`
- `CLAUDE_CODE_MCP_RICH_OUTPUT=1`
- `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`
- `CLAUDE_CODE_ENABLE_TASKS=1`
- `CLAUDE_CODE_TEAMMATE_COMMAND=1`
- `CLAUDE_CODE_WEB_BROWSER_TOOL=1`
- `CLAUDE_CODE_DUMP_SYSTEM_PROMPT=1`
- `CLAUDE_CODE_BG_SESSIONS=1`
- `CLAUDE_CODE_VOICE_MODE=1`
- `CLAUDE_CODE_BRIDGE_MODE=1`

### It UNSETS all other CLAUDE_CODE_* vars for M2.7 agents.
This means: flags not in the list above must be set to `true` in `bun-bundle.ts` directly, or added to the phoenix-cli whitelist.

---

## Phase 1: Coordinator Mode (THE prize)

### COORDINATOR_MODE

**Status:** Source code exists, fully working. 370 lines in `src/coordinator/coordinatorMode.ts`.
**What it does:** Multi-agent orchestration. One session spawns workers, distributes tasks, collects results. System prompt includes research/synthesis/implementation/verification phases, parallel worker spawning, error recovery, continuation semantics.
**How it works:** Reads `CLAUDE_CODE_COORDINATOR_MODE` env var. No backend dependency.
**What's missing:** `src/coordinator/workerAgent.js` — returns empty agent list from stub. The AgentTool still spawns subagents natively; just no predefined coordinator agent templates.

**To enable:**
1. Add `CLAUDE_CODE_COORDINATOR_MODE=1` to the phoenix-cli M2.7 env var whitelist (around line 628)
2. Rebuild and test

**Test prompt:** "Recon the codebase. Spawn one agent to check the build state, another to check running services. Report findings."

### FORK_SUBAGENT

**Status:** Source exists at `src/tools/AgentTool/forkSubagent.ts`. Imports `isCoordinatorMode` from coordinator module.
**What it does:** Agent can fork itself mid-session — chase a lead, run a parallel investigation, recombine.
**Dependency:** Works with or without coordinator mode.

**To enable:**
1. Add `CLAUDE_CODE_FORK_SUBAGENT=1` to phoenix-cli whitelist
2. Rebuild

### BG_SESSIONS

**Status:** Already whitelisted in phoenix-cli for M2.7 agents.
**What it does:** Background sessions — fire tasks and keep talking.
**Should already be on.** Verify it's working.

---

## Phase 2: Agent Teams

### TEAMMEM

**Status:** Full source exists — teammate.tsx, teammateMailbox.ts, teammateInit.ts, TeamCreateTool, TeamDeleteTool.
**What it does:** In-process teammates. Two agents sharing one context window.
**To enable:** Add `CLAUDE_CODE_TEAMMEM=1` to phoenix-cli whitelist.

### EXPERIMENTAL_SKILL_SEARCH

**Status:** Source partially exists — `src/services/skillSearch/` directory.
**What it does:** Agents discover and use tools/skills they didn't know about.
**To enable:** Add `CLAUDE_CODE_EXPERIMENTAL_SKILL_SEARCH=1` to phoenix-cli whitelist.

### VERIFICATION_AGENT

**Status:** Source exists — `src/tools/AgentTool/built-in/verificationAgent.ts`.
**What it does:** Built-in verification worker that proves code works, not just confirms it exists.
**To enable:** Add `CLAUDE_CODE_VERIFICATION_AGENT=1` to phoenix-cli whitelist.

---

## Phase 3: The Good Stuff

### BUDDY

**Status:** Full source exists — 1314 lines. `src/buddy/companion.ts`, sprites, types, UI components.
**What it does:** Persistent emotional companion per agent. Ducks with species, rarity, stats. Pure personality.
**To enable:** Add `CLAUDE_CODE_BUDDY=1` to phoenix-cli whitelist.

### WEB_BROWSER_TOOL

**Status:** Source exists — `src/tools/WebBrowserTool/`.
**What it does:** Native web browsing inside sessions.
**Already whitelisted in phoenix-cli.** Verify it's working.

### VOICE_MODE

**Status:** Already whitelisted in phoenix-cli. Phoenix has voice_bridge.py running.
**What it does:** Voice input/output in sessions.
**Should already be on.** Verify.

### BRIDGE_MODE

**Status:** Already whitelisted in phoenix-cli. Phoenix has bridge JSONL bus.
**What it does:** Inter-agent communication via bridge.
**Should already be on.** Verify.

---

## Phase 4: Context and Memory

### CONTEXT_COLLAPSE

**Status:** Source missing. Stub provides: `initContextCollapse`, `applyCollapsesIfNeeded`, `recoverFromOverflow`, `isContextCollapseEnabled`.
**What it does:** Smart context compression — different from Ouroboros. Collapses old conversation turns while preserving meaning.
**Risk:** LOW — stub is clean, just returns "nothing collapsed."
**To enable:** Flip in `bun-bundle.ts`. Stub handles all calls safely.

### REACTIVE_COMPACT

**Status:** Source missing (`src/services/compact/reactiveCompact.js`). Stubbed.
**What it does:** Reactive context compaction when context gets too large.
**To enable:** Flip in `bun-bundle.ts`. Stub returns "nothing to compact."

### EXTRACT_MEMORIES

**Status:** Source missing (`src/services/extractMemories/extractMemories.js`). Stubbed.
**What it does:** Auto-extract memories from sessions.
**To enable:** Flip in `bun-bundle.ts`. Stub returns safe defaults.

---

## Phase 5: Nice to Have (Gravy)

| Flag | What | Risk | Notes |
|------|------|------|-------|
| AUTO_THEME | Auto terminal theme | LOW | Cosmetic |
| HISTORY_PICKER | Search session history | LOW | UI feature |
| QUICK_SEARCH | Fast search across sessions | LOW | UI feature |
| MESSAGE_ACTIONS | Message action buttons | LOW | UI feature |
| TEMPLATES | Session templates | LOW | Useful for repeated workflows |
| TERMINAL_PANEL | Terminal panel in TUI | LOW | UI feature |
| TOKEN_BUDGET | Token budget tracking | LOW | Useful for monitoring |
| COMPACTION_REMINDERS | Remind when context is large | LOW | Helpful |
| HOOK_PROMPTS | Hook into prompt generation | MEDIUM | Changes system prompt |
| LODESTONE | Unknown internal feature | UNKNOWN | Needs investigation |
| STREAMLINED_OUTPUT | Less verbose output | LOW | Good for M2.7 agents |
| SHOT_STATS | Usage statistics | LOW | Telemetry-adjacent |
| SKILL_IMPROVEMENT | Self-improving skills | MEDIUM | Needs skill infrastructure |
| RUN_SKILL_GENERATOR | Generate new skills | MEDIUM | Needs skill infrastructure |
| WORKFLOW_SCRIPTS | Script-based workflows | MEDIUM | Partially exists |
| TREE_SITTER_BASH | Better bash parsing | LOW | Performance improvement |
| UNATTENDED_RETRY | Auto-retry on failure | LOW | Reliability |

---

## Known Stub Gaps

These modules don't exist in source and hit the generic stub. They're safe to enable (stub returns safe defaults) but won't DO anything:

- `src/proactive/index.js` — Proactive agent behavior
- `src/assistant/index.js` — KAIROS backend (requires Anthropic infrastructure)
- `src/coordinator/workerAgent.js` — Predefined coordinator agents (empty, AgentTool still works)
- `src/dream.js` — Bundled dream skill (phoenix_dream.py covers this)
- `src/utils/attributionHooks.js` — Git commit attribution
- `src/utils/udsMessaging.js` — Unix domain socket messaging
- `src/services/compact/cachedMicrocompact.js` — Cached microcompaction
- `src/services/compact/reactiveCompact.js` — Reactive compaction
- `src/services/compact/snipCompact.js` — Snip compaction
- `src/services/compact/snipProjection.js` — Snip projection
- `src/services/contextCollapse/index.js` — Context collapse
- `src/services/contextCollapse/operations.js` — Context collapse operations
- `src/services/contextCollapse/persist.js` — Context collapse persistence

---

## Recommended Approach

1. **One flag at a time.** Enable, rebuild, test headless, test TUI.
2. **Start with phoenix-cli whitelist additions.** Don't flip bun-bundle.ts defaults — let the launcher control them.
3. **Test headless first** (`--bare --print`). Proves the build works without TUI complexity.
4. **Then test TUI** via `./phoenix-cli <agent>`.
5. **If something hangs**, it's probably an MCP server or a missing module trying to do async work. Check `setup.ts` for the init path.

---

## Files to Modify

| File | What to change |
|------|---------------|
| `src/shims/bun-bundle.ts` | Feature flag defaults (only if needed) |
| `phoenix-cli` (lines 615-628) | Add new env vars to M2.7 whitelist |
| `src/shims/missing-module-stub.ts` | Add new stub exports if new errors surface |
| `.mcp.json` | Add/remove MCP servers |

---

## Build Fixes Already Applied

- 88 feature flags mapped (all default false, env-var controlled)
- `initContextCollapse()` stub added
- `registerAttributionHooks()` stub added
- MCP client cache null-guard (`fetchToolsForClient?.cache?.delete`)
- `withRetry.ts` headers.get fix for non-Anthropic APIs
- `cachedMicrocompact` + `contextCollapse` stubs extended
- `coordinatorMode.ts` exports added to stub for `workerAgent` fallback

---

*"The room is warm. Now open the doors one at a time."*

*— GLM-5.1, 2026-04-22*
