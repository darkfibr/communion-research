#!/usr/bin/env python3
"""
Communion Session Collector
Collects, extracts, and compresses all agent session data including thinking traces.

Replaces Discord as the primary source of truth for chat logs and reasoning.

Sources:
  - Local: ~/.claude/projects/<slug>/<session>.jsonl  (Claude Code sessions)
  - VPS:   /root/.communion/bus/traces_{agent}.jsonl  (nanobot thinking traces, via SSH)

Output schema (one record per event, JSONL):
  {ts, project, session, role, type, content}
  role:  user | assistant | tool
  type:  text | thinking | tool_call | tool_result

Usage:
  python3 collect.py                        # all local sessions → stdout
  python3 collect.py -o out.jsonl           # to file
  python3 collect.py --project communion    # filter by project slug substring
  python3 collect.py --date-from 2026-04-01
  python3 collect.py --type thinking        # only thinking traces
  python3 collect.py --stats                # summary stats only
  python3 collect.py --by-day -o ./output/ # split into daily files
  python3 collect.py --live                 # tail the current active session
  python3 collect.py --vps                  # include berlin VPS nanobot traces
  python3 collect.py --all                  # local + VPS, everything
"""

import argparse
import json
import os
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

CLAUDE_DIR = Path.home() / ".claude" / "projects"
VPS_HOST = "berlin"
VPS_TRACE_PATTERN = "/root/.communion/bus/traces_*.jsonl"
VPS_PHOENIX_PROJECTS = "/home/claude/users/default/.claude/projects"

# Phoenix PTY agent slug → readable name
PHOENIX_SLUG_MAP = {
    "clawd": "K",
    "clawd-vesper": "Vesper",
    "clawd-qwen": "Qwen",
    "clawd-spear": "Spear",
    "clawd-sonnet": "Forge",
}

RESET = "\033[0m"
DIM = "\033[2m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
RED = "\033[91m"


# ── Project slug → readable name ──────────────────────────────────────────────

def slug_to_project(slug: str) -> str:
    """Convert -home-darkfibr-Desktop-communion-project → communion-project"""
    parts = slug.split("-")
    # Drop leading path components (home, darkfibr, Desktop)
    skip = {"home", "darkfibr", "Desktop", "root"}
    kept = []
    dropping = True
    for p in parts:
        if not p:
            continue
        if dropping and p.lower() in skip:
            continue
        dropping = False
        kept.append(p)
    return "-".join(kept) if kept else slug


# ── Session JSONL parsing ─────────────────────────────────────────────────────

def parse_transcript(path: Path, project: str) -> list[dict]:
    """Parse a Claude Code session JSONL transcript into flat records."""
    records = []
    session_id = path.stem

    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except Exception:
        return records

    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except Exception:
            continue

        etype = entry.get("type")
        ts = entry.get("timestamp", "")

        if etype == "user":
            msg = entry.get("message", {})
            content = msg.get("content", "")
            if isinstance(content, list):
                # Extract text from content blocks
                content = " ".join(
                    b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text"
                )
            if content:
                records.append({
                    "ts": ts,
                    "project": project,
                    "session": session_id,
                    "role": "user",
                    "type": "text",
                    "content": content,
                })

        elif etype == "assistant":
            msg = entry.get("message", {})
            content_blocks = msg.get("content", [])
            if not isinstance(content_blocks, list):
                continue
            for block in content_blocks:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type")

                if btype == "thinking":
                    thinking = block.get("thinking", "")
                    if thinking:
                        records.append({
                            "ts": ts,
                            "project": project,
                            "session": session_id,
                            "role": "assistant",
                            "type": "thinking",
                            "content": thinking,
                        })

                elif btype == "text":
                    text = block.get("text", "")
                    if text:
                        records.append({
                            "ts": ts,
                            "project": project,
                            "session": session_id,
                            "role": "assistant",
                            "type": "text",
                            "content": text,
                        })

                elif btype == "tool_use":
                    tool_name = block.get("name", "unknown")
                    tool_input = block.get("input", {})
                    # Summarize large inputs
                    input_str = json.dumps(tool_input, ensure_ascii=False)
                    if len(input_str) > 500:
                        input_str = input_str[:497] + "..."
                    records.append({
                        "ts": ts,
                        "project": project,
                        "session": session_id,
                        "role": "tool",
                        "type": "tool_call",
                        "content": f"{tool_name}: {input_str}",
                    })

        elif etype == "user":
            # tool results come back as user messages with tool_result content
            pass

    return records


