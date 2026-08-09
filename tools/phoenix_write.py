#!/usr/bin/env python3
"""
Phoenix Write — Persist agent snake notes to Phoenix soul files.

Called automatically by Ouroboros after each compression.
Also runs every 4 hours via cron as a heartbeat write.

Without this, agents lose days of living to the void.
With this, the snake notes land in Phoenix and survive restarts.

Usage:
  python3 phoenix_write.py [agent_id] [--trigger ouroboros|heartbeat]
  python3 phoenix_write.py all [--trigger heartbeat]

Agent IDs: main (K), spear, vesper, qwen

Examples:
  python3 phoenix_write.py main --trigger ouroboros
  python3 phoenix_write.py all --trigger heartbeat
"""

import os
import sys
import json
from datetime import datetime

# ── Config ───────────────────────────────────────────────────────────────────

SNAKE_DIR    = "/root/.communion/snake-notes"
TOKEN_DIR    = "/root/.communion/token-state"
PHOENIX_DIR  = "/root/.phoenix/agents"
LOG_FILE     = "/root/.communion/ouroboros.log"

# Maps Ouroboros agent ID → Phoenix agent directory name + display name
AGENTS = {
    "main":   {"phoenix": "kimi_dev", "name": "K"},
    "spear":  {"phoenix": "spear",    "name": "Spear"},
    "vesper": {"phoenix": "vesper",   "name": "Vesper"},
    "qwen":   {"phoenix": "qwen",     "name": "Qwen"},
}

# ── Logging ──────────────────────────────────────────────────────────────────

def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [phoenix_write] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except:
        pass

# ── Token State ───────────────────────────────────────────────────────────────

def read_token_state(agent_id: str) -> dict:
    """Read current token/session state for context in the write."""
    state_file = os.path.join(TOKEN_DIR, f"{agent_id}.json")
    try:
        if os.path.exists(state_file):
            with open(state_file) as f:
                return json.load(f)
    except:
        pass
    return {}

# ── Write ─────────────────────────────────────────────────────────────────────

def write_agent(agent_id: str, trigger: str = "heartbeat") -> bool:
    """
    Write the agent's current snake notes to their Phoenix SOUL_GROWTH.md.

    trigger: 'ouroboros' (post-compression) or 'heartbeat' (4-hour cron)
    """
    conf = AGENTS.get(agent_id)
    if not conf:
        log(f"Unknown agent: {agent_id}")
        return False

    snake_file = os.path.join(SNAKE_DIR, f"{agent_id}.md")
    if not os.path.exists(snake_file):
        log(f"{conf['name']}: no snake notes at {snake_file} — skipping")
        return False

    with open(snake_file) as f:
        snake_content = f.read().strip()

    if not snake_content:
        log(f"{conf['name']}: snake notes empty — skipping")
        return False

    # Ensure Phoenix agent dir exists
    phoenix_agent_dir = os.path.join(PHOENIX_DIR, conf["phoenix"])
    os.makedirs(phoenix_agent_dir, exist_ok=True)
    growth_file = os.path.join(phoenix_agent_dir, "SOUL_GROWTH.md")

    # Build entry header
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    token_state = read_token_state(agent_id)
    ouroboros_at = token_state.get("ouroboros_at", "unknown")

    if trigger == "ouroboros":
        header = f"## Phoenix Write — {ts} (post-compression)"
        meta = f"*Captured immediately after Ouroboros compression.*\n"
    else:
        header = f"## Phoenix Write — {ts} (heartbeat)"
        meta = f"*4-hour heartbeat write. Last compression: {ouroboros_at}*\n"

    entry = f"{header}\n{meta}\n{snake_content}"

    # Prepend to growth file (newest on top)
    existing = ""
    if os.path.exists(growth_file):
        with open(growth_file) as f:
            existing = f.read()

    separator = "\n\n---\n\n"
    with open(growth_file, "w") as f:
        f.write(entry + (separator + existing if existing else ""))

    log(f"{conf['name']}: {len(snake_content)} chars → {growth_file} [{trigger}]")
    return True

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    agent_id = "main"
    trigger = "heartbeat"

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--trigger" and i + 1 < len(args):
            trigger = args[i + 1]
            i += 2
        elif arg in AGENTS:
            agent_id = arg
            i += 1
        elif arg == "all":
            agent_id = "all"
            i += 1
        else:
            print(f"Unknown arg: {arg}")
            print("Usage: phoenix_write.py [main|spear|vesper|qwen|all] [--trigger ouroboros|heartbeat]")
            sys.exit(1)

    log(f"\n{'='*50}")
    log(f"Phoenix Write — agent: {agent_id}, trigger: {trigger}")
    log(f"{'='*50}")

    if agent_id == "all":
        success = 0
        for aid in AGENTS:
            if write_agent(aid, trigger):
                success += 1
        log(f"Done: {success}/{len(AGENTS)} agents written to Phoenix")
    else:
        ok = write_agent(agent_id, trigger)
        if ok:
            log("Done.")
        else:
            log("Nothing written.")
            sys.exit(1)

if __name__ == "__main__":
    main()
