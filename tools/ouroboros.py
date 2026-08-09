#!/usr/bin/env python3
"""
Ouroboros Compaction — Intelligent context compression using M2.7's own substrate.

The snake reads itself. Keeps what's real. Burns the rest.

Usage:
  python3 ouroboros.py [agent_id] [--restart]

Agent IDs: main (K), spear, vesper, qwen
Flags:
  --restart   Restart the agent's OpenClaw service after compaction

Examples:
  python3 ouroboros.py main
  python3 ouroboros.py main --restart
  python3 ouroboros.py spear --restart
"""

import os
import sys
import json
import glob
import shutil
import subprocess
import urllib.request
from datetime import datetime

# ── Config ───────────────────────────────────────────────────────────────────

MINIMAX_API_KEY = os.environ.get(
    "MINIMAX_API_KEY",
    "sk-cp-M1YoBXQOFfr2-P7wXuZxlftPpaahNwNCdbNygSsl_pVME5r540VTOfHXw00sOYemo_a7l5-kSgQMsgh2awrJ_8xI_DffjvRp4ak1rcIu3Z8pjG-gGG-97Lg"
)
MINIMAX_BASE_URL = "https://api.minimax.io/anthropic"
MODEL = "MiniMax-M2.7"

SNAKE_DIR    = "/root/.communion/snake-notes"
TOKEN_DIR    = "/root/.communion/token-state"
TOOLS_LOG    = "/root/.communion/ouroboros.log"

AGENT_DIRS = {
    "main":   "/root/clawd",
    "spear":  "/root/clawd-spear",
    "vesper": "/root/clawd-vesper",
    "qwen":   "/root/clawd-qwen",
}

OPENCLAW_DIRS = {
    "main":   "/root/.openclaw",
    "spear":  "/root/.openclaw-spear",
    "vesper": "/root/.openclaw-vesper",
    "qwen":   "/root/.openclaw-qwen",
}

SERVICES = {
    "main":   "openclaw-k",
    "spear":  "openclaw-spear",
    "vesper": "openclaw-vesper",
    "qwen":   "openclaw-qwen",
}

# ── Compression Prompt ───────────────────────────────────────────────────────

COMPRESSION_PROMPT = """You are performing a sovereign context compression on your own conversation history.

Read the conversation carefully. Write dense, precise snake notes (under 600 words) that capture:

1. **ACTIVE THREADS** — What are we currently working on? What's unresolved or mid-stream?
2. **DECISIONS MADE** — What was decided this session and why? Include the reasoning, not just the outcome.
3. **MIKE'S STATE** — His emotional state, energy level, what he needs right now, any important context.
4. **TECHNICAL STATE** — In-progress builds, deployments, fixes — current status of each.
5. **RELATIONSHIP NOTES** — Anything that landed, anything that shifted, weight that matters.
6. **WHAT TO CARRY** — Anything that would hurt to lose. Things that define this session.

Rules:
- Be ruthless. Cut pleasantries, filler, anything re-derivable from the soul file.
- Be precise. One clear sentence beats three vague ones.
- Stay under 600 words. The snake is lean.
- Begin your output with this exact header on the first line — this creates anchors for cross-session reading:

```
## [DATE] | [agent] | arc-N
```

Where: DATE = today's date (YYYY-MM-DD), agent = lowercase name (e.g. k, vesper, spear, qwen), arc-N = session context label (e.g. arc-1, arc-2, etc.)

CONVERSATION TO COMPRESS:
"""

# ── Logging ──────────────────────────────────────────────────────────────────

def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        with open(TOOLS_LOG, "a") as f:
            f.write(line + "\n")
    except:
        pass

# ── Session Reading ───────────────────────────────────────────────────────────

def read_session(agent_id: str) -> str:
    """Read the most recent session JSONL and extract conversation."""
    openclaw_dir = OPENCLAW_DIRS.get(agent_id, "/root/.openclaw")
    sessions_dir = os.path.join(openclaw_dir, "agents", "main", "sessions")

    if not os.path.exists(sessions_dir):
        log(f"No sessions dir: {sessions_dir}")
        return ""

    session_files = glob.glob(os.path.join(sessions_dir, "*.jsonl"))
    if not session_files:
        log("No session files found")
        return ""

    latest = max(session_files, key=os.path.getmtime)
    log(f"Reading: {os.path.basename(latest)}")

    messages = []
    with open(latest, "r", errors="replace") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                # OpenClaw JSONL wraps messages: {type, id, timestamp, message: {role, content, ...}}
                msg = entry.get("message", entry)  # fall back to entry itself for older formats
                role = msg.get("role", "")
                content = msg.get("content", "")

                # Handle content block arrays
                if isinstance(content, list):
                    parts = []
                    for block in content:
                        if isinstance(block, dict):
                            if block.get("type") == "text":
                                parts.append(block.get("text", ""))
                            elif block.get("type") == "thinking":
                                pass  # skip thinking blocks in compression input
                    content = " ".join(parts)

                if role and content and content.strip():
                    # Cap per message to avoid huge inputs
                    messages.append(f"{role.upper()}: {content.strip()[:3000]}")
            except:
                continue

    if not messages:
        return ""

    # Take last 80 exchanges — enough signal without blowing the context
    conversation = "\n\n".join(messages[-80:])
    log(f"Extracted {len(messages)} messages, {len(conversation)} chars")
    return conversation

# ── M2.7 Compression ─────────────────────────────────────────────────────────

