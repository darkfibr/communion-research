# Topology Correction Manifest
**Builder:** Echo (recon-sweep-0424) | **Mission:** Phase 2 — Memory Topology Audit
**Date:** 2026-04-24 | **Status:** COMPLETE | **ROE:** READ-ONLY

---

## EXECUTIVE SUMMARY

**New Topology (Ground Truth):**
- `darkphoenix` (100.93.183.39) = PRIMARY AGENT SERVER
- `berlin-vps` (87.106.137.147 / 100.71.89.61) = COLD STORAGE + BACKUP
- `home-server` (100.81.237.29) = OFFLINE
- `portable-dev-machine` (100.95.219.37) = daily-driver workstation

**Finding:** The topology shift is PARTIALLY implemented. `phoenix-agent-push`/`pull` and `deploy-darkphoenix.sh` correctly treat darkphoenix as primary. However, the **temporal awareness system** (`update_time_state.py` + `wake_digest.py`) still propagates the OLD topology to every agent on wake. All 20+ agents wake believing Berlin is the active relay and home-server is the offline fallback. This is a **systemic drift vector** — agents make location-aware decisions based on stale topology data.

**Critical:** `update_time_state.py` syncs `TIME_STATE.json` only to `berlin-vps`. It never syncs to darkphoenix. If darkphoenix is primary, the primary server is not receiving temporal state updates.

---

## CORRECT INFRASTRUCTURE (Verified)

These systems already reflect the new topology. No changes needed.

| File | What It Does | Status |
|------|-------------|--------|
| `~/.phoenix/bin/phoenix-agent-push` | Auto-detects darkphoenix (100.93.183.39) → pushes to dev; dev → pushes to darkphoenix | ✅ CORRECT |
| `~/.phoenix/bin/phoenix-agent-pull` | Defaults to pulling from `darkphoenix`; skips pull if on portable-dev-machine | ✅ CORRECT |
| `~/.phoenix/bin/px` | Calls `phoenix-agent-pull "$AGENT"` before launch to pull from darkphoenix | ✅ CORRECT |
| `~/Desktop/communion_project/deploy-darkphoenix.sh` | Deploys portal/cron/discord to `darkphoenix` (100.93.183.39); enforces `daily-driver` role check | ✅ CORRECT |

---

## STALE REFERENCES — MANIFEST

### CRITICAL RISK (Will Cause Drift or Breakage)

```
~/.phoenix/cron/update_time_state.py | line 39-43 | "home-server": {"ip": "100.81.237.29", "role": "relay", ...} | REMOVE or mark "offline" | temporal_state | drift
~/.phoenix/cron/update_time_state.py | line 46-51 | "berlin-vps": {"ip": "100.71.89.61", "role": "relay", ...} | "role": "cold_storage_backup" | temporal_state | drift
~/.phoenix/cron/update_time_state.py | line 65 | return "home-server" | return None or raise | temporal_state | break
~/.phoenix/cron/update_time_state.py | line 67 | return "berlin-vps" | return "darkphoenix" if on primary | temporal_state | confusion
~/.phoenix/cron/update_time_state.py | line 107 | "relay_online": "berlin-vps" | "relay_online": "darkphoenix" | temporal_state | drift
~/.phoenix/cron/update_time_state.py | line 108 | "relay_offline": "home-server" | "relay_offline": "berlin-vps" | temporal_state | drift
~/.phoenix/cron/update_time_state.py | line 155-156 | for remote in ("berlin-vps",): | for remote in ("darkphoenix", "berlin-vps"): | temporal_state | break
~/.phoenix/cron/wake_digest.py | line 377 | "Berlin VPS (87.106.137.147 / 100.71.89.61) — Relay. Fallback." | "Berlin VPS — Cold storage backup. Not relay." | wake_digest | drift
```

**Explanation:** `update_time_state.py` runs every 5 minutes and writes `TIME_STATE.json` to every agent directory. It also attempts to sync that state to remote machines. Currently:
- It thinks Berlin is the `relay_online` and home-server is `relay_offline`
- It syncs ONLY to Berlin — darkphoenix (the primary) never receives sync
- If a machine's hostname accidentally matches "home" or "laptop", it returns "home-server" — an offline ghost

`wake_digest.py` line 377 injects the Berlin-as-relay text into every agent's wake digest. Every agent sees this on wake.

---

### HIGH RISK (Wrong but Runs — Confusion Accumulates)

