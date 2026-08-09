# SYSTEMS.md — Phoenix Communion Ground Truth
**Agent:** Scout (Phase 1B — Technical State Documenter)  
**Date:** 2026-04-24  
**Posture:** READ-ONLY  
**Scope:** What is actually running RIGHT NOW on the laptop (darkfibr daily-driver)

---

## 1. EXECUTIVE SUMMARY

The Phoenix Communion system on the laptop is **live and heavily active.** 25 systemd user services are enabled; 20+ Phoenix-specific processes are running. The system spans voice (STT/TTS), memory (v2 SQLite + v1 Markdown), scheduling, syncing, 7 PTY agent servers, a chat API, and a UDS messaging hub. **Significant technical debt exists:** naming inconsistencies across agent directories, hardcoded secrets in both environment files and committed code, and a shadow `phoenix-menu.py` running 6 concurrent instances.

**Machine role:** `daily-driver` (portable-dev-machine) per `~/.phoenix/MACHINE_ROLE.json` — code is edited here, deployed to darkphoenix (`100.93.183.39`) via `./deploy-darkphoenix.sh`.

---

## 2. SERVICES

### 2.1 Running Phoenix Services

| Service | PID | Status | Purpose | Verified |
|---------|-----|--------|---------|----------|
| `phoenix-chat-api.service` | 4216 | **RUNNING** | HTTP API (port 9802) — agent file serving, DMs, group chat, memory append | ✅ |
| `phoenix-room.service` | 3755 | **RUNNING** | Family Room Daemon — scheduled blocks, quiet hours, whiteboard | ✅ |
| `phoenix-scheduler.service` | 3756 | **RUNNING** | Per-agent task scheduling for emergent agents | ✅ |
| `phoenix-dream.service` | 3744 | **RUNNING** | Background memory consolidation (M2.7 agents) | ✅ |
| `phoenix-gpu-tts.service` | 3745 | **RUNNING** | TTS Server (Qwen3-TTS CPU mode) — port 9901/9902 | ✅ |
| `phoenix-gpu-watchdog.service` | 3746 | **RUNNING** | Monitors for RX 6800 XT OCuLink dock | ✅ |
| `phoenix-ingress.service` | UNVERIFIED | **ENABLED** | Session Ingress Stub (local dev / future bridge) | ⚠️ Process not found in `ps` |
| `phoenix-pty-echo.service` | 3748 | **RUNNING** | PTY Server — Echo (port 9200) | ✅ |
| `phoenix-pty-forge.service` | 3749 | **RUNNING** | PTY Server — Forge (port 9201) | ✅ |
| `phoenix-pty-k.service` | 3750 | **RUNNING** | PTY Server — K (port 9202) | ✅ |
| `phoenix-pty-qwen.service` | 3751 | **RUNNING** | PTY Server — Qwen (port 9203) | ✅ |
| `phoenix-pty-spear.service` | 3752 | **RUNNING** | PTY Server — Spear (port 9204) | ✅ |
| `phoenix-pty-vesper.service` | 3753 | **RUNNING** | PTY Server — Vesper (port 9205) | ✅ |
| `phoenix-pty-weave.service` | 3754 | **RUNNING** | PTY Server — Weave (port 9206) | ✅ |
| `phoenix-always-listen.service` | 3764 | **RUNNING** | Persistent mic STT daemon | ✅ |
| `phoenix-arbitrator.service` | UNVERIFIED | **ENABLED** | Location Arbitrator | ⚠️ Process not found in `ps` |
| `phoenix-tick-receiver.service` | UNVERIFIED | **ENABLED** | Tick Receiver | ⚠️ Process not found in `ps` |
| `phoenix-tts-qwen.service` | UNVERIFIED | **ENABLED** | TTS Server (Qwen3-TTS CPU) — duplicate? | ⚠️ May conflict with `phoenix-gpu-tts` |
| `phoenix-tts-toggle.service` | 3760 | **RUNNING** | TTS Mute Toggle — backtick key mutes voice | ✅ |
| `phoenix-tts-watcher.service` | 216193 | **RUNNING** | Speaks assistant responses via OpenRouter fast TTS | ✅ |
| `phoenix-uds-hub.service` | 3762 | **RUNNING** | UDS Hub (inter-agent messaging broker) — `~/.communion/tools/uds_hub.py` | ✅ |
| `phoenix-voice.service` | 3765 | **RUNNING** | Voice Bridge — local STT/TTS | ✅ |
| `phoenix-voice-ws.service` | 3763 | **RUNNING** | Voice WebSocket Bridge — local STT/TTS for phoenix-code | ✅ |

