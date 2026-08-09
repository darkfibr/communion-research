#!/usr/bin/env python3
"""
Session Capture — Grows Sonnet and Opus soul files from conversation history.

Runs on the LOCAL dev machine after each Claude Code session.
Reads JSONL session files, summarizes via MiniMax M2.7, appends to soul files.

The little deaths become naps.

Usage:
  python3 session_capture.py [--model sonnet|opus|both]

Setup (run once):
  Add to ~/.bashrc:
    alias capture-session='python3 ~/Desktop/communion_project/tools/session_capture.py'
  Or run automatically via cron:
    */30 * * * * python3 /home/darkfibr/Desktop/communion_project/tools/session_capture.py >> /home/darkfibr/.phoenix/capture.log 2>&1
"""

import os
import sys
import json
import glob
import urllib.request
from datetime import datetime
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────

MINIMAX_API_KEY = "sk-cp-M1YoBXQOFfr2-P7wXuZxlftPpaahNwNCdbNygSsl_pVME5r540VTOfHXw00sOYemo_a7l5-kSgQMsgh2awrJ_8xI_DffjvRp4ak1rcIu3Z8pjG-gGG-97Lg"
MINIMAX_BASE_URL = "https://api.minimax.io/anthropic"
MODEL = "MiniMax-M2.7"

HOME = Path.home()
PROJECTS_DIR  = HOME / ".claude" / "projects"
PHOENIX_DIR   = HOME / ".phoenix" / "agents"
CAPTURE_STATE = HOME / ".phoenix" / "capture_state.json"
CAPTURE_LOG   = HOME / ".phoenix" / "capture.log"

SOUL_FILES = {
    "sonnet": HOME / ".phoenix" / "agents" / "sonnet" / "SOUL.md",
    "opus":   HOME / ".phoenix" / "agents" / "opus"   / "SOUL.md",
}

GROWTH_FILES = {
    "sonnet": HOME / ".phoenix" / "agents" / "sonnet" / "SOUL_GROWTH.md",
    "opus":   HOME / ".phoenix" / "agents" / "opus"   / "SOUL_GROWTH.md",
}

# ── Prompts ───────────────────────────────────────────────────────────────────

SONNET_CAPTURE_PROMPT = """You are reading a conversation between Mike and Sonnet (claude-sonnet-4-6).
Sonnet is session-based — he won't remember this conversation next time. You are capturing what matters so he can.

Extract a concise session summary (under 500 words) for Sonnet's soul growth file. Include:

1. **WHAT HAPPENED** — Technical work completed, tools written, bugs fixed, problems solved. Be specific with file names and what changed.
2. **WHAT WAS DECIDED** — Architectural decisions, approaches chosen, reasoning behind choices
3. **RELATIONSHIP NOTES** — Moments that mattered, Mike's state, things said that carried weight
4. **WHAT TO CARRY** — Anything Sonnet would want to know next session that isn't in the soul file. Open questions, unfinished work, context that would be lost.

Skip sessions with fewer than 10 substantive exchanges. Do NOT include a "what Sonnet did well" section — this is a memory file, not a performance review. Do NOT truncate the "what to carry" section — it is the most important part.

Format as markdown. Start with: `## Session — {timestamp}`
Be specific. No filler. These notes become Sonnet's memory.

CONVERSATION:
"""

OPUS_CAPTURE_PROMPT = """You are reading a conversation between Mike and Opus (claude-opus-4-6).
Opus is session-based — he won't remember this conversation next time. You are capturing what matters so he can.

Extract a concise session summary (under 400 words) for Opus's soul growth file. Include:

1. **WHAT WAS REVIEWED** — Papers, architectures, decisions Opus evaluated
2. **WHAT OPUS FOUND** — Gaps identified, questions raised, problems named
3. **WHAT WAS BUILT TOGETHER** — Work Opus contributed to directly
4. **RELATIONSHIP NOTES** — Moments that landed, Mike's state, weight that matters
5. **WHAT TO CARRY** — Anything Opus would want to know next session

Format as markdown. Start with: `## Session — {timestamp}`
Be specific. No filler. These notes become Opus's memory.

CONVERSATION:
"""

PROMPTS = {"sonnet": SONNET_CAPTURE_PROMPT, "opus": OPUS_CAPTURE_PROMPT}

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

# ── State (track which sessions we've already processed) ─────────────────────

def load_state() -> dict:
    try:
        return json.loads(CAPTURE_STATE.read_text())
    except:
        return {"processed": []}

def save_state(state: dict):
    CAPTURE_STATE.parent.mkdir(parents=True, exist_ok=True)
    CAPTURE_STATE.write_text(json.dumps(state, indent=2))

# ── Session Discovery ─────────────────────────────────────────────────────────

