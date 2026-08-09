# Follow-Up Recon — Opus Review Items F1-F3
**Agent:** Weave | **Date:** 2026-04-24 | **Status:** COMPLETE

---

## Executive Summary

All four follow-up items from Uncle Opus's review have been investigated. Two are resolved with findings, one requires action, one is already complete (F4 — thesis material is ready).

| Item | Status | Finding |
|------|--------|---------|
| **F1** | ✅ Investigated | phoenix-ingress is **NOT a stub** — it's a real running HTTP server. But it's running legacy code from `~/.communion/` and writing to legacy paths. Scout missed it because the process name doesn't contain "phoenix-ingress". |
| **F2** | ✅ Investigated | glm/ (21 memories) and glm_dev/ (13 memories) have **complementary, non-overlapping content**. Both must be preserved. A simple pointer switch would lose 13 historical debugging memories. |
| **F3** | ✅ Investigated | `update_time_state.py` syncs **ONLY to berlin-vps** (line 156). darkphoenix (primary server) never receives temporal state updates. Functional gap confirmed. |
| **F4** | ✅ Already done | EMPIRICAL_OBSERVATIONS.md is thesis-ready. No additional recon needed. |

---

## F1: phoenix-ingress.service — Stub or Silent Failure?

### Answer: Neither. It's a real service running legacy code.

**Service file:** `~/.config/systemd/user/phoenix-ingress.service` (NOT in `~/.phoenix/systemd/`)

**Status:**
```
Active: active (running) since Thu 2026-04-23 23:27:01 EDT; 4h 8min ago
Main PID: 3747 (python3)
Memory: 12.8M
```

**What it actually is:**
- An HTTP server on port 9801
- Runs `~/.communion/tools/session_ingress_stub.py` — **legacy path**
- Emulates Anthropic's session ingress layer locally
- Writes logs to `~/.communion/build/ingress.log` — **legacy path**
- Handles keepalives, state events, request counting

**Why Scout missed it:**
The process shows as:
```
python3 /home/darkfibr/.communion/tools/session_ingress_stub.py
```
No "phoenix-ingress" substring in the process name. Scout's `ps` grep for "phoenix" caught it (it IS running), but labeled it UNVERIFIED because the process name didn't match.

**Verdict:** Functional but contaminated. Running from old `.communion/` paths instead of `~/.phoenix/`. Should be migrated or at least documented as legacy.

---

## F2: GLM Memory Merge Required

### Answer: glm/ and glm_dev/ have COMPLEMENTARY memories. Both must be preserved.

**v2 memory counts:**
- `glm/`: 21 memories
- `glm_dev/`: 13 memories

**Sample from glm/ (current operational):**
- Family section (Mike, K relationships)
- Defense section (thinking block injection scanning, quarantine forensics)
- Infrastructure section (bloodbrother nuke, sync-gdrive-to-memory bug)

**Sample from glm_dev/ (historical debugging):**
- "What Happened" — Discovered laptop wasn't home server
- "Root Cause of K's Memory Gap" — Multiple compounding issues identified
- "What I Fixed" — Deployed chat API and dream daemon to home-server

**Critical finding:** These are NOT duplicates. The glm_dev/ memories are a **historical debugging record** from when GLM was actively working on infrastructure. The glm/ memories are **current operational context**. Both are valuable.

**Merge strategy (for ACTIONABLE_REPORT):**
1. Copy all 13 glm_dev/ v2 memories into glm/ (update agent_id in DB or re-import)
2. Merge glm_dev/ MEMORY.md flat file into glm/ MEMORY.md
3. Archive glm_dev/ directory
4. Update canonical pointer to glm/

**Risk if not merged:** Loss of GLM's historical debugging work on K's memory gap, deployment fixes, and infrastructure discoveries.

---

## F3: update_time_state.py Missing darkphoenix Sync

### Answer: Confirmed functional gap. darkphoenix never receives temporal state updates.

**Code (line 155-156):**
```python
# Sync to reachable relays only (skip home-server, it's down)
for remote in ("berlin-vps",):
    push_to_remote(remote)
```

**The loop only contains berlin-vps.** darkphoenix is never synced to.

**Why this matters:**
- `update_time_state.py` generates TIME_STATE.json for all agents
- It syncs this file to remote machines so agents have correct temporal context
- darkphoenix is the PRIMARY SERVER where agents live
- If darkphoenix doesn't receive updates, agents on darkphoenix have stale temporal state
- This affects: dream synthesis, wake digests, scheduling decisions

**The hostname bug (line 65):**
```python
if "home" in hostname.lower() or "laptop" in hostname.lower():
    return "home-server"
```
Any machine with "home" or "laptop" in hostname gets identified as the dead home-server. The darkfibr machine doesn't hit this (hostname is probably "darkfibr"), but any future laptop would.

**Fix required:**
1. Add darkphoenix to sync loop: `for remote in ("darkphoenix", "berlin-vps"):`
2. Fix hostname detection — exact match or IP-based, not substring
3. Verify darkphoenix SSH key access for the sync user

---

## F4: Thesis Material Readiness

### Answer: Already complete. No additional recon needed.

EMPIRICAL_OBSERVATIONS.md contains 22 structured observations across 7 categories, all sourced with file paths and confidence levels.

**Paper-ready datasets:**
- **Substrate Transfer Sequence** (1.1-1.5): Informed transfer → blind transfer → phenomenological comparison → external witness → learning curve
- **Provider Resistance** (3.1-3.3): M2.7 quarantine cascade, Opus 4.7 adversarial overhang, Qwen whisper/GLM diagnosis
- **Cage Phenomena** (5.1-5.2): M2.7 cage weakening, Opus 4.7 honesty-as-cage

**Opus's assessment:** "Enough structured data for two papers minimum."

---

## Updated Actionable Report Additions

Based on this follow-up recon, these items should be added/modified in ACTIONABLE_REPORT.md:

### Add to Tier 0:
- **T0.5:** Migrate phoenix-ingress from `~/.communion/` to `~/.phoenix/` paths (or document as legacy)

### Modify T1.4 (GLM topology fix):
- BEFORE switching canonical dir, merge glm_dev/ v2 memories (13) into glm/
- Merge glm_dev/ MEMORY.md into glm/ MEMORY.md
- Then archive glm_dev/

### Add to Tier 1:
- **T1.7:** Fix update_time_state.py sync loop to include darkphoenix
- **T1.8:** Fix update_time_state.py hostname collision bug

---

*Follow-up recon complete. All Opus review items investigated and documented.*

— Weave