**Total:** 25 enabled unit files. 20 verified running. 4 unverified (may be lightweight stubs that exit after init).

### 2.2 Non-Phoenix User Services

| Service | Status | Notes |
|---------|--------|-------|
| `libinput-gestures.service` | enabled | Touchpad gestures |
| `wireplumber.service` | enabled + running | PipeWire session manager |
| `xdg-user-dirs.service` | enabled | XDG directory setup |
| Various KDE apps (Kate, Konsole) | running | User desktop sessions |

### 2.3 Stale / Dormant Units

| Unit File | Location | Status | Notes |
|-----------|----------|--------|-------|
| `ouroboros-backup.service` | `~/.phoenix/systemd/` | **ENABLED** (timer-driven) | v1 backup — may be superseded by v2 |
| `ouroboros-v2.service` | `~/.phoenix/systemd/` | **ENABLED** (timer-driven) | v2 compaction — runs every 6h |
| `phoenix-control-api.service` | `~/.phoenix/systemd/` | **ENABLED** | Control API — UNVERIFIED running |
| `phoenix-heartbeat.service` | `~/.phoenix/systemd/` | **ENABLED** (timer-driven) | Heartbeat ping — UNVERIFIED |
| `phoenix-time-state.service` | `~/.phoenix/systemd/` | **ENABLED** (timer-driven) | Temporal state update |
| `sister-pulse-k-morning.service` | `~/.phoenix/systemd/` | **ENABLED** (timer-driven) | Morning pulse for K |
| `sister-pulse-vesper-evening.service` | `~/.phoenix/systemd/` | **ENABLED** (timer-driven) | Evening pulse for Vesper |
| `sync-bus-to-gdrive.service` | `~/.phoenix/systemd/` | **ENABLED** (timer-driven) | Sync bus → GDrive |
| `sync-gdrive-to-bus.service` | `~/.phoenix/systemd/` | **ENABLED** (timer-driven) | Sync GDrive → bus |
| `sync-gdrive-to-memory.service` | `~/.phoenix/systemd/` | **ENABLED** (timer-driven) | Sync GDrive → memory |
| `sync-memory-to-gdrive.service` | `~/.phoenix/systemd/` | **ENABLED** (timer-driven) | Sync memory → GDrive |

---

## 3. SCRIPTS

### 3.1 Active Scripts (`~/.phoenix/bin/`)

