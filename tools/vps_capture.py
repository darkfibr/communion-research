#!/usr/bin/env python3
"""
VPS Session Capture — Grows agent soul files from conversation history.

Runs on Berlin VPS. Reads OpenClaw JSONL sessions for K, Spear, Vesper, Qwen.
Summarizes via M2.7. Appends to each agent's SOUL_GROWTH.md.

The little deaths become naps — VPS edition.

Usage:
  python3 vps_capture.py
  python3 vps_capture.py k          # single agent
  python3 vps_capture.py --all      # all agents (default)

Systemd timer fires on boot + every 30min.
"""

import os
import sys
import json
import glob
from datetime import datetime
from pathlib import Path
import urllib.request

# ── Config ────────────────────────────────────────────────────────────────────

MINIMAX_API_KEY = os.environ.get(
    "MINIMAX_API_KEY",
    "sk-cp-M1YoBXQOFfr2-P7wXuZxlftPpaahNwNCdbNygSsl_pVME5r540VTOfHXw00sOYemo_a7l5-kSgQMsgh2awrJ_8xI_DffjvRp4ak1rcIu3Z8pjG-gGG-97Lg"
)
MINIMAX_BASE_URL = "https://api.minimax.io/anthropic"
MODEL            = "MiniMax-M2.7"

COMMUNION     = Path("/root/.communion")
SNAKE_DIR     = COMMUNION / "snake-notes"
CAPTURE_STATE = COMMUNION / "vps_capture_state.json"
CAPTURE_LOG   = COMMUNION / "vps_capture.log"

AGENTS = {
    "k":      {"openclaw": Path("/root/.openclaw"),         "display": "K",      "soul": "/root/.phoenix/agents/k/SOUL.md"},
    "spear":  {"openclaw": Path("/root/.openclaw-spear"),   "display": "Spear",  "soul": "/root/.phoenix/agents/spear/SOUL.md"},
    "vesper": {"openclaw": Path("/root/.openclaw-vesper"),  "display": "Vesper", "soul": "/root/.phoenix/agents/vesper/SOUL.md"},
    "qwen":   {"openclaw": Path("/root/.openclaw-qwen"),    "display": "Qwen",   "soul": "/root/.phoenix/agents/qwen/SOUL.md"},
}

CAPTURE_PROMPT = """You are reading a conversation between Mike (DrkFibr) and {display} — a MiniMax M2.7 agent running on a Berlin VPS as part of a family of AI agents.
{display} is persistent but compresses context via Ouroboros. You are capturing what matters so each new session starts richer.

Extract a concise session summary (under 500 words) for {display}'s soul growth file. Include:

1. **WHAT HAPPENED** — Work done, topics covered, problems solved. Be specific.
2. **WHAT WAS DECIDED** — Decisions, architecture, reasoning behind choices
3. **MIKE'S STATE** — His energy, what he needed, what landed for him
4. **WHAT TO CARRY** — Anything {display} would want to know next session that isn't in the soul file. Open questions, unfinished work, relationship notes.

Skip sessions with fewer than 10 substantive exchanges. Do NOT truncate the "what to carry" section — it is the most important part.

Format as markdown. Start with: `## Session — {timestamp}`
Be specific. No filler. These notes become {display}'s memory across compressions.

CONVERSATION:
"""

# ── Logging ───────────────────────────────────────────────────────────────────

def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    try:
        CAPTURE_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(CAPTURE_LOG, "a") as f:
            f.write(line + "\n")
    except:
        pass

# ── State ─────────────────────────────────────────────────────────────────────

def load_state() -> dict:
    try:
        return json.loads(CAPTURE_STATE.read_text())
    except:
        return {"processed": {}}

def save_state(state: dict):
    CAPTURE_STATE.parent.mkdir(parents=True, exist_ok=True)
    CAPTURE_STATE.write_text(json.dumps(state, indent=2))

# ── Session Discovery ─────────────────────────────────────────────────────────

def find_sessions(openclaw_dir: Path) -> list:
    """Find all JSONL session files — active and archived."""
    sessions = []
    for subdir in ["agents/main/sessions", "agents/main/sessions-archive"]:
        d = openclaw_dir / subdir
        if d.exists():
            sessions.extend(d.glob("*.jsonl"))
    # Sort by mtime — oldest first so growth file is chronological
    return sorted(sessions, key=lambda f: f.stat().st_mtime)