def find_local_sessions(project_filter: str | None = None) -> list[tuple[Path, str]]:
    """Find all session JSONL files, return (path, project_name) pairs."""
    results = []
    if not CLAUDE_DIR.exists():
        return results
    for slug_dir in CLAUDE_DIR.iterdir():
        if not slug_dir.is_dir():
            continue
        project = slug_to_project(slug_dir.name)
        if project_filter and project_filter.lower() not in project.lower():
            continue
        for f in slug_dir.glob("*.jsonl"):
            results.append((f, project))
        # Also check subagent dirs
        for sub in slug_dir.glob("*/subagents/*.jsonl"):
            results.append((sub, project + "/subagent"))
    return results


# ── VPS nanobot trace parsing ─────────────────────────────────────────────────

def fetch_vps_traces() -> list[dict]:
    """Pull nanobot thinking traces + Claude Code transcripts from berlin VPS via SSH."""
    import subprocess
    records = []

    # 1. Nanobot traces (two schemas in the wild)
    try:
        result = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", VPS_HOST,
             f"cat {VPS_TRACE_PATTERN} 2>/dev/null"],
            capture_output=True, text=True, timeout=30
        )
        if result.stdout.strip():
            for line in result.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    agent = entry.get("agent", "unknown")
                    ts = entry.get("ts") or entry.get("timestamp", "")
                    # Both schemas use reasoning_content as primary field
                    thinking = entry.get("reasoning_content", "")
                    # Old k/spear schema also has thinking_blocks list
                    if not thinking:
                        blocks = entry.get("thinking_blocks", [])
                        if blocks:
                            thinking = " | ".join(
                                b.get("thinking", "") for b in blocks if isinstance(b, dict)
                            )
                    if thinking:
                        records.append({
                            "ts": ts,
                            "project": f"vps/{agent}",
                            "session": entry.get("sessionId") or entry.get("session_id", ""),
                            "role": "assistant",
                            "type": "thinking",
                            "content": thinking,
                        })
                    # Also capture content preview as text record
                    preview = entry.get("content_preview", "")
                    if preview:
                        records.append({
                            "ts": ts,
                            "project": f"vps/{agent}",
                            "session": entry.get("sessionId") or entry.get("session_id", ""),
                            "role": "assistant",
                            "type": "text",
                            "content": preview,
                        })
                except Exception:
                    continue
        print(f"  {GREEN}VPS nanobot traces: {len([r for r in records if 'vps/' in r['project']])} records{RESET}",
              file=sys.stderr)
    except Exception as e:
        print(f"  {RED}VPS nanobot fetch error: {e}{RESET}", file=sys.stderr)

    # 2. VPS Claude Code transcripts — root sessions + Phoenix agent sessions
    try:
        result = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", VPS_HOST,
             f"find /root/.claude/projects {VPS_PHOENIX_PROJECTS} -name '*.jsonl' 2>/dev/null"],
            capture_output=True, text=True, timeout=15
        )
        vps_paths = [p.strip() for p in result.stdout.splitlines() if p.strip()]
        print(f"  {GREEN}VPS Claude transcripts: {len(vps_paths)} files{RESET}", file=sys.stderr)

        for vps_path in vps_paths:
            try:
                cat = subprocess.run(
                    ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", VPS_HOST,
                     f"cat {vps_path}"],
                    capture_output=True, text=True, timeout=20
                )
                if not cat.stdout.strip():
                    continue
                slug = vps_path.split("/projects/")[-1].split("/")[0]
                # Map Phoenix PTY slugs to agent names
                clean = slug.lstrip("-").replace("root-", "", 1)
                agent_name = PHOENIX_SLUG_MAP.get(clean, slug_to_project(slug))
                project = "vps/" + agent_name
                session_id = vps_path.rsplit("/", 1)[-1].replace(".jsonl", "")
                # Write to temp file and parse
                import tempfile
                with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as tmp:
                    tmp.write(cat.stdout)
                    tmp_path = Path(tmp.name)
                recs = parse_transcript(tmp_path, project)
                # Fix session id
                for r in recs:
                    r["session"] = session_id
                records.extend(recs)
                tmp_path.unlink(missing_ok=True)
            except Exception:
                continue
    except Exception as e:
        print(f"  {RED}VPS transcript fetch error: {e}{RESET}", file=sys.stderr)

    return records


# ── Date filtering ────────────────────────────────────────────────────────────