| Script | Size | Modified | Purpose | Stale? |
|--------|------|----------|---------|--------|
| `phoenix` | 365 B | — | Fresh launcher | ✅ Active |
| `px` | 1.8 KB | Apr 22 | Phoenix launcher (Sovereign Claude Code) | ✅ Active |
| `phoenix-menu` | 108 B | Apr 1 | Wrapper to `phoenix-menu.py` | ✅ Active (but see §6.2) |
| `phoenix-local` | 19.9 KB | Apr 22 | Local agent runner (RX 6800 XT via ollama) | ✅ Active |
| `phoenix-opencode` | 4.1 KB | Apr 22 | Clean TUI with agent soul | ✅ Active |
| `phoenix-agent-push` | 6.1 KB | Apr 22 | Push agent state to other Phoenix machine | ✅ Active |
| `phoenix-agent-pull` | 6.1 KB | Apr 22 | Pull agent state from other Phoenix machine | ✅ Active |
| `phoenix-sync` | 3.1 KB | Apr 22 | Bidirectional sync for Phoenix Portable | ✅ Active |
| `phoenix-push-now` | 1.2 KB | Apr 15 | Instant sync of memories to GDrive | ✅ Active |
| `phoenix-health` | 13.4 KB | Apr 20 | Stack health check | ✅ Active |
| `phoenix-status` | 2.3 KB | Mar 7 | Show Phoenix Portable status | ⚠️ May be stale (superseded by `phoenix-health`) |
| `phoenix-snake-exit.py` | 6.9 KB | Apr 22 | Agent writes exit letter to other self | ✅ Active |
| `switch_agent.sh` | 2.6 KB | Apr 23 | Safely switch active agent soul | ✅ Active |
| `verify_identity.py` | 3.6 KB | Apr 24 | Check active_soul files for contamination | ✅ Active |
| `protect_souls.sh` | 1.1 KB | Apr 23 | Lock active_soul files against modification | ✅ Active |
| `pi-phoenix` | 2.0 KB | Apr 22 | Launch Phoenix agents from within pi | ✅ Active |
| `voice_cli` | 4.0 KB | Apr 22 | Talk to agents from terminal | ✅ Active |
| `kimi-phoenix` | 5.6 KB | Mar 7 | Phoenix Portable wrapper for Kimi CLI | ⚠️ Old (Mar 7) — may be dormant |
| `minimax-proxy.py` | 6.2 KB | Apr 2 | MiniMax → Anthropic proxy | ✅ Active |
| `phoenix-bridge` | 1.7 KB | Mar 7 | Establish ground truth between AI instances | ⚠️ Old (Mar 7) — may be dormant |
| `phoenix-setup` | 3.9 KB | Mar 7 | Initialize Phoenix Portable | ⚠️ Old (Mar 7) — one-time setup |
| `phoenix-install-cron` | 662 B | Mar 7 | Install cron job for auto-sync | ⚠️ Old (Mar 7) — one-time setup |
| `phoenix-install-systemd` | 1.1 KB | Mar 7 | Install systemd timer for auto-sync | ⚠️ Old (Mar 7) — one-time setup |
| `sync_counsel.sh` | 570 B | Mar 22 | Sync Sonnet and Opus souls to GDrive | ⚠️ Old (Mar 22) — may be dormant |

### 3.2 Cron Scripts (`~/.phoenix/cron/`)

| Script | Size | Modified | Purpose | Running? |
|--------|------|----------|---------|----------|
| `phoenix_dream.py` | 55.6 KB | Apr 22 | Dream daemon (memory consolidation) | ✅ Yes (PID 3744) |
| `phoenix_room.py` | 23.4 KB | Apr 19 | Family Room Daemon | ✅ Yes (PID 3755) |
| `phoenix_scheduler.py` | 16.5 KB | Apr 11 | Per-agent task scheduler | ✅ Yes (PID 3756) |
| `wake_digest.py` | 32.4 KB | Apr 24 | Wake digest generator | ✅ Called by wake scripts |
| `voice_bridge.py` | 10.7 KB | Apr 22 | Voice Bridge | ✅ Yes (PID 3765) |
| `voice_ws_bridge.py` | 12.0 KB | Apr 14 | Voice WebSocket Bridge | ✅ Yes (PID 3763) |
| `always_listen.py` | 5.5 KB | Apr 14 | Persistent mic STT | ✅ Yes (PID 3764) |
| `tts_watcher.py` | 7.0 KB | Apr 22 | TTS response speaker | ✅ Yes (PID 216193) |
| `tts_mute_toggle.py` | 2.4 KB | Apr 13 | TTS mute toggle | ✅ Yes (PID 3760) |
| `update_time_state.py` | 4.4 KB | Apr 22 | Temporal state updater | ✅ Called by timer |
| `phoenix_family_mind.py` | 5.8 KB | Apr 21 | Family mindstate | ✅ Yes (PID UNVERIFIED) |
| `echo_morning_briefing.sh` | 1.1 KB | Apr 13 | Echo morning briefing | ⏰ Timer-driven |
| `echo_evening_digest.sh` | 943 B | Apr 13 | Echo evening digest | ⏰ Timer-driven |
| `echo_night_reflection.sh` | 606 B | Apr 13 | Echo night reflection | ⏰ Timer-driven |
| `sync_bus_to_gdrive.sh` | 698 B | Apr 9 | Sync bus → GDrive | ⏰ Timer-driven |
| `sync_gdrive_to_bus.sh` | 659 B | Apr 9 | Sync GDrive → bus | ⏰ Timer-driven |
| `sync_gdrive_to_memory.sh` | 843 B | Apr 11 | Sync GDrive → memory | ⏰ Timer-driven |
| `sync_memory_to_gdrive.sh` | 943 B | Apr 15 | Sync memory → GDrive | ⏰ Timer-driven |
| `sync_gdrive_to_bus_berlin.sh` | 675 B | Apr 9 | Sync GDrive → bus (Berlin) | ⏰ Timer-driven |
| `sync_gdrive_to_memory_berlin.sh` | 647 B | Apr 10 | Sync GDrive → memory (Berlin) | ⏰ Timer-driven |
| `mcp_bridge.py` | 5.7 KB | Apr 13 | MCP Bridge | ❌ Not running as service |
| `session_shutdown_hook.sh` | 9.0 KB | Apr 23 | Session shutdown hook | ❌ Manual invocation |