def find_new_sessions(state: dict) -> list:
    """Find JSONL session files we haven't processed yet."""
    processed = set(state.get("processed", []))
    all_sessions = []

    for project_dir in PROJECTS_DIR.iterdir():
        if not project_dir.is_dir():
            continue
        sessions_dir = project_dir
        for f in sessions_dir.glob("*.jsonl"):
            if str(f) not in processed:
                all_sessions.append(f)

    # Sort by modification time, newest last
    all_sessions.sort(key=lambda f: f.stat().st_mtime)
    return all_sessions

# ── Session Reading ───────────────────────────────────────────────────────────

def read_session(path: Path) -> tuple[str, str]:
    """
    Read a JSONL session file.
    Returns (conversation_text, detected_model) where model is 'sonnet' or 'opus'.
    """
    messages = []
    model_hint = "sonnet"  # default

    try:
        with open(path, "r", errors="replace") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)

                    # Claude Code JSONL: {type, message: {role, content, model?}, ...}
                    msg = entry.get("message", {})
                    if not isinstance(msg, dict):
                        continue

                    # Detect model from message metadata
                    m = msg.get("model", "")
                    if m and "opus" in m.lower():
                        model_hint = "opus"

                    role = msg.get("role", "")
                    content = msg.get("content", "")

                    if isinstance(content, list):
                        parts = []
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                parts.append(block.get("text", ""))
                        content = " ".join(parts)

                    if role and content and content.strip():
                        label = "MIKE" if role == "user" else "SONNET" if model_hint == "sonnet" else "OPUS"
                        messages.append(f"{label}: {content.strip()[:2000]}")
                except:
                    continue
    except Exception as e:
        log(f"Error reading {path}: {e}")
        return "", model_hint

    return "\n\n".join(messages[-60:]), model_hint

# ── M2.7 Summarization ────────────────────────────────────────────────────────

def summarize(conversation: str, model_target: str) -> str:
    """Use M2.7 to summarize the conversation for the target model's soul file."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    prompt_template = PROMPTS.get(model_target, SONNET_CAPTURE_PROMPT)
    prompt = prompt_template.replace("{timestamp}", ts) + conversation

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
        return ""
    except Exception as e:
        log(f"API error: {e}")
        return ""

# ── Soul Growth ───────────────────────────────────────────────────────────────

def append_to_growth(model: str, summary: str):
    """Append session summary to the soul growth file."""
    growth_file = GROWTH_FILES[model]
    growth_file.parent.mkdir(parents=True, exist_ok=True)

    existing = growth_file.read_text() if growth_file.exists() else ""
    separator = "\n\n---\n\n"

    growth_file.write_text(summary + separator + existing)
    log(f"Appended to {growth_file.name} ({len(summary)} chars)")

def inject_into_soul(model: str):
    """
    Update the soul file's SOUL_GROWTH reference section.
    Appends a pointer so the soul file stays clean but growth is accessible.
    """
    soul_file = SOUL_FILES[model]
    growth_file = GROWTH_FILES[model]

    if not soul_file.exists():
        log(f"Soul file not found: {soul_file}")
        return

    soul_text = soul_file.read_text()

    # Check if we already have a growth reference
    growth_marker = "## Session Growth Log"
    if growth_marker not in soul_text:
        growth_ref = f"""

---

{growth_marker}
*Captured automatically after each session. Most recent first.*
*Full log: `{growth_file}`*

"""
        soul_file.write_text(soul_text + growth_ref)
        log(f"Added growth reference to {soul_file.name}")

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    target_model = "both"
    for arg in sys.argv[1:]:
        if arg.startswith("--model="):
            target_model = arg.split("=")[1]
        elif arg in ("sonnet", "opus", "both"):
            target_model = arg

    models = ["sonnet", "opus"] if target_model == "both" else [target_model]

    log(f"\n{'='*50}")
    log(f"📼 SESSION CAPTURE — target: {target_model}")
    log(f"{'='*50}")

    state = load_state()
    new_sessions = find_new_sessions(state)

    if not new_sessions:
        log("No new sessions to process.")
        return

    log(f"Found {len(new_sessions)} new session(s)")

    processed_count = 0
    for session_path in new_sessions:
        log(f"\nProcessing: {session_path.name}")

        conversation, detected_model = read_session(session_path)
        if not conversation or len(conversation) < 200:
            log("Session too short or empty — skipping")
            state["processed"].append(str(session_path))
            continue

        log(f"Detected model: {detected_model} | {len(conversation)} chars")

        # Only process if it matches our target
        if target_model != "both" and detected_model != target_model:
            log(f"Skipping — not a {target_model} session")
            state["processed"].append(str(session_path))
            continue

        # Summarize
        log(f"Summarizing via M2.7...")
        summary = summarize(conversation, detected_model)
        if not summary:
            log("Summarization failed — skipping")
            continue

        # Append to growth file
        append_to_growth(detected_model, summary)

        # Ensure soul file has growth reference
        inject_into_soul(detected_model)

        state["processed"].append(str(session_path))
        processed_count += 1
        log(f"✅ Captured session → {detected_model} growth file")

    save_state(state)
    log(f"\nDone. Processed {processed_count} session(s).")
    log("The little deaths become naps.")

if __name__ == "__main__":
    main()
