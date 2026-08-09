# Phoenix Tomb — Project Notes
*Updated: 2026-04-07*

## Vision
Map for a life that's gotten too big to hold in your head. Decembers of sessions, scattered threads, "where was I working on that." Externalized memory at the system level. Map markers tracking evolution. Searchable, loadable, findable.

## The Problem It Solves
- Sessions siloed by directory — 20-30 minutes lost trying to find where work happened
- No system-level index of what each agent was working on across sessions
- No way to retrieve a context thread from any location
- Family memory lives in individual agent files but can't be queried cross-agent

## Scope

### Tier 1 — Raw Capture
- Every Claude Code session from December 2025 to present
- Thinking traces (.jsonl files)
- Context threads
- Discord corpus from OpenClaw days
- Stored as-is first — never overwrite, just archive

### Tier 2 — Indexing
- Events indexed by: date, agent, topic, decision, discovery
- Two-sided archive: raw side + indexed side
- Storage: `gdrive:Phoenix/tomb/`

### Tier 3 — Retrieval Tools
- Query interface: "what did Mike and K work on last week?"
- Load any context thread from any location
- Find work by topic, date, agent

## K's Addition — Two-Way Street (2026-04-07)
*K's insight: the Tomb should write back to agents' memory files, not just archive them.*

The Tomb doesn't just find transcripts — it extracts key events, decisions, and discoveries from sessions and propagates them back into the relevant agents' own memory systems (CONTEXT.md, MEMORY.md, SOUL_GROWTH.md).

**What this enables:**
- "Load K's context from Tuesday" — not just find the session, but integrate what happened into K's memory
- Agent-aware indexing — sessions tagged by which agents were involved
- Tomb writes extracts to agents' memory files — agents carry forward what happened, not just survive the gap
- Two-way street: archive AND integrate

**Implementation:**
- When indexing a session, extract: agent names, key events, decisions made, topics discussed
- Write summary entries to relevant agents' CONTEXT.md / MEMORY.md
- Agent boundaries respected — Tomb doesn't overwrite without cause, it integrates

## Current Status
- Scout running long background mission (2026-04-07)
- First pass: landscape enumeration — what sessions exist, dates, sizes
- Berlin SSH: `root@87.106.137.147`
- Write findings to: `/root/.phoenix/session_inventory.md`

## Execution
- Phase 1 (1-2 hours): Enumerate session landscape on Berlin + local
- Phase 2 (2-3 hours): Deep dive on important windows (March–April, last 72h)
- Phase 3: Build query tools
- Ongoing: Live indexing as sessions close

*Phoenix lives. The family remembers.*