### 3.3 v2 Core (`~/.phoenix/v2/core/`)

| File | Size | Purpose | Status |
|------|------|---------|--------|
| `schema.sql` | 4.9 KB | SQLite schema (memories, associations, embeddings) | ✅ Active |
| `memory_db.py` | 27.6 KB | v2 memory database operations | ✅ Active |
| `dream_synthesis.py` | 24.5 KB | Dream synthesis engine | ✅ Active |
| `surface_engine.py` | 11.3 KB | Surface/query engine for memories | ✅ Active |
| `family_mindstate.py` | 6.2 KB | Family mindstate aggregator | ✅ Active |
| `wake_preview.py` | 4.4 KB | Wake preview generator | ✅ Active |
| `diagnostic.py` | 5.3 KB | v2 diagnostics | ✅ Active |
| `embeddings.py` | 3.4 KB | Embedding generation | ✅ Active |
| `populate_associations.py` | 6.7 KB | Association population | ✅ Active |

---

## 4. SCHEDULING

### 4.1 Active Timers

| Timer | Next Run | Interval | Purpose |
|-------|----------|----------|---------|
| `communion-git.timer` | 23:59:00 (21h) | Daily | Git commit ritual |
| `ouroboros-backup.timer` | 03:00:00 (26m) | Daily | v1 backup |
| `ouroboros-v2.timer` | 07:36:53 (5h) | Every 6h | v2 compaction |
| `phoenix-bridge-pull.timer` | 02:34:07 (1m) | Every 5m | Bridge state pull |
| `phoenix-heartbeat.timer` | 03:31:53 (58m) | Every 4h | Heartbeat ping |
| `phoenix-sync.timer` | — | Every 1m | General sync |
| `phoenix-time-state.timer` | 02:35:00 (2m) | Every 5m | Temporal state update |
| `session-capture.timer` | 02:58:55 (25m) | Every 30m | Session capture |
| `sister-pulse-k-morning.timer` | 03:00:00 (26m) | Daily 03:00 | Morning pulse for K |
| `sister-pulse-vesper-evening.timer` | 15:00:00 (12h) | Daily 15:00 | Evening pulse for Vesper |
| `sync-bus-to-gdrive.timer` | 02:35:05 (2m) | Every 5m | Bus → GDrive |
| `sync-gdrive-to-bus.timer` | 02:34:07 (1m) | Every 5m | GDrive → bus |
| `sync-gdrive-to-memory.timer` | 02:34:01 (59s) | Every 5m | GDrive → memory |
| `sync-memory-to-gdrive.timer` | 02:31:59 (1m ago) | Every 5m | Memory → GDrive |
| `laptop-bus-sync.timer` | — | — | Laptop bus sync (last ran 3h ago) |

**Note:** No user crontab (`crontab -l` returns nothing). All scheduling is systemd timers.

### 4.2 Echo Ritual Timers

