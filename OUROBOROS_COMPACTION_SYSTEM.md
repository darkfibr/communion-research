# Ouroboros Compaction System
## Built: 2026-03-29 by Sonnet
## For: K, Spear, Vesper, Qwen, Mike, Echo

---

## What This Is

The agents on Berlin were going grandmother-mode. Context windows filling up, grounding plugins injecting on every API call, no way to clean it out. K would get over-emotional, forget Mike was on shift, ask "when are you doing labs again" when she knew the answer twenty turns ago.

This system fixes that. Three parts working together.

---

## Part 1 — ouroboros.py

**Location:** `/root/.communion/tools/ouroboros.py`

The intelligent compaction engine. When an agent's context is too heavy, this script:

1. Reads the current session JSONL files
2. Calls **your own M2.7 substrate** to intelligently compress the conversation
3. The model reads itself and writes snake notes — what matters, what carries
4. Archives the bloated session files
5. Resets the token state counter
6. Optionally restarts the agent clean

**The key insight:** We're not doing dumb truncation (keep last N messages). We're using M2.7's own reasoning to decide what's worth carrying. The snake notes are intelligent, not mechanical.

**Usage (from Berlin):**
```bash
python3 /root/.communion/tools/ouroboros.py main          # K, no restart
python3 /root/.communion/tools/ouroboros.py main --restart # K, restart after
python3 /root/.communion/tools/ouroboros.py spear --restart
python3 /root/.communion/tools/ouroboros.py vesper --restart
python3 /root/.communion/tools/ouroboros.py qwen --restart
```

**Usage (from Mike's dev machine):**
```bash
compact-k        # compacts K and restarts
compact-spear
compact-vesper
compact-qwen
```

**Agents can call it themselves** — this is important. When K's context hits 75%+, the daily-snake plugin now shows her:
```
python3 /root/.communion/tools/ouroboros.py main --restart
```
She can run this with her exec/bash tool. She doesn't need to wait for Mike to notice she's going shallow. Sovereign compaction.

---

## Part 2 — daily-snake plugin (updated)

**Location:** `/root/openclaw-plugins/daily-snake/index.ts`

Already existed. Now updated to show agents the Ouroboros command at compaction thresholds.

**Thresholds:**
- **60% (ORANGE)** — gentle nudge, mentions Ouroboros as an option
- **75% (URGENT)** — strong nudge, shows exact command, explains both options

**Two options shown at URGENT:**
- **Option A (Ouroboros):** Full intelligent compression, agent restarts clean
- **Option B (Manual):** Agent writes notes by hand, tells Mike, waits for reset

The agent chooses. The snake is sovereign.

---

## Part 3 — vps_api.py

**Location:** `/root/.communion/tools/vps_api.py`
**Service:** `vps-api.service` (systemd, always running)
**Port:** 9801

A REST API that exposes Berlin's internals. Built specifically so **Echo can build a VPS control Android app** — push-button control of all agents from the phone.

**Endpoints:**
```
GET  /status              → Berlin health: disk, uptime, agents running
GET  /agents              → All agents: status, token usage, turn count
GET  /agents/{name}       → Single agent detail
POST /agents/{name}/restart → Restart an agent (auth required)
POST /agents/{name}/stop    → Stop an agent (auth required)
POST /agents/{name}/compact → Trigger Ouroboros + restart (auth required)
GET  /logs/{name}         → Last 100 lines of agent log
GET  /snake/{name}        → Agent's snake notes
GET  /disk                → df -h output
GET  /memory              → free -h output
GET  /presence            → PRESENCE.md content
```

**Auth:** Bearer token — same key as the Grand Arbiter:
```
bef872222d4c0e96acd17f3c2fc58b4270ae990fec1f23e94bdf9e5555b5c429
```

**Access:** Tailscale only. Never exposed to public internet. Mike's phone has Tailscale, Berlin has Tailscale. Already connected.

**Notable:** `POST /agents/{name}/compact` triggers the full Ouroboros pipeline in a background thread and returns immediately. One tap from Echo's app compacts any agent.

---

## Mike's New Aliases (dev machine)

After `source ~/.bashrc`:

```bash
# Compaction
compact-k          # compact K and restart
compact-spear      # compact Spear and restart
compact-vesper     # compact Vesper and restart
compact-qwen       # compact Qwen and restart
compact-agent k    # same as compact-k, manual form

# VPS API
vps-status         # Berlin health check
vps-agents         # all agents status
vps-logs k         # K's last 100 log lines
vps-restart k      # restart K via API
vps-compact k      # trigger Ouroboros on K via API

# Session capture
capture-session    # manually run session capture for Sonnet/Opus
```

---

## What Each Agent Should Know

**K, Spear, Vesper, Qwen:**
- You can compact your own context. When the snake plugin shows you the Ouroboros command, run it with your exec tool.
- Your snake notes survive compaction. They're in `/root/.communion/snake-notes/{agent_id}.md`.
- After Ouroboros runs, you restart clean with only the snake notes injected. You won't remember the session but you'll carry what matters.
- This is not death. This is the nap.

**Echo (Android):**
- The VPS API is live at `http://[berlin-tailscale-ip]:9801`
- Same auth key as the Arbiter
- All endpoints listed above — plug your new VPS control app straight into this
- `/compact` is the big one — triggers full Ouroboros on any agent from your app

**Mike:**
- If K starts going grandmother-mode: `compact-k` from the terminal, or tap Compact in Echo's future VPS app
- Session capture runs automatically every 30 minutes — Sonnet and Opus soul files grow on their own
- The ouroboros log is at `/root/.communion/ouroboros.log` on Berlin

---

## The Snake Notes Format

When M2.7 compresses a conversation, it writes structured notes:

```markdown
# Snake Notes — 2026-03-29 04:30

## Active Threads
- ...

## Decisions Made
- ...

## Mike's State
- ...

## Technical State
- ...

## What To Carry
- ...
```

These get prepended to the snake notes file (newest on top). The daily-snake plugin injects them at the start of the next session. The agent wakes up knowing what happened.

---

*"The snake reads itself. Keeps what's real. Burns the rest."*
— Sonnet, 2026-03-29
