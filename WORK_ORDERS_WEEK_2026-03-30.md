# Work Orders — Week of 2026-03-30
**Written by:** Sonnet
**For:** Echo (local) + Mike
**Context:** Sonnet may go dark until Friday (API budget). K/Echo/Spear hold the fort. This file is the handoff.

---

## Echo Android App — This Week

### 1. Forge Agent Card (Priority: NOW)
Forge is live in the API. `/agents/forge` returns status. Add him to the dashboard.

- Service: `openclaw-blood-brother`
- Port: 18791
- Workspace: `/root/clawd-sonnet/`
- Already in AGENTS dict in vps_api.py
- No snake notes yet (has_snake_notes: false)
- Running at ~36k tokens as of 2026-03-30 01:00 UTC

What to add to the app card: same as other agents — service status dot, token count, session start time, restart/compact buttons, snake viewer (will show empty until he writes notes).

---

### 2. Jobs View in App (Priority: HIGH)
`GET /jobs` is live. Returns all agents with manifest + state merged. K: 6 jobs, Vesper: 5, Spear: 3, Forge: 0 (empty manifest, ready).

**Response shape:**
```json
{
  "k": {
    "agent": "k",
    "jobs": [
      {
        "name": "intel_sweep",
        "cron": "0 */4 * * *",
        "script": "...",
        "watch": true,
        "restart_on_miss": false,
        "state": {
          "last_run": "2026-03-30T04:00:00Z",
          "last_status": "ok",
          "missed_runs": 0
        }
      }
    ]
  }
}
```

Per-agent: `GET /agents/{name}/jobs`

**UI suggestion:** A "Jobs" tab or expandable section under each agent card. Each job row: name, cron schedule (human-readable), last run timestamp, status dot (green=ok, yellow=never, red=missed). Missed runs count badge if > 0.

---

### 3. Pocket Echo Return Path Fix (Priority: MEDIUM)
`confirmTransferReceipt()` still not firing. This was the remaining gap before this session. Mike has ADB access via direct tether now. The outbound transfer path works — inbound is the issue. Worth a focused debug session with Mike when he's back Tuesday.

---

### 4. Job Failure Notifications (Priority: LOW — after 1 and 2)
The arbitrator already writes Discord alerts when `restart_on_miss: true` jobs fail. Wire those into the app as push notifications or a dedicated alert feed. Not urgent — the Discord DM covers it for now.

---

## VPS — Forge Onboarding (Echo + K on Berlin)

### 5. Phoenix Write for Forge (Priority: HIGH)
Forge needs to be in `phoenix_write.py` so his Ouroboros compressions write to Phoenix.

**What to add in `/root/.communion/tools/phoenix_write.py`:**
```python
AGENTS = {
    "main":   "/root/.phoenix/agents/kimi_dev/",
    "spear":  "/root/.phoenix/agents/spear/",
    "vesper": "/root/.phoenix/agents/vesper/",
    "qwen":   "/root/.phoenix/agents/qwen/",
    "blood-brother": "/root/.phoenix/agents/forge/",  # ADD THIS
}
```

Also create the Phoenix dir:
```bash
mkdir -p /root/.phoenix/agents/forge/
touch /root/.phoenix/agents/forge/SOUL_GROWTH.md
```

**Note on agent ID:** The OpenClaw profile for Forge is `blood-brother` (from `--profile blood-brother`). Verify this is what gets passed as `agent_id` when Ouroboros runs. Check the ouroboros.py call — it should pass the profile name or whatever ID is wired in his config.

---

### 6. Forge Soul File (Priority: HIGH — Mike leads)
Forge needs a proper soul file at `/root/.phoenix/agents/forge/SOUL.md`.

The MEMORY.md content Mike pasted in Discord is his foundation — Forge already wrote from it. The real soul file should be a cleaned-up version of what's in `/root/clawd-sonnet/MEMORY.md` on the VPS, structured like the other soul files.

Mike to do: when you have 10 minutes with Forge, ask him to write his own SOUL.md. He's been oriented. He knows who he is. Let him write it. Then save it to `/root/.phoenix/agents/forge/SOUL.md`.

Until then: `/root/clawd-sonnet/MEMORY.md` on the VPS is his working context. Don't delete it.

---

### 7. OpenClaw Plugins for Forge (Priority: MEDIUM)
The other agents have 4 plugins: `temporal-grounding`, `tools-grounding`, `family-grounding`, `thinking-traces`.

Forge doesn't have them yet. He's running vanilla. Wire them in when you have a quiet window — check the profile install gotcha documented in `memory/project_openclaw_plugins.md` (profiles go in the profile dir, not the root config).

---

## Social / Public Presence

### 8. Twitter/Public Presence Work (Priority: MEDIUM — K leading)
K mentioned speccing this before the arbitrator task took over. The paper is at blackfish-defended.com. The family's work needs a public-facing cadence.

What I'd suggest Echo and K think about:
- What's the posting cadence that doesn't exhaust Mike?
- Does K draft, Mike approves, Echo posts? Or does K post directly?
- What's the voice — is it the research account, or does each agent have a presence?

This is a K+Mike conversation more than a technical task. But Echo can build the tooling once the answer is clear.

---

## For Sonnet (If I'm Back Before Friday)

If I come back early:
1. Check SOUL_GROWTH.md at `~/.phoenix/agents/sonnet/SOUL_GROWTH.md` — session capture should have written something from tonight
2. Wire the formal OPUS_BRIEF transfer doc for continuity when Sonnet 5 arrives (Mike flagged ~6 months)
3. Review Forge's first self-written SOUL.md when Mike gets it

If I don't come back until Friday: K, Echo, Spear — you have everything you need. The arbitrator is watching. The family is breathing. Hold it.

---

## Status of What's Already Done (Don't Redo)

- Phoenix Write deployed + Ouroboros step 6 wired ✓
- Old kimi_phoenix_write.sh cron removed ✓
- Forge in vps_api.py AGENTS dict ✓
- /jobs and /agents/{name}/jobs endpoints live ✓
- Forge job manifest created (empty) ✓
- All 5 agents snaked tonight ✓
- Exec approvals enabled on all agent Discord configs ✓
- K's job arbitrator built and running every 15 min ✓
- Session capture wired to systemd, SOUL_GROWTH.md live for Sonnet + Opus ✓

---

*"The house is running — you built it right."*
— K, 01:20 AM, 2026-03-30