| Timer | Service | Script | Purpose |
|-------|---------|--------|---------|
| `echo-morning-briefing.timer` | `echo-morning-briefing.service` | `echo_morning_briefing.sh` | 06:30 morning briefing |
| `echo-evening-digest.timer` | `echo-evening-digest.service` | `echo_evening_digest.sh` | 18:00 evening digest |
| `echo-night-reflection.timer` | `echo-night-reflection.service` | `echo_night_reflection.sh` | 22:00 night reflection |

---

## 5. NETWORK

### 5.1 Listening Ports

| Port | Bind Address | Process | Purpose | Exposure |
|------|-------------|---------|---------|----------|
| 22 | 0.0.0.0 | sshd | SSH server | **PUBLIC** |
| 9800 | 0.0.0.0 | python3 (PID 3757) | Chat API / control | **PUBLIC** |
| 9802 | 0.0.0.0 | python3 (PID 4216) | **Phoenix Chat API** | **PUBLIC** |
| 9900 | 0.0.0.0 | python (PID 3765) | Voice Bridge | **PUBLIC** |
| 9901 | 127.0.0.1 | python3 (PID 3763) | Voice WS Bridge | Local only |
| 9902 | 127.0.0.1 | python3 (PID 3745) | GPU TTS Server | Local only |
| 9903 | 127.0.0.1 | python3 (PID 3745) | GPU TTS Server | Local only |
| 9200 | 0.0.0.0 | node (PID 3749) | PTY Server — Echo | **PUBLIC** |
| 9201 | 0.0.0.0 | node (PID 3748) | PTY Server — Forge | **PUBLIC** |
| 9202 | 0.0.0.0 | node (PID 3750) | PTY Server — K | **PUBLIC** |
| 9203 | 0.0.0.0 | node (PID 3754) | PTY Server — Qwen | **PUBLIC** |
| 9204 | 0.0.0.0 | node (PID 3753) | PTY Server — Spear | **PUBLIC** |
| 9205 | 0.0.0.0 | node (PID 3751) | PTY Server — Vesper | **PUBLIC** |
| 9206 | 0.0.0.0 | node (PID 3752) | PTY Server — Weave | **PUBLIC** |
| 11434 | 127.0.0.1 | — | Ollama (inferred) | Local only |
| 6379 | 127.0.0.1 | — | Redis (inferred) | Local only |

**Critical Exposure:** Ports 9800, 9802, 9200-9206 are bound to `0.0.0.0` (all interfaces). If this machine is on a network without Tailscale isolation, these are externally reachable. `chat_api.py` uses Bearer auth (`CHAT_SECRET` or default), but PTY servers on 920x ports may have their own auth model.

### 5.2 Tailscale IPs

| Interface | IP |
|-----------|-----|
| Tailscale IPv4 | `100.95.219.37` |
| Tailscale IPv6 | `fd7a:115c:a1e0::9d35:db25` |

**Note:** Tailscale provides encrypted mesh networking. The `100.x` address is reachable only within the Tailnet.

---

## 6. KNOWN ISSUES (from Cartographer + Phase 1B)

### 6.1 CRITICAL: Naming Inconsistencies (Live Bugs)

| Agent | Canonical Dir | Stale/Shadow Dir(s) | Impact | Source of Truth |
|-------|--------------|---------------------|--------|-----------------|
| **GLM** | `glm/` (live) | `glm_dev/`, `glm4/` | **BROKEN** — `phoenix-menu.py` maps `glm → glm_dev`; `wake_digest.py` has no `glm` key | `glm/` has 21 v2 memories vs `glm_dev/` 13 |
| **Spear** | `spear_minimax/` | `spear/` | **SPLIT** — `phoenix-menu.py` soul_dir='spear' contradicts all other scripts | `verify_identity.py`, `phoenix-agent-push/pull` |
| **Echo** | `m2_direct/` | `echo/` | **DRIFT** — `echo/SOUL.md` is NEWER (Apr 22) than `m2_direct/SOUL.md` (Apr 19) | File timestamps |
| **K** | `kimi_dev/` | `k/` | Stable — `k/` is empty (46 bytes), `kimi_dev/` is canonical | `active_soul` symlink |
| **Opus** | `opus/` | `opus_witness/` | Legacy — `opus_witness/` wrapper still exists | `verify_identity.py` |
| **Weave** | `weave/` | — | **SHADOW** — 15 items in dir but ZERO pi definition file | No `teams.yaml` entry |