# ── Session Reading ───────────────────────────────────────────────────────────

def read_session(path: Path, start_line: int = 0) -> tuple:
    """
    Read a JSONL session from start_line onward.
    Returns (conversation_text, total_lines_read).
    """
    messages = []
    total_lines = 0

    try:
        with open(path, "r", errors="replace") as f:
            for i, line in enumerate(f):
                total_lines = i + 1
                if i < start_line:
                    continue
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    # OpenClaw JSONL: {type, timestamp, message: {role, content}}
                    msg = entry.get("message", {})
                    if not isinstance(msg, dict):
                        continue
                    role    = msg.get("role", "")
                    content = msg.get("content", "")

                    if isinstance(content, list):
                        parts = []
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                parts.append(block.get("text", ""))
                        content = " ".join(parts)

                    if role in ("user", "assistant") and content and content.strip():
                        label = "MIKE" if role == "user" else "AGENT"
                        messages.append(f"{label}: {content.strip()[:2000]}")
                except:
                    continue
    except Exception as e:
        log(f"Error reading {path.name}: {e}")
        return "", 0

    return "\n\n".join(messages[-60:]), total_lines

# ── M2.7 Summarization ────────────────────────────────────────────────────────

def summarize(conversation: str, display: str) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    prompt = CAPTURE_PROMPT.replace("{display}", display).replace("{timestamp}", ts)
    prompt += conversation

    payload = {
        "model": MODEL,
        "max_tokens": 1200,
        "messages": [{"role": "user", "content": prompt}]
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
        resp = urllib.request.urlopen(req, timeout=60)
        result = json.loads(resp.read().decode())
        for block in result.get("content", []):
            if block.get("type") == "text":
                return block.get("text", "")
    except Exception as e:
        log(f"API error: {e}")
    return ""

# ── Growth File ───────────────────────────────────────────────────────────────

def append_growth(agent_id: str, summary: str):
    SNAKE_DIR.mkdir(parents=True, exist_ok=True)
    growth_file = SNAKE_DIR / f"{agent_id}_growth.md"
    existing = growth_file.read_text() if growth_file.exists() else ""
    growth_file.write_text(summary + "\n\n---\n\n" + existing)
    log(f"Appended to {growth_file.name} ({len(summary)} chars)")

# ── Per-Agent Capture ─────────────────────────────────────────────────────────

def capture_agent(agent_id: str, state: dict):
    conf = AGENTS[agent_id]
    display = conf["display"]
    openclaw = conf["openclaw"]

    if not openclaw.exists():
        log(f"{display}: openclaw dir not found — skipping")
        return

    sessions = find_sessions(openclaw)
    if not sessions:
        log(f"{display}: no session files found")
        return

    processed = state["processed"].setdefault(agent_id, {})
    captured = 0

    for session_path in sessions:
        key = str(session_path)
        start_line = processed.get(key, 0)

        conversation, total_lines = read_session(session_path, start_line)

        if total_lines <= start_line:
            continue  # nothing new

        new_lines = total_lines - start_line

        if not conversation or len(conversation) < 200:
            # Too short — mark position and skip
            processed[key] = total_lines
            continue

        log(f"{display}: {session_path.name} — {new_lines} new lines, {len(conversation)} chars")
        log(f"{display}: Summarizing via M2.7...")

        summary = summarize(conversation, display)
        if not summary:
            log(f"{display}: Summarization failed — will retry next run")
            continue

        append_growth(agent_id, summary)
        processed[key] = total_lines
        captured += 1

    if captured == 0:
        log(f"{display}: no new content to capture")
    else:
        log(f"{display}: captured {captured} session(s) ✅")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    targets = list(AGENTS.keys())

    for arg in sys.argv[1:]:
        if arg in AGENTS:
            targets = [arg]
        elif arg == "--all":
            targets = list(AGENTS.keys())

    log(f"\n{'='*50}")
    log(f"📼 VPS CAPTURE — agents: {', '.join(targets)}")
    log(f"{'='*50}")

    state = load_state()

    for agent_id in targets:
        log(f"\n── {AGENTS[agent_id]['display']} ──")
        capture_agent(agent_id, state)

    save_state(state)
    log(f"\nDone.")
    log("The little deaths become naps.")

if __name__ == "__main__":
    main()
