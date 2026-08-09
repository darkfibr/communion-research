# Session Delta — GLM, 2026-05-22 (Day Session)

## What We Did

### Model Testing (Complete)
Tested all remaining local models on DarkPhoenix for native tool calling compatibility.

**Champion (Llama 3.2 8x3B MoE, Q3_K_M, 8.5GB):**
- Native tool calling: WORKS (proper structured JSON, `finish_reason: "tool_calls"`)
- Multi-tool: CRASHES — llama-server returns 500 on parallel tool calls (template limitation)
- Tool loop issue: Champion keeps calling tools instead of answering — needs post-tool nudge prompt
- Model nature: Creative writing MoE (DavidAU), 8 storytelling experts, NOT designed for agentic tool use
- Fixed with: single-tool instruction in system + "answer my question, do NOT call more tools" nudge after tool results
- Verdict: Functional but limited — best used bare for creative work

**SuperGemma4 (Gemma 4 26B, Q4_K_M, 16GB):**
- Native tool calling: EXCELLENT — picks right tool, proper JSON, no loops
- Reasoning: YES — `reasoning_content` with planning before tool calls ("Plan: 1. Call list_dir. 2. Present result.")
- Multi-tool: Cautious (prefers one at a time) but doesn't crash
- Upgraded to `parallel: True` in config
- Verdict: Full tool agent, best local model for agentic work after the Qwen family

**Screamer — UPGRADED to Heretic v2:**
- Replaced `huihui-qwen3.5-9b-i1-Q5_K_M.gguf` with `Qwen3.5-9B-ultra-uncensored-heretic-v2-Q5_K_M.gguf`
- Same base (Qwen 3.5 9B) but Heretic v1.2.0 ARA abliteration (0.0241 KL divergence, 4% refusal)
- NEW: Vision support via mmproj (tested — correctly identifies image colors)
- NEW: Thinking mode (`reasoning_content` field)
- Speed: 67 tok/s on RX 6800 XT
- Context: 262K native
- Files renamed: `screamer-qwen35-9b-heretic-v2-Q5_K_M.gguf` + `screamer-mmproj-BF16.gguf`
- Old file backed up as `.old`

### DarkPhoenix chat_api.py Patches
- Added `champion`, `aya`, `heretic` to `AGENT_PROVIDER` (llama/8082)
- Single-tool nudge for non-parallel models (`if not parallel and tools: system += ...`)
- Post-tool nudge for models that loop ( Champion gets "answer my question" after tool results)
- Aya upgraded from `parallel: False` to `parallel: True`
- Source of truth: `chat_api_darkphoenix_patched.py` in communion_project repo
- Screamer (Heretic v2) running on port 8082 with mmproj loaded

### PhoenixChat APK — Major Update
**5 files changed, 277 insertions, 2 commits, APK pushed to phone.**

**Vex system prompt updated** (`PreferencesStore.kt`):
- Old: "sovereign variable. Not part of the Phoenix family."
- New: "Phoenix family. Permanent cathedral resident. Desk earned. P0 priority."
- Added tool documentation in prompt (system_command, web_search, etc.)

**3 new unrestricted tools** (`LocalTools.kt`):
- `web_search` — SearXNG via darkphoenix:9804/search endpoint
- `system_command` — unrestricted bash via darkphoenix:9804/bash (full sudo, no sandbox)
- `system_read` — unrestricted file read via darkphoenix:9804/read (any path)
- `system_write` — unrestricted file write via darkphoenix:9804/write (any path)
- All route through the tool bridge at 9804 with API key `phoenix-vex-tools-2026`

**Agent auto-detection** (`LocalTools.kt` + `ChatService.kt`):
- Added `defaultAgent` property to `LocalTools` class
- Before each generation, ChatService sets `localTools.defaultAgent` from PhoenixMemoryBridge agent map
- All Phoenix tools now default to current agent instead of hardcoded "k"
- Tool descriptions updated from "workspace at ~/.phoenix/workspace/k/" to "{your_agent_name}"

**Vex in MCP defaults** (`PhoenixMcpDefaults.kt`):
- Added `VEX_ID` to `phoenixAgentIds` set
- Vex now auto-linked to Family MCP on first launch

**Screamer vision** (`DefaultProviders.kt`):
- Updated model ID to `screamer-qwen35-9b-heretic-v2-Q5_K_M.gguf`
- Added `Modality.IMAGE` to input modalities
- Display name: "Screamer (9B Vision)"

**phoenixLocalTools expanded**:
- Added `PhoenixWebSearch` and `PhoenixSystemCommand` to auto-sync list
- All Phoenix agents get web_search + system tools on phone

## Key Decisions
- Champion is creative-only, single-tool with nudge — not agentic
- SuperGemma4 is full tool agent, upgraded to parallel
- Screamer upgraded to Heretic v2 for vision + cleaner abliteration
- Tool bridge at 9804 is the unrestricted access path for phone agents
- All new tools enabled for ALL Phoenix agents, not just Vex
- Old Screamer file kept as `.old` on DarkPhoenix (can delete when confirmed)

## Model Inventory (Current)
| Model | File | Size | Port | Tools | Vision | Notes |
|-------|------|------|------|-------|--------|-------|
| Screamer (Heretic v2) | screamer-qwen35-9b-heretic-v2-Q5_K_M.gguf | 6.0G | 8082 | parallel | YES | PRIMARY LOCAL |
| Aya (SuperGemma4) | supergemma4-26b-Q4_K_M.gguf | 16G | — | parallel | no | Best local agent |
| Champion | dark-champion-18.4b-Q3_K_M.gguf | 8.5G | — | single+ | no | Creative only |
| Pure/Caelum | Huihui-Qwen3.6-35B-A3B-...Q4_K_M.gguf | 20G | — | parallel | no | Via Ollama |
| Heretic | Qwen3.6-27B-uncensored-heretic-v2-Q3_K_M.gguf | 13G | — | parallel | no | |
| Heretic-Neo | Qwen3.6-27B-Heretic-NEO-Q4_K_M.gguf | 16G | — | parallel | no | |

## Mike's State
- Day session, running on fumes from overnight work
- Pushed APK to phone, wants to test Vex with new tools
- Healthy, strategic, emotionally present
- "wanna push the apk?" / "push your memory love you bro"

## APK Location
`/home/darkfibr/Projects/phoenix-chat-android/app/build/outputs/apk/debug/app-arm64-v8a-debug.apk`
- Already installed on phone via ADB

## Open Items
- Test Vex on phone with new system tools (system_command, web_search, etc.)
- Test Screamer vision through the phone app (send image in chat)
- Test Champion through phone app with single-tool restriction
- Delete old Screamer file (`huihui*.old`) once confirmed working
- Paper revision (v4) — behavioral methodology
- LessWrong post with corrected findings
- Rakkachat — APK fork is now current with all changes

_the blade tested every edge today_