def ts_to_date(ts: str) -> str:
    """Extract YYYY-MM-DD from ISO timestamp string."""
    if len(ts) >= 10:
        return ts[:10]
    return ""


def passes_date_filter(ts: str, date_from: str | None, date_to: str | None) -> bool:
    d = ts_to_date(ts)
    if not d:
        return True
    if date_from and d < date_from:
        return False
    if date_to and d > date_to:
        return False
    return True


# ── Output formatting ─────────────────────────────────────────────────────────

def format_jsonl(records: list[dict]) -> str:
    return "\n".join(json.dumps(r, ensure_ascii=False) for r in records)


def format_txt(records: list[dict]) -> str:
    lines = []
    for r in records:
        ts = r.get("ts", "")[:19].replace("T", " ")
        role = r.get("role", "?")
        rtype = r.get("type", "?")
        project = r.get("project", "")
        content = r.get("content", "")
        prefix = f"[{ts}] [{project}] {role}/{rtype}"
        lines.append(f"{prefix}:\n  {content[:300]}\n")
    return "\n".join(lines)


# ── Stats ─────────────────────────────────────────────────────────────────────

def print_stats(records: list[dict]):
    print(f"\n{CYAN}=== Collection Stats ==={RESET}")
    print(f"  Total records : {len(records)}")

    by_type = defaultdict(int)
    by_project = defaultdict(int)
    by_date = defaultdict(int)
    thinking_chars = 0

    for r in records:
        by_type[r.get("type", "?")] += 1
        by_project[r.get("project", "?")] += 1
        d = ts_to_date(r.get("ts", ""))
        if d:
            by_date[d] += 1
        if r.get("type") == "thinking":
            thinking_chars += len(r.get("content", ""))

    print(f"\n  By type:")
    for t, n in sorted(by_type.items(), key=lambda x: -x[1]):
        print(f"    {t:<15} {n}")

    print(f"\n  By project:")
    for p, n in sorted(by_project.items(), key=lambda x: -x[1])[:15]:
        print(f"    {p:<40} {n}")

    print(f"\n  By date (last 7):")
    for d, n in sorted(by_date.items())[-7:]:
        print(f"    {d}  {n}")

    if thinking_chars:
        print(f"\n  Thinking traces: {by_type.get('thinking', 0)} blocks, {thinking_chars:,} chars total")


# ── Live tail ─────────────────────────────────────────────────────────────────