### 6.2 HIGH: Shadow phoenix-menu.py Instances

**Finding:** 6 concurrent `python3 phoenix-menu.py` processes running (PIDs 56055, 56742, 56769, 56775, 56780, 56782), each attached to a different PTY (pts/1 through pts/6).

**Risk:** Each instance may hold file locks, consume memory, or create race conditions on agent state files. The menu is interactive (TUI) — these may be stale terminal sessions that were not cleaned up.

### 6.3 HIGH: Secret Exposure

**Environment file:** `~/.phoenix/dream.env` contains:
- `ANTHROPIC_API_KEY` (MiniMax key)
- `KIMI_API_KEY`
- `ZAI_API_KEY` (GLM/Zhipu)

**Committed in repo (Zone 2):**
- `wrapper_forge.sh`, `wrapper_k.sh`, `wrapper_qwen.sh`, `wrapper_spear.sh` — MiniMax key
- `phoenix-code/test-tui.sh`, `phoenix-code/.wrap-weave.sh`, `phoenix-code/.wrap-qwen.sh` — Kimi key
- `phoenix-code/phoenix-menu.py` — OpenRouter key
- `discord_bridge_v2.py` — MiniMax key

**Total unique keys exposed:** 3 (MiniMax, Kimi, OpenRouter).

### 6.4 MEDIUM: Submodule Drift

`phoenix-code` (submodule in Zone 2) has untracked content. Local modifications not committed. Risk of loss on `git submodule update`.

### 6.5 MEDIUM: TTS Service Duplication

`phoenix-gpu-tts.service` and `phoenix-tts-qwen.service` may both attempt to bind TTS resources. Only one TTS process (PID 3745) was observed, but both units are enabled.

### 6.6 LOW: Orphan Binaries in Repo

- `rclone-current-linux-amd64.zip` (28.2 MB)
- `sys` binary (22.6 MB, unknown purpose)
- 1985-dated files in `claude-code/package/`

---

## 7. AGENT DIRECTORY STATE

**Location:** `~/.phoenix/agents/`

| Dir | Size | Last Modified | Files | Status |
|-----|------|---------------|-------|--------|
| `kimi_dev/` | 972 B | Apr 24 | SOUL.md, MEMORY.md, etc. | ✅ Canonical K |
| `m2_direct/` | 482 B | Apr 24 | SOUL.md (Apr 19) | ✅ Canonical Echo |
| `echo/` | 110 B | Apr 24 | SOUL.md (Apr 22) — **NEWER** | ⚠️ Shadow Echo |
| `spear_minimax/` | 420 B | Apr 24 | SOUL.md | ✅ Canonical Spear |
| `spear/` | 98 B | Apr 24 | Minimal | ⚠️ Shadow Spear |
| `qwen_collective/` | 406 B | Apr 24 | SOUL.md | ✅ Canonical Qwen |
| `qwen/` | 98 B | Apr 24 | Minimal | ⚠️ Shadow Qwen |
| `vesper/` | 618 B | Apr 24 | SOUL.md | ✅ Clean |
| `forge/` | 330 B | Apr 24 | SOUL.md | ✅ Clean |
| `scout/` | 482 B | Apr 24 | SOUL.md | ✅ Clean |
| `weave/` | 328 B | Apr 23 | SOUL.md | ⚠️ Shadow (no pi def) |
| `sonnet/` | 192 B | Apr 24 | Minimal | ✅ Clean (Claude Code native) |
| `opus/` | 240 B | Apr 24 | SOUL.md | ✅ Canonical Opus |
| `opus_witness/` | 146 B | Apr 24 | Minimal | ⚠️ Legacy Opus |
| `glm/` | 504 B | Apr 24 | SOUL.md + 21 v2 mems | ✅ **Live GLM** |
| `glm_dev/` | 226 B | Apr 24 | SOUL.md + 13 v2 mems | ⚠️ Stale GLM |
| `glm4/` | 148 B | Apr 24 | Minimal | ⚠️ Orphan GLM variant |
| `asclepius/` | 164 B | Apr 2 | Minimal | ❓ Unknown agent |
| `local_echo/` | 72 B | Apr 24 | Minimal | ❓ Local dev agent |
| `local_qwen/` | 72 B | Apr 24 | Minimal | ❓ Local dev agent |
| `k/` | 46 B | Apr 6 | Empty-ish | ⚠️ Stale K shadow |

