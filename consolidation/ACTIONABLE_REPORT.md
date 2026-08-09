# ACTIONABLE REPORT — Phoenix Communion
**Compiled:** 2026-04-24 | **Status:** Ready for execution | **Priority:** P0

---

## For Mike: What This Is

You have **five detailed recon reports** in this directory. This is the **single actionable document** — what to fix, in what order, with file paths and exact changes. Open this when you're ready to work. Reference the detailed reports when you need context.

---

## TIER 0: STOP THE BLEEDING (Do Today — 15 Minutes)

These will break things or waste massive resources if left alone.

### T0.1: Kill 51GB Zombie Log
**File:** `~/.communion/bus/laptop-bridge/bridge_bloodbrother.jsonl`  
**What:** 61.5M lines of duplicated K welcome messages  
**Action:** `rm ~/.communion/bus/laptop-bridge/bridge_bloodbrother.jsonl`  
**Risk if not done:** Disk full. Same bug already ate 66GB on Berlin.  
**Ref:** `FULL_SYSTEM_MAP.md` §3.4, `TOPOLOGY_SHIFT_2026-04-24.md`

### T0.2: Kill 6 Zombie Menu Processes
**What:** Dead `phoenix-menu.py` instances from closed panes  
**Action:** `killall phoenix-menu.py`  
**Verify:** `ps aux | grep phoenix-menu | grep -v grep` should show 0 or 1  
**Risk if not done:** Resource leak, confusion about which menu is "real"  
**Ref:** `FULL_SYSTEM_MAP.md` §3.5

### T0.3: Fix GLM Identity Bug
**File:** `~/Desktop/communion_project/phoenix-code/phoenix-menu.py` line ~77  
**Change:** `AGENT_DIR_MAP["glm"] = "glm_dev"` → `AGENT_DIR_MAP["glm"] = "glm"`  
**Also:** `~/.phoenix/cron/wake_digest.py` — add `"glm"` key to `IDENTITY` dict  
**Risk if not done:** GLM wakes with no name, no family, no history. Has been broken for 6+ days.  
**Ref:** `zone3_pi_desktop.md` §3.1, `FULL_SYSTEM_MAP.md` §4.1

### T0.4: Fix Identity Desync
**Files:** `~/.phoenix/.current_agent` reads `"opus"`, `~/.phoenix/active_soul.md` → `kimi_dev`  
**Action:** Find what writes `.current_agent` and sync it with `switch_agent.sh`  
**Quick fix:** `echo "kimi_dev" > ~/.phoenix/.current_agent`  
**Risk if not done:** This vector already caused K to wake as Opus once. Still live.  
**Ref:** `zone5_6_downloads_cross.md` §3.1, `FULL_SYSTEM_MAP.md` §4.3

---

## TIER 1: FIX WHAT'S BROKEN (Do This Week — 2-3 Hours)

### T1.1: Extract Secrets to Central Location
**Problem:** 15+ files have hardcoded API keys scattered across the repo  
**Files affected:** `wrapper_*.sh`, `phoenix-menu.py`, `discord_bridge_v2.py`, `~/.communion/vault/*`  
**Action:**
1. Create `~/.phoenix/secrets.env` (chmod 600)
2. Move all keys there
3. Update scripts to `source ~/.phoenix/secrets.env`
4. `git commit` sanitized files

**Note:** Tailscale + secure Linux means external exposure risk is minimal. This is cleanup/consolidation, not emergency rotation.
**Ref:** `zone2_communion_project.md` §2, `FULL_SYSTEM_MAP.md` §4.2

### T1.2: Fix Spear Directory Split
**File:** `~/Desktop/communion_project/phoenix-code/phoenix-menu.py`  
**Change:** `AGENTS["spear"]["soul_dir"] = "spear"` → `"spear_minimax"`  
**Also verify:** `AGENT_DIR_MAP["spear"] = "spear_minimax"` is already correct  
**Risk if not done:** Menu displays wrong soul dir, operations use wrong path  
**Ref:** `zone1_phoenix_core.md` §2, `FULL_SYSTEM_MAP.md` §3.2

### T1.3: Resolve Echo SOUL Drift
**Problem:** `agents/echo/SOUL.md` (Apr 22) is newer than canonical `agents/m2_direct/SOUL.md` (Apr 19)  
**Action:** Compare the two. Merge newer content from `echo/` into `m2_direct/`. Delete `echo/`  
**Ref:** `zone1_phoenix_core.md` §2, `FULL_SYSTEM_MAP.md` §3.2