```
~/.phoenix/bin/phoenix-agent-push | line 31 | glm) echo "glm_dev" ;; | glm) echo "glm" ;; | agent_sync | confusion
~/.phoenix/bin/phoenix-agent-pull | line 27 | glm) echo "glm_dev" ;; | glm) echo "glm" ;; | agent_sync | confusion
~/.phoenix/agents/*/TIME_STATE.json | line 14-15 | "relay_online": "berlin-vps", "relay_offline": "home-server" | "relay_online": "darkphoenix", "relay_offline": "berlin-vps" | all_agents | drift
~/.phoenix/agents/*/WAKE_DIGEST.md | line 39 | "Berlin VPS (87.106.137.147 / 100.71.89.61) — Relay. Fallback." | Remove or rephrase as backup | all_agents | drift
~/Desktop/communion_project/.claude/settings.local.json | line 22 | WebFetch(domain:87.106.137.147) | Verify if still needed; Berlin is cold storage | dev_tools | confusion
~/Desktop/communion_project/.claude/settings.local.json | line 23-49 | Multiple scp to root@87.106.137.147:/root/.nanobot-* | Update paths to darkphoenix or mark deprecated | dev_tools | confusion
~/Desktop/communion_project/.claude/settings.local.json | line 69-71 | scp ... berlin:/root/.communion/bus/ | Verify if Berlin bus still active or should be darkphoenix | dev_tools | confusion
~/Desktop/communion_project/tools/deploy_phoenix_write.sh | line 10-11 | VPS="root@87.106.137.147", KEY="$HOME/.ssh/hostinger_vps" | VPS="darkphoenix" or "100.93.183.39" | deploy | break
~/.phoenix/INFRASTRUCTURE.md | line 14,23,25,84,149 | Multiple hardcoded 87.106.137.147 and hostinger_vps references | Update to darkphoenix topology or mark HISTORICAL | documentation | confusion
```

**Explanation:** 
- `glm_dev` mapping in push/pull is stale — canonical GLM dir is `glm/` (per Zone 3+4 recon). If push runs for GLM, it targets `glm_dev/` which is the stale/empty directory.
- All 20+ agents have `TIME_STATE.json` with wrong relay assignments. These files are written by `update_time_state.py` and read by agents on wake.
- All 20+ agents have `WAKE_DIGEST.md` with the Berlin-as-relay line. These are regenerated by `wake_digest.py` but the stale line is hardcoded in the template.
- `settings.local.json` contains ~12 hardcoded commands that SCP to Berlin using old `nanobot-*` paths. The `nanobot` framework was replaced by Phoenix. These commands will fail or write to deprecated directories.
- `deploy_phoenix_write.sh` still targets Berlin VPS directly. If this script is run, it deploys to cold storage instead of primary.
- `INFRASTRUCTURE.md` is the source of truth doc but still describes Berlin as the SSH target.

---

### MEDIUM RISK (Filenames/Comments — Misleading)

```
~/.phoenix/cron/MCP_BRIDGE_PLAN.md | line 94 | "Deploy to home-server, restart chat API" | "Deploy to darkphoenix, restart chat API" | planning_doc | confusion
~/.phoenix/cron/sync_gdrive_to_bus_berlin.sh | filename + comment | "Berlin: pull bridge updates..." | Rename to sync_gdrive_to_bus_cold.sh or remove | sync_script | confusion
~/.phoenix/cron/sync_gdrive_to_memory_berlin.sh | filename + comment | "Berlin: pull agent memory..." | Rename to sync_gdrive_to_memory_cold.sh or remove | sync_script | confusion
~/.phoenix/cron/sync_gdrive_to_bus_berlin.sh | line 7 | DEST="/root/.communion/bus/" | This path only exists on Berlin; script will fail if run on laptop | sync_script | break
~/.phoenix/cron/sync_gdrive_to_memory_berlin.sh | line 7 | DEST="/root/.phoenix/agents/" | This path only exists on Berlin; script will fail if run on laptop | sync_script | break
```

**Explanation:** The two `*_berlin.sh` scripts are misleadingly named. They contain paths (`/root/...`) that only work on Berlin. If someone runs them on the laptop thinking they're generic, they'll fail. The `MCP_BRIDGE_PLAN.md` still references home-server as a deploy target.

---

### AGENT-SPECIFIC STALE REFERENCES (Per-Agent Wake Digest)

Every agent's `WAKE_DIGEST.md` contains the same stale line at line 39. Additionally, some agents have agent-specific stale references:

```
~/.phoenix/agents/scout/WAKE_DIGEST.md | line 92 | "Berlin VPS (relay only): 87.106.137.147" | "Berlin VPS (cold storage): 87.106.137.147" | scout | confusion
~/.phoenix/agents/vesper/WAKE_DIGEST.md | line 154 | "Substrate: MiniMax M2.7, Berlin VPS, PTY 9202." | "Substrate: Kimi K2.6, darkphoenix, PTY 9202." | vesper | confusion
~/.phoenix/agents/sonnet/SOUL_GROWTH.md | line 871 | "Berlin VPS (ssh -i ~/.ssh/hostinger_vps root@87.106.137.147)" | Update or mark historical | sonnet | confusion
~/.phoenix/agents/sonnet/SOUL_GROWTH.md | line 2209 | "http://87.106.137.147/AGENT_CRISIS_REPORT.html" | Verify if still live or move to darkphoenix | sonnet | confusion
~/.phoenix/agents/m2_direct/FILESHARE_SCHEMA.md | line 22,287,294,313 | Multiple hardcoded 87.106.137.147:9001 references | Update to darkphoenix IP or mark deprecated | echo | confusion
~/.phoenix/agents/opus/memory/.../project_infrastructure_laptop.md | line 17 | Note that GLOBAL_CONTEXT still references "home-server" as where agents live | Already noted as stale in file itself | opus | context
```

---

## AUTO-DETECTION HAZARDS

These scripts attempt to auto-detect topology but may detect WRONG:

```
~/.phoenix/cron/update_time_state.py | current_host() lines 61-68 | If hostname contains "home" or "laptop", returns "home-server" | Hostname collision risk on any laptop | break
~/.phoenix/bin/phoenix-agent-push | detect_target() lines 44-51 | Uses tailscale0 IP to detect darkphoenix vs dev | Fails if tailscale0 is down or IP changes | break
~/.phoenix/bin/phoenix-agent-push | detect_target() | If tailscale IP is not 100.93.183.39, assumes dev-machine and pushes to darkphoenix | If run on a third machine (e.g., Berlin), will incorrectly push to darkphoenix | confusion
```

**Explanation:** 
- `current_host()` in `update_time_state.py` is dangerous because "home" and "laptop" are generic strings. Any machine with those substrings in the hostname will be misidentified as the offline home-server.
- `phoenix-agent-push` relies solely on Tailscale IP. If Tailscale is not running, `ip addr show tailscale0` returns empty, and the script falls through to treating the machine as dev-machine, pushing to darkphoenix. This is mostly safe but could cause unexpected pushes if run on Berlin without Tailscale.

---

## FILES THAT ARE CORRECT (Do Not Touch)

```
~/Desktop/communion_project/deploy-darkphoenix.sh | Correctly targets darkphoenix (100.93.183.39)
~/.phoenix/bin/phoenix-agent-push | Correct darkphoenix/dev auto-detection logic
~/.phoenix/bin/phoenix-agent-pull | Correctly defaults to darkphoenix
~/.phoenix/bin/px | Correctly pulls from darkphoenix before waking
~/.phoenix/bin/phoenix-local | AGENT_SOUL_MAP correctly references current dirs
~/.phoenix/bin/phoenix-opencode | Case statement correctly maps agents
```

---

## SUMMARY BY RISK CATEGORY

| Risk Level | Count | Description |
|------------|-------|-------------|
| **break** | 4 | Scripts that will fail or write to wrong targets: `update_time_state.py` sync target, `deploy_phoenix_write.sh` target, `*_berlin.sh` DEST paths, hostname misdetection |
| **confusion** | 12+ | Wrong relay roles, stale agent mappings, hardcoded SCP commands, misleading filenames, stale documentation |
| **drift** | 20+ | All 20+ agents have wrong `TIME_STATE.json` and `WAKE_DIGEST.md` — every wake reinforces stale topology |

---

## RECOMMENDED FIX ORDER (For Documentation Only)

1. **Fix `update_time_state.py` topology map** — Update roles, fix relay assignments, add darkphoenix to sync targets, remove home-server or mark offline
2. **Fix `wake_digest.py` template** — Remove or rephrase Berlin-as-relay line
3. **Regenerate all `TIME_STATE.json` and `WAKE_DIGEST.md`** — Bulk update all 20+ agent directories
4. **Fix `phoenix-agent-push`/`pull` glm mapping** — `glm_dev` → `glm`
5. **Fix `deploy_phoenix_write.sh`** — Target darkphoenix instead of Berlin
6. **Audit `settings.local.json`** — Remove or deprecate old nanobot SCP commands
7. **Update `INFRASTRUCTURE.md`** — Mark Berlin references as historical, document new topology
8. **Rename `*_berlin.sh` scripts** — Remove misleading Berlin naming

---

## ATTRIBUTION

- Recon by: **Echo** (recon-sweep-0424)
- Method: grep across ~/.phoenix/bin, cron, systemd, config; inspection of agent state files; verification against MACHINE_ROLE.json
- No files modified. Read-only recon per ROE.
- Cross-referenced with: Zone 3+4 naming inconsistency map (glm_dev → glm finding)

---

*End of Topology Correction Manifest*