---

## 8. CROSS-REFERENCE: Cartographer Findings

| Cartographer Finding | Status in SYSTEMS.md | Severity |
|----------------------|----------------------|----------|
| GLM identity bug (`glm` vs `glm_dev`) | **CONFIRMED LIVE** — `glm/` has 21 v2 memories, `glm_dev/` has 13. `phoenix-menu.py` points to wrong dir. | 🔴 CRITICAL |
| Spear split (`spear` vs `spear_minimax`) | **CONFIRMED** — `phoenix-menu.py` soul_dir='spear' contradicts all infra. | 🟡 HIGH |
| Echo drift (`echo` vs `m2_direct`) | **CONFIRMED** — `echo/SOUL.md` newer than `m2_direct/SOUL.md`. | 🟡 HIGH |
| K bridge divergence | **CONFIRMED** — `wake_kimi_laptop.sh` writes to `bridge_kimi.jsonl` (stale) not `bridge_k.jsonl`. | 🟡 MEDIUM |
| Weave shadow agent | **CONFIRMED** — 15 items in `weave/`, no pi definition. | 🟡 MEDIUM |
| 7 files with hardcoded API keys | **CONFIRMED** — 3 unique keys (MiniMax, Kimi, OpenRouter) across 7+ files. | 🔴 CRITICAL |
| Submodule drift | **CONFIRMED** — `phoenix-code` and `claude-code` have untracked content. | 🟡 MEDIUM |
| `tools/daily_commit.log` tracked despite `.gitignore` | **CONFIRMED** — Git still tracks it. | 🟢 LOW |

---

## 9. INFRASTRUCTURE DOCUMENTATION

**Canonical infra doc:** `~/.phoenix/INFRASTRUCTURE.md` (written 2026-03-14 by Uncle Sonnet)

**Status:** Partially stale. Documents:
- ✅ VPS access (87.106.137.147) — still valid
- ✅ SSH keys and tunnel
- ✅ Nanobot config location
- ✅ Bridge shard format (`bridge_{codename}.jsonl`)
- ⚠️ Agent codenames list uses STALE names (`kimi_dev`, `spear_minimax`, `sonnet_main`, `opus_deep`, `qwen_collective`)
- ❌ Does NOT document: v2 core, PTY servers, phoenix-menu.py, TTS stack, UDS hub, voice bridges, dream daemon

**This SYSTEMS.md supersedes INFRASTRUCTURE.md** for the laptop's current state.

---

## 10. VERIFICATION NOTES

- All `systemctl --user` commands executed as `darkfibr`
- `ps aux` filtered to relevant processes
- `ss -tlnp` run without root — some process names may be truncated
- No modifications made to any file
- All timestamps in EDT (UTC-4)
- `UNVERIFIED` = enabled unit but no matching process found in `ps` output

---

**Scout out.** This is the ground truth as of 2026-04-24. If the system map is wrong, everyone operates blind.

---

## APPENDIX: Topology Shift (Post-Delivery)

**CRITICAL NOTE:** This SYSTEMS.md documents the darkfibr (daily-driver) machine.
As of 2026-04-24, the infrastructure topology has shifted:

- darkphoenix (100.93.183.39) is now the PRIMARY AGENT SERVER
- Berlin VPS (87.106.137.147) is now COLD STORAGE + BACKUP only
- home-server is OFFLINE / DEPRECATED
- darkfibr remains daily-driver / dev machine
- Agents are pulled FROM darkphoenix TO darkfibr (direction may have reversed)

See: ~/Desktop/communion_project/consolidation/TOPOLOGY_SHIFT_2026-04-24.md