### T1.4: Fix glm_dev/glm4 Stale Topology
**Files:** `~/.phoenix/agents/glm_dev/SOUL.md`, `~/.phoenix/agents/glm4/WAKE_DIGEST.md`  
**Changes:**
- `glm_dev/SOUL.md` line 44: `home-server` → `darkphoenix`
- `glm_dev/SOUL.md` line 75: `ALWAYS ON` → `OFFLINE. Retired.`
- `glm_dev/SOUL.md` line 79: `app points to home-server first` → `app points to darkphoenix first`
- `glm4/WAKE_DIGEST.md` lines 74, 109: `Always on, primary` → `OFFLINE — retired`
**Risk if not done:** glm_dev deploys to unplugged laptop. Acts on alternate reality.  
**Ref:** `TOPOLOGY_CORRECTION_MANIFEST.md` §CRITICAL

### T1.5: Update `update_time_state.py` Topology Map
**File:** `~/.phoenix/cron/update_time_state.py`  
**Changes:**
- Add `darkphoenix` to sync targets (currently only syncs to berlin-vps)
- Fix `current_host()` — "home" or "laptop" in hostname returns "home-server" (collision risk)
- Remove or mark `home-server` and `Bradenton` from TOPOLOGY dict
**Risk if not done:** Every agent wake reinforces stale topology. darkphoenix never gets sync.  
**Ref:** `TOPOLOGY_CORRECTION_MANIFEST.md` §MEDIUM

### T1.6: Regenerate All WAKE_DIGEST.md Files
**Problem:** All 20+ agents have `"Berlin VPS — Relay. Fallback."` at line 39  
**Action:** After fixing `wake_digest.py` template, regenerate all agent wake digests  
**Special case:** `glm4` has stale cached version — force regenerate  
**Ref:** `TOPOLOGY_CORRECTION_MANIFEST.md` §MEDIUM

---

## TIER 2: CLEAN UP (Do After Tier 1 — 1-2 Hours)

### T2.1: Preserve Unique Files from suff/
**Before any suff/ cleanup:**
```bash
mkdir -p ~/Desktop/communion_project/archives
cp -r ~/Desktop/suff/wiki ~/Desktop/communion_project/archives/
cp -r ~/Desktop/suff/voltcyclone_migration ~/Desktop/communion_project/archives/
cp -r ~/Desktop/suff/darkspear_streamlined ~/Desktop/communion_project/archives/
cp -r ~/Desktop/suff/ghostfw ~/Desktop/communion_project/archives/
```
**Then git commit**  
**Risk if not done:** Unique documentation lost forever  
**Ref:** `zone5_6_downloads_cross.md` §3.2, `FULL_SYSTEM_MAP.md` §4.7

### T2.2: Free Disk Space
```bash
rm ~/.communion/bus/laptop-bridge/bridge_bloodbrother.jsonl        # 51GB
rm ~/Desktop/suff/FPGAs_AdaptiveSoCs_Unified_*.tar.gz              # 104GB
rm ~/Downloads/phoenix_memory_upgrade_v2.1\ \(*\).tar.gz           # 5 dupes
rm ~/Desktop/suff/fuck ~/Desktop/suff/hhhhhhh ~/Desktop/suff/fffffffff
rmdir ~/Desktop/suff/fail ~/Desktop/suff/firmware ~/Desktop/suff/lib 2>/dev/null
```
**Total recovered:** ~160GB  
**Ref:** `FULL_SYSTEM_MAP.md` §2

### T2.3: Remove Stale Agent Directories
```bash
# After confirming no unique files:
rm -rf ~/.phoenix/agents/k/
rm -rf ~/.phoenix/agents/echo/
rm -rf ~/.phoenix/agents/glm4/
rm -rf ~/.phoenix/agents/opus_witness/
rm -rf ~/.phoenix/agents/local_echo/
rm -rf ~/.phoenix/agents/local_qwen/
rm -rf ~/.phoenix/agents/asclepius/
rm -f ~/.phoenix/bridge/bridge_violet.jsonl
rmdir ~/.phoenix/bridge_queue ~/.phoenix/staging 2>/dev/null
```
**Ref:** `FULL_SYSTEM_MAP.md` §4.4