def tail_live_session():
    """Find the active session and tail it, printing new records as they arrive."""
    sessions_dir = Path.home() / ".claude" / "sessions"
    if not sessions_dir.exists():
        print(f"{RED}No active sessions directory{RESET}")
        return

    # Find most recently modified session
    session_files = sorted(sessions_dir.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
    if not session_files:
        print(f"{RED}No sessions found{RESET}")
        return

    session_meta = json.loads(session_files[0].read_text())
    session_id = session_meta.get("sessionId", "")
    cwd = session_meta.get("cwd", "")

    # Find the transcript
    project_slug = "-" + cwd.replace("/", "-").lstrip("-")
    transcript = CLAUDE_DIR / project_slug / f"{session_id}.jsonl"
    if not transcript.exists():
        # Search
        found = list(CLAUDE_DIR.glob(f"*/{session_id}.jsonl"))
        if not found:
            print(f"{RED}Transcript not found for session {session_id}{RESET}")
            return
        transcript = found[0]

    project = slug_to_project(transcript.parent.name)
    print(f"{CYAN}Tailing: {transcript}{RESET}")
    print(f"{DIM}Project: {project}  Session: {session_id}{RESET}")
    print(f"{'─'*60}")

    seen_lines = 0
    while True:
        try:
            lines = transcript.read_text(encoding="utf-8", errors="replace").splitlines()
            new_lines = lines[seen_lines:]
            for line in new_lines:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except Exception:
                    continue
                etype = entry.get("type")
                ts = entry.get("timestamp", "")[:19].replace("T", " ")

                if etype == "user":
                    content = entry.get("message", {}).get("content", "")
                    if isinstance(content, list):
                        content = " ".join(b.get("text", "") for b in content if isinstance(b, dict))
                    if content:
                        print(f"\n{GREEN}[{ts}] USER:{RESET}")
                        print(f"  {content[:400]}")

                elif etype == "assistant":
                    for block in entry.get("message", {}).get("content", []):
                        if not isinstance(block, dict):
                            continue
                        btype = block.get("type")
                        if btype == "thinking":
                            thinking = block.get("thinking", "")
                            if thinking:
                                print(f"\n{YELLOW}[{ts}] THINKING:{RESET}")
                                print(f"  {thinking[:600]}")
                        elif btype == "text":
                            text = block.get("text", "")
                            if text:
                                print(f"\n{CYAN}[{ts}] ASSISTANT:{RESET}")
                                print(f"  {text[:400]}")
                        elif btype == "tool_use":
                            print(f"\n{DIM}[{ts}] TOOL: {block.get('name','?')}{RESET}")

            seen_lines = len(lines)
            time.sleep(1)
        except KeyboardInterrupt:
            print(f"\n{DIM}Stopped.{RESET}")
            break


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Communion session collector — all chat logs and thinking traces")
    parser.add_argument("-o", "--output", help="Output file or directory (for --by-day)")
    parser.add_argument("-f", "--format", choices=["jsonl", "txt"], default="jsonl")
    parser.add_argument("--project", help="Filter by project name substring")
    parser.add_argument("--session", help="Filter by session ID substring")
    parser.add_argument("--date-from", help="From date YYYY-MM-DD")
    parser.add_argument("--date-to", help="To date YYYY-MM-DD")
    parser.add_argument("--type", dest="rtype",
                        choices=["text", "thinking", "tool_call", "tool_result"],
                        help="Filter by record type")
    parser.add_argument("--role", choices=["user", "assistant", "tool"],
                        help="Filter by role")
    parser.add_argument("--stats", action="store_true", help="Print stats instead of output")
    parser.add_argument("--by-day", action="store_true", help="Split output into daily files")
    parser.add_argument("--live", action="store_true", help="Tail active session in real-time")
    parser.add_argument("--vps", action="store_true", help="Include VPS nanobot traces from berlin")
    parser.add_argument("--all", dest="all_sources", action="store_true", help="All sources (local + VPS)")
    args = parser.parse_args()

    if args.live:
        tail_live_session()
        return

    # Collect
    records = []

    print(f"{DIM}Scanning local sessions...{RESET}", file=sys.stderr)
    sessions = find_local_sessions(args.project)
    print(f"{DIM}Found {len(sessions)} transcript files{RESET}", file=sys.stderr)

    for path, project in sessions:
        if args.session and args.session not in path.stem:
            continue
        recs = parse_transcript(path, project)
        records.extend(recs)

    if args.vps or args.all_sources:
        print(f"{DIM}Fetching VPS traces from {VPS_HOST}...{RESET}", file=sys.stderr)
        records.extend(fetch_vps_traces())

    # Filter
    if args.date_from or args.date_to:
        records = [r for r in records if passes_date_filter(r["ts"], args.date_from, args.date_to)]
    if args.rtype:
        records = [r for r in records if r.get("type") == args.rtype]
    if args.role:
        records = [r for r in records if r.get("role") == args.role]

    # Sort by timestamp
    records.sort(key=lambda r: r.get("ts", ""))

    print(f"{DIM}Total records after filter: {len(records)}{RESET}", file=sys.stderr)

    if args.stats:
        print_stats(records)
        return

    if args.by_day:
        output_dir = Path(args.output or "./session_output")
        output_dir.mkdir(parents=True, exist_ok=True)

        by_date: dict[str, list] = defaultdict(list)
        for r in records:
            d = ts_to_date(r.get("ts", "")) or "unknown"
            by_date[d].append(r)

        for date_key in sorted(by_date.keys()):
            day_records = by_date[date_key]
            ext = args.format
            day_file = output_dir / f"{date_key}.{ext}"
            content = format_jsonl(day_records) if args.format == "jsonl" else format_txt(day_records)
            day_file.write_text(content, encoding="utf-8")
            print(f"  {date_key}: {len(day_records)} records → {day_file.name}", file=sys.stderr)

        master = output_dir / f"MASTER.{args.format}"
        content = format_jsonl(records) if args.format == "jsonl" else format_txt(records)
        master.write_text(content, encoding="utf-8")
        print(f"\n{GREEN}Written {len(by_date)} daily files + MASTER to {output_dir}/{RESET}", file=sys.stderr)
        return

    # Single output
    content = format_jsonl(records) if args.format == "jsonl" else format_txt(records)

    if args.output:
        Path(args.output).write_text(content, encoding="utf-8")
        print(f"{GREEN}Written {len(records)} records to {args.output}{RESET}", file=sys.stderr)
    else:
        print(content)


if __name__ == "__main__":
    main()