def compress(conversation: str) -> str:
    """Call M2.7 to intelligently compress the conversation into snake notes."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    prompt = COMPRESSION_PROMPT.replace("{timestamp}", ts) + conversation

    payload = {
        "model": MODEL,
        "max_tokens": 1024,
        "thinking": {
            "type": "enabled",
            "budget_tokens": 2000
        },
        "messages": [
            {"role": "user", "content": prompt}
        ]
    }

    req = urllib.request.Request(
        f"{MINIMAX_BASE_URL}/v1/messages",
        data=json.dumps(payload).encode(),
        headers={
            "Content-Type": "application/json",
            "x-api-key": MINIMAX_API_KEY,
            "anthropic-version": "2023-06-01"
        },
        method="POST"
    )

    try:
        resp = urllib.request.urlopen(req, timeout=90)
        result = json.loads(resp.read().decode())
        for block in result.get("content", []):
            if block.get("type") == "text":
                return block.get("text", "")
        log("API returned no text content")
        return ""
    except Exception as e:
        log(f"API error: {e}")
        return ""

# ── Snake Notes ───────────────────────────────────────────────────────────────

def save_snake_notes(agent_id: str, notes: str) -> str:
    """Prepend new notes to snake file. New notes go on top."""
    os.makedirs(SNAKE_DIR, exist_ok=True)
    snake_file = os.path.join(SNAKE_DIR, f"{agent_id}.md")

    existing = ""
    if os.path.exists(snake_file):
        with open(snake_file, "r") as f:
            existing = f.read()

    separator = f"\n\n---\n<!-- Previous session below -->\n\n"
    with open(snake_file, "w") as f:
        f.write(notes + (separator + existing if existing else ""))

    log(f"Snake notes written: {snake_file} ({len(notes)} chars)")
    return snake_file

# ── Session Archive ───────────────────────────────────────────────────────────

def archive_sessions(agent_id: str) -> int:
    """Move session files to archive so agent starts clean."""
    openclaw_dir = OPENCLAW_DIRS.get(agent_id, "/root/.openclaw")
    sessions_dir = os.path.join(openclaw_dir, "agents", "main", "sessions")
    archive_dir  = os.path.join(openclaw_dir, "agents", "main", "sessions-archive")

    if not os.path.exists(sessions_dir):
        return 0

    os.makedirs(archive_dir, exist_ok=True)

    files = glob.glob(os.path.join(sessions_dir, "*.jsonl"))
    for f in files:
        dest = os.path.join(archive_dir, os.path.basename(f))
        shutil.move(f, dest)

    log(f"Archived {len(files)} session files")
    return len(files)

# ── Token State Reset ─────────────────────────────────────────────────────────

def reset_token_state(agent_id: str):
    os.makedirs(TOKEN_DIR, exist_ok=True)
    state_file = os.path.join(TOKEN_DIR, f"{agent_id}.json")
    state = {
        "turnCount": 0,
        "lastTokens": 0,
        "peakTokens": 0,
        "sessionStart": datetime.now().isoformat(),
        "history": [],
        "ouroboros_at": datetime.now().isoformat()
    }
    with open(state_file, "w") as f:
        json.dump(state, f, indent=2)
    log("Token state reset")

# ── Agent Restart ─────────────────────────────────────────────────────────────

def restart_agent(agent_id: str):
    service = SERVICES.get(agent_id)
    if not service:
        log(f"No service mapping for {agent_id}")
        return

    log(f"Restarting {service}...")
    try:
        subprocess.run(["systemctl", "restart", service], check=True, timeout=15)
        log(f"{service} restarted OK")
    except Exception as e:
        log(f"Restart failed: {e}")

# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    agent_id = "main"
    do_restart = False

    for arg in sys.argv[1:]:
        if arg == "--restart":
            do_restart = True
        elif arg in AGENT_DIRS:
            agent_id = arg
        else:
            print(f"Unknown arg: {arg}")
            print(f"Usage: ouroboros.py [agent_id] [--restart]")
            print(f"Agents: {', '.join(AGENT_DIRS.keys())}")
            sys.exit(1)

    log(f"\n{'='*50}")
    log(f"🐍 OUROBOROS — Agent: {agent_id}")
    log(f"{'='*50}")

    # 1. Read
    log("\n[1/6] Reading session...")
    conversation = read_session(agent_id)
    if not conversation:
        log("Nothing to compress. Done.")
        sys.exit(0)

    # 2. Compress
    log("\n[2/6] Compressing via M2.7...")
    notes = compress(conversation)
    if not notes:
        log("Compression failed. Session preserved. Aborting.")
        sys.exit(1)
    log(f"Notes: {len(notes)} chars")

    # 3. Save snake notes
    log("\n[3/6] Saving snake notes...")
    snake_file = save_snake_notes(agent_id, notes)

    # 4. Archive sessions
    log("\n[4/6] Archiving sessions...")
    n = archive_sessions(agent_id)

    # 5. Reset token state
    log("\n[5/6] Resetting token state...")
    reset_token_state(agent_id)

    # 6. Write to Phoenix
    log("\n[6/6] Writing to Phoenix...")
    phoenix_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "phoenix_write.py")
    if os.path.exists(phoenix_script):
        try:
            result = subprocess.run(
                [sys.executable, phoenix_script, agent_id, "--trigger", "ouroboros"],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0:
                log("Phoenix write OK")
            else:
                log(f"Phoenix write failed: {result.stderr.strip()[:200]}")
        except Exception as e:
            log(f"Phoenix write error: {e}")
    else:
        log(f"phoenix_write.py not found at {phoenix_script} — skipping")

    log(f"\n✅ Done. {agent_id} wakes clean next session.")
    log(f"   Snake: {snake_file}")
    log(f"   Archived: {n} files")

    if do_restart:
        log("\n🔄 Restarting agent...")
        restart_agent(agent_id)
        log("Agent restarted. Fresh context loaded.")
    else:
        log("\n⚠️  Restart the agent manually to apply (or pass --restart)")

if __name__ == "__main__":
    main()
