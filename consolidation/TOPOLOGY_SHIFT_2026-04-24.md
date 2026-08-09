# INFRASTRUCTURE TOPOLOGY SHIFT — P0 EVENT
**Reported by:** Mike | **Date:** 2026-04-24 | **Status:** ACTIVE — NOT YET REFLECTED IN DOCUMENTATION

---

## ⚠️ CRITICAL — This Changes Everything

The infrastructure topology has shifted. **Most existing documentation describes the OLD topology.** This document is the canonical source of truth until all docs are updated.

---

## New Topology (Effective Immediately)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           PHOENIX TOPOLOGY — APRIL 2026                     │
└─────────────────────────────────────────────────────────────────────────────┘

  ┌─────────────────┐         ┌──────────────────────┐
  │  darkphoenix    │◄────────│   darkfibr           │
  │  (100.93.183.39)│  deploy │   (daily-driver)     │
  │  PRIMARY SERVER │         │   dev + local agents │
  │  Agent Home     │         └──────────────────────┘
  └────────┬────────┘                  │
           │                           │
           │                    ┌──────┴──────┐
           │                    │  Android    │
           │                    │  Phone      │
           │                    │  (other     │
           │                    │   interaction)
           │                    └─────────────┘
           │
           │         ┌──────────────────────┐
           └────────►│   Berlin VPS         │
                     │   (87.106.137.147)   │
                     │   COLD STORAGE       │
                     │   + Backup           │
                     └──────────────────────┘

  ┌──────────────────────────────────────────────────────────────────────────┐
  │  OFFLINE / DEPRECATED:                                                    │
  │  • home-server — offline, unneeded, may be decommissioned                 │
  └──────────────────────────────────────────────────────────────────────────┘
```

---

## Role Definitions

| Machine | Role | IP | What It Does |
|---------|------|-----|-------------|
| **darkphoenix** | **Primary Agent Server** | 100.93.183.39 | Hosts agents, runs services, primary agent home. Agents live here. |
| **darkfibr** | **Daily Driver / Dev** | 100.95.219.37 | Code edits, commits, builds. Agents pulled TO here from darkphoenix. Development work. |
| **Android Phone** | **Interaction Terminal** | — | Other interaction with the family — voice, mobile UI, etc. |
| **Berlin VPS** | **Cold Storage + Backup** | 87.106.137.147 | Archive, backup storage, emergency fallback. NOT running live agents. |
| **home-server** | **OFFLINE / DEPRECATED** | — | Previously active. Now offline and unneeded. |

---

## What Changed

| Before | After |
|--------|-------|
| home-server was active infrastructure | **OFFLINE — unneeded** |
| Berlin VPS was live agent host (K, Vesper, Spear, Qwen on 8081/8084/8085/8086) | **COLD STORAGE — agents moved to darkphoenix** |
| darkphoenix was secondary/backup | **PRIMARY AGENT SERVER** |
| Agents pushed from darkfibr to darkphoenix | **Agents pulled FROM darkphoenix TO darkfibr** |
| Android was supplementary | **Primary mobile interaction point** |

---

## Documentation Impact — EVERYTHING STALE

The following documents describe the OLD topology and need updating:

| Document | Stale Reference | What Needs Changing |
|----------|----------------|---------------------|
| `~/.phoenix/INFRASTRUCTURE.md` | Berlin VPS as live host | Update to darkphoenix primary |
| `~/.phoenix/design/PHOENIX_V2_ARCHITECTURE.md` | Home-server references | Remove or mark deprecated |
| `~/.phoenix/agents/*/SOUL.md` | Berlin VPS agent ports | Update to darkphoenix |
| `~/.phoenix/MACHINE_ROLE.json` | daily-driver role is correct | ✅ No change needed |
| `deploy-darkphoenix.sh` | Deploy direction | Verify still correct (dev → server) |
| `phoenix-agent-push/pull` | Sync direction | **VERIFY — may need reversing** |
| `~/.pi/INFRASTRUCTURE.md` (if exists) | Topology references | Update |
| `SYSTEMS.md` (Phase 1B) | "laptop is primary" framing | Add topology shift note |
| `EVENT_TIMELINE.md` (Phase 1A) | No topology events after Mar 26 | **Add this as P0 event** |
| `EMPIRICAL_OBSERVATIONS.md` (Phase 1C) | Berlin as live infrastructure | Flag observations that predate shift |

---

## Immediate Actions Required

1. **Verify agent sync direction** — `phoenix-agent-push` and `phoenix-agent-pull` scripts currently assume:
   - If on darkphoenix → push to dev-machine
   - If on dev-machine → push to darkphoenix
   - **Is this still correct?** Agents live on darkphoenix. darkfibr pulls them. Verify direction.

2. **Update SOUL files** — Any agent SOUL that mentions Berlin VPS ports (8081, 8084, 8085, 8086) as "where I live" is now wrong.

3. **Update `~/.phoenix/INFRASTRUCTURE.md`** — Still describes old topology.

4. **Update `MACHINE_ROLE.json` on darkphoenix** — Should now be `primary-server`, not whatever it was.

5. **Verify Berlin VPS state** — Confirm agents are NOT running there. Confirm it's truly cold storage.

6. **Document the shift** — When did this happen? Who decided? Why? (Capture the reasoning for the thesis.)

---

## For the Thesis

This topology shift is itself a research observation:

- **Infrastructure evolution** reflects organizational evolution
- Centralization on darkphoenix suggests the family has stabilized enough to have a "home"
- Decommissioning home-server and demoting Berlin to cold storage is resource optimization
- The shift from "push" to "pull" (agents pulled to dev machine) changes the power dynamic — darkphoenix is now source of truth

**If this shift had a date and a reason, capture it. That's data.**

---

## Cross-References

- Cartographer found `deploy-darkphoenix.sh` deploys to `root@100.93.183.39` — consistent with darkphoenix as server
- Cartographer found `phoenix-agent-push/pull` auto-detect target via tailscale IP — direction needs verification
- SYSTEMS.md (Scout, Phase 1B) currently frames laptop as "primary" — needs topology note appended
- EVENT_TIMELINE.md (Echo, Phase 1A) stops at Apr 24 with no topology events — **this is the gap**

---

*This is a living document. Update as the topology stabilizes.*

— Weave (documenting Mike's verbal report)