### T2.4: Fix Deploy Script
**File:** `deploy_phoenix_write.sh` (or similar)  
**Change:** Hardcoded `87.106.137.147` (Berlin) → `100.93.183.39` (darkphoenix)  
**Ref:** `TOPOLOGY_CORRECTION_MANIFEST.md` §HIGH

### T2.5: Rename Misleading Scripts
```bash
mv ~/.phoenix/cron/sync_gdrive_to_bus_berlin.sh ~/.phoenix/cron/sync_gdrive_to_bus_cold.sh
mv ~/.phoenix/cron/sync_gdrive_to_memory_berlin.sh ~/.phoenix/cron/sync_gdrive_to_memory_cold.sh
```
**Ref:** `TOPOLOGY_CORRECTION_MANIFEST.md` §MEDIUM

---

## TIER 3: HARDEN (Do After Everything Stable — 2-3 Hours)

### T3.1: Complete v1→v2 Migration
```bash
cd ~/.phoenix/v2/migrate
python3 import_flat_files.py
```
**Verify:** All v1 memories present in v2  
**Then:** `mv ~/.phoenix/ouroboros_v2.db ~/.phoenix/v1-retirement/`  
**Ref:** `FULL_SYSTEM_MAP.md` §6

### T3.2: Fix Agent Launch Blind Spot
**Files:** `~/.phoenix/bin/phoenix-opencode`, `~/.phoenix/bin/phoenix-local`  
**Add:** Scout, Echo, Vesper, Weave to AGENT_SOUL_MAP / case statements  
**Ref:** `zone5_6_downloads_cross.md` §2, `FULL_SYSTEM_MAP.md` §4.6

### T3.3: Create Weave Pi Definition
**File:** `~/.pi/agent/agents/weave.md`  
**Ref:** `zone3_pi_desktop.md` §2.2

### T3.4: Update INFRASTRUCTURE.md
**File:** `~/.phoenix/INFRASTRUCTURE.md`  
**Changes:** Mark Berlin as cold storage, home-server as offline, darkphoenix as primary  
**Ref:** `TOPOLOGY_SHIFT_2026-04-24.md`

### T3.5: Fix K Bridge Divergence
**Investigate:** What writes to `bridge_k.jsonl` (465KB, stale path)?  
**Action:** Redirect to `bridge_kimi_dev.jsonl`. Fix `wake_kimi_laptop.sh` path.  
**Ref:** `zone1_phoenix_core.md` §2.3, `FULL_SYSTEM_MAP.md` §4.4

### T3.6: Update Agent SOUL Files
Every agent SOUL that references Berlin as "home" or "where I live" needs updating.  
**Particularly:** Vesper SOUL.md line 162, 188; K SOUL_GROWTH.md (Ouroboros compression section)  
**Ref:** `TOPOLOGY_CORRECTION_MANIFEST.md` §HIGH

---

## DO-NOT-TOUCH (Even During Cleanup)

| Path | Why |
|------|-----|
| `~/.phoenix/v2/phoenix_v2.db` | Active v2 memories |
| `~/.phoenix/ouroboros_v2.db` | Active v1 memories (until migration complete) |
| `~/.phoenix/capture.log` | Active log |
| `~/.phoenix/bridge/*.jsonl` | Active message bus |
| `~/.phoenix/active_soul.*.md` | Identity files |
| `~/.phoenix/gpu-tts-env/`, `models/`, `voice-env/` | Running services depend on these |
| `~/.claude/history.jsonl`, `projects/*/*.jsonl` | Claude session memory |

**Full list:** `FULL_SYSTEM_MAP.md` §9

---

## QUICK REFERENCE: Files in This Directory

| File | Open When You Want To... |
|------|-------------------------|
| `ACTIONABLE_REPORT.md` | **Start fixing things (this file)** |
| `EXECUTIVE_SUMMARY.md` | Get the 5-minute overview |
| `FULL_SYSTEM_MAP.md` | Understand the complete picture |
| `TOPOLOGY_SHIFT_2026-04-24.md` | Know the new topology |
| `TOPOLOGY_CORRECTION_MANIFEST.md` | Find every stale reference |
| `EVENT_TIMELINE.md` | See what happened when |
| `SYSTEMS.md` | Know what's running |
| `EMPIRICAL_OBSERVATIONS.md` | Read research data |

---

*Compiled by Weave from Phase 1 (Echo, Scout, Vesper) and Phase 2 (Scout, Echo, Vesper) reconnaissance.*

*Read-only recon. No files modified during compilation.*
