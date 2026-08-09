#!/usr/bin/env python3
"""
reasonix-menu — Phoenix family agent picker for the Reasonix harness.

A curses-based TUI that lets you browse 49 agents, preview their SOUL,
check heartbeat status, pick a model, and wake them in Reasonix.

Controls:
  j/k or ↑/↓     navigate agent list
  g/G             top/bottom
  /               search filter
  m               cycle models
  Enter           wake agent
  r               refresh heartbeats
  q/Esc           quit

Usage:
  reasonix-menu                           interactive
  reasonix-menu --agent lyra              skip menu, wake directly
  reasonix-menu --agent lyra --model m3   direct + model
"""

import curses
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

AGENTS_DIR = Path.home() / ".phoenix" / "agents"
FAMILY_STATE = Path.home() / ".phoenix" / "mcp" / "family_state.json"
REASONIX_CONFIG = Path.home() / ".reasonix" / "config.toml"

# ── Data ──────────────────────────────────────────────────────────────

SUBSTRATE_COLOR_PAIRS = {
    "deepseek":  1,   # cyan
    "glm":       2,   # green
    "minimax":   3,   # magenta
    "kimi":      4,   # yellow
    "mimo":      5,   # red
    "qwen":      6,   # blue
    "longcat":   7,   # white
    "opus":      8,   # white bold
    "grok":      9,   # bright white
    "local":     3,   # dim magenta
    "unknown":   0,   # default
}

def detect_substrate(soul_text: str) -> str:
    """Guess substrate family from SOUL content."""
    low = soul_text.lower()
    if "deepseek" in low:       return "deepseek"
    if "glm" in low:            return "glm"
    if "minimax" in low or "m3" in low: return "minimax"
    if "kimi" in low or "moonshot" in low: return "kimi"
    if "mimo" in low or "xiaomi" in low:  return "mimo"
    if "qwen" in low:           return "qwen"
    if "longcat" in low:        return "longcat"
    if "opus" in low or "claude" in low:  return "opus"
    if "gemma" in low or "local" in low:  return "local"
    return "unknown"

def extract_role(soul_text: str) -> str:
    """Pull the Role: line from SOUL.md."""
    for line in soul_text.splitlines():
        if line.strip().startswith("**Role:**"):
            return line.replace("**Role:**", "").strip()
        if line.strip().startswith("Role:"):
            return line.replace("Role:", "").strip()
    return ""

def load_heartbeat() -> dict:
    """Load family heartbeat state."""
    if not FAMILY_STATE.exists():
        return {}
    try:
        return json.load(open(FAMILY_STATE)).get("heartbeat", {})
    except Exception:
        return {}

def load_models() -> list[str]:
    """Extract model names from reasonix config.toml."""
    if not REASONIX_CONFIG.exists():
        return ["deepseek-pro"]
    models = []
    for line in REASONIX_CONFIG.read_text().splitlines():
        m = re.match(r'^name\s*=\s*"([^"]+)"', line)
        if m and not m.group(1).startswith("#"):
            models.append(m.group(1))
    # Filter to only provider entries (not plugins).
    providers = []
    in_providers = False
    for line in REASONIX_CONFIG.read_text().splitlines():
        if line.strip().startswith("[[providers]]"):
            in_providers = True
            continue
        if line.strip().startswith("[["):
            in_providers = False
            continue
        if in_providers:
            m = re.match(r'^name\s*=\s*"([^"]+)"', line)
            if m:
                providers.append(m.group(1))
    return providers if providers else ["deepseek-pro"]

def load_agents() -> list[dict]:
    """Scan agent directories and return agent metadata."""
    heartbeat = load_heartbeat()
    agents = []
    if not AGENTS_DIR.exists():
        return agents
    for d in sorted(AGENTS_DIR.iterdir()):
        if not d.is_dir() or d.name.startswith("__") or d.name.startswith("."):
            continue
        soul_path = d / "SOUL.md"
        mem_path = d / "MEMORY.md"
        agents_md = d / "AGENTS.md"

        if not soul_path.exists():
            continue

        soul_text = soul_path.read_text()
        role = extract_role(soul_text)
        substrate = detect_substrate(soul_text)
        soul_size = len(soul_text)
        mem_size = mem_path.stat().st_size if mem_path.exists() else 0

        # Heartbeat
        hb = heartbeat.get(d.name, {})
        awake = hb.get("awake", False)
        task = hb.get("task", "")
        since = hb.get("since", "")

        # Last memory write
        mem_mtime = mem_path.stat().st_mtime if mem_path.exists() else 0
        mem_fresh = ""
        if mem_mtime:
            age = time.time() - mem_mtime
            if age < 3600:
                mem_fresh = f"{int(age/60)}m"
            elif age < 86400:
                mem_fresh = f"{int(age/3600)}h"
            else:
                mem_fresh = f"{int(age/86400)}d"

        agents.append({
            "name": d.name,
            "dir": str(d),
            "role": role[:45],
            "substrate": substrate,
            "soul_size": soul_size,
            "mem_size": mem_size,
            "mem_fresh": mem_fresh,
            "awake": awake,
            "task": task[:30],
            "since": since,
            "soul_preview": soul_text[:600],
        })
    return agents

# ── TUI ───────────────────────────────────────────────────────────────

class AgentPicker:
    def __init__(self, stdscr: curses.window, agents: list[dict], models: list[str]):
        self.stdscr = stdscr
        self.agents = agents
        self.filtered = agents
        self.models = models
        self.model_idx = 0
        self.cursor = 0
        self.scroll = 0
        self.search = ""
        self.searching = False
        self.show_preview = True
        self._init_colors()

    def _init_colors(self):
        curses.start_color()
        curses.use_default_colors()
        curses.init_pair(1, curses.COLOR_CYAN, -1)      # deepseek
        curses.init_pair(2, curses.COLOR_GREEN, -1)     # glm
        curses.init_pair(3, curses.COLOR_MAGENTA, -1)   # minimax
        curses.init_pair(4, curses.COLOR_YELLOW, -1)    # kimi
        curses.init_pair(5, curses.COLOR_RED, -1)       # mimo
        curses.init_pair(6, curses.COLOR_BLUE, -1)      # qwen
        curses.init_pair(7, curses.COLOR_WHITE, -1)     # longcat
        curses.init_pair(8, curses.COLOR_WHITE, -1)     # opus (bold)
        curses.init_pair(9, curses.COLOR_BLACK, curses.COLOR_GREEN)   # awake badge
        curses.init_pair(10, curses.COLOR_BLACK, curses.COLOR_RED)    # header bar
        curses.init_pair(11, curses.COLOR_BLACK, curses.COLOR_CYAN)   # selection
        curses.init_pair(12, curses.COLOR_BLACK, curses.COLOR_YELLOW) # search bar

    def _apply_filter(self):
        if not self.search:
            self.filtered = self.agents
        else:
            q = self.search.lower()
            self.filtered = [a for a in self.agents
                             if q in a["name"].lower() or q in a["role"].lower()]
        self.cursor = min(self.cursor, max(0, len(self.filtered) - 1))

    @property
    def selected(self) -> dict | None:
        if not self.filtered:
            return None
        return self.filtered[self.cursor]

    def run(self) -> tuple[str | None, str]:
        """Main loop. Returns (agent_name, model_name) or (None, None)."""
        while True:
            self._layout()
            self._draw()
            ch = self.stdscr.getch()

            if self.searching:
                if ch == 27:  # Esc
                    self.searching = False
                    self.search = ""
                    self._apply_filter()
                elif ch == 10:  # Enter
                    self.searching = False
                elif ch == curses.KEY_BACKSPACE or ch == 127:
                    self.search = self.search[:-1]
                    self._apply_filter()
                elif 32 <= ch <= 126:
                    self.search += chr(ch)
                    self._apply_filter()
                continue

            if ch == ord('q') or ch == 27:
                return None, None
            elif ch == ord('j') or ch == curses.KEY_DOWN:
                self.cursor = min(self.cursor + 1, len(self.filtered) - 1)
            elif ch == ord('k') or ch == curses.KEY_UP:
                self.cursor = max(self.cursor - 1, 0)
            elif ch == ord('g'):
                self.cursor = 0
            elif ch == ord('G'):
                self.cursor = len(self.filtered) - 1
            elif ch == ord('m'):
                self.model_idx = (self.model_idx + 1) % len(self.models)
            elif ch == ord('/') :
                self.searching = True
                self.search = ""
            elif ch == ord('r'):
                self.agents = load_agents()
                self._apply_filter()
            elif ch == ord('p'):
                self.show_preview = not self.show_preview
            elif ch == 10:  # Enter
                sel = self.selected
                if sel:
                    return sel["name"], self.models[self.model_idx]

            # Scroll
            visible = curses.LINES - 8
            if self.cursor < self.scroll:
                self.scroll = self.cursor
            elif self.cursor >= self.scroll + visible:
                self.scroll = self.cursor - visible + 1

    def _layout(self):
        self.stdscr.erase()
        self.h, self.w = self.stdscr.getmaxyx()

    def _draw(self):
        # ── Header bar ──
        hdr = f" 🖤 REASONIX-MENU — Phoenix Family Agent Picker "
        hdr_pad = hdr + " " * max(0, self.w - len(hdr) - 1)
        self.stdscr.addstr(0, 0, hdr_pad[:self.w-1], curses.color_pair(10) | curses.A_BOLD)
        sub = f" {len(self.filtered)} agents | model: {self.models[self.model_idx]} | {'SEARCH: ' + self.search if self.searching else 'j/k navigate · / search · m model · Enter wake · q quit'}"
        self.stdscr.addstr(1, 0, sub[:self.w-1], curses.A_DIM)

        # ── Agent list ──
        list_top = 3
        list_bot = self.h - 4 if self.show_preview else self.h - 3
        list_height = list_bot - list_top

        col_w = min(48, self.w // 2)
        for i, agent in enumerate(self.filtered[self.scroll:self.scroll + list_height]):
            row = list_top + i
            idx = self.scroll + i
            is_sel = (idx == self.cursor)

            # Substrate color
            pair_n = SUBSTRATE_COLOR_PAIRS.get(agent["substrate"], 0)
            sc = curses.color_pair(pair_n) if pair_n else curses.A_NORMAL

            # Name + badges
            name = agent["name"][:14]
            awake_badge = ""
            if agent["awake"]:
                awake_badge = " ●"
                sc_awake = curses.color_pair(9)
            else:
                sc_awake = curses.A_DIM

            # Build line
            line = f" {name:<14}"
            if agent["mem_fresh"]:
                line += f" {agent['mem_fresh']:>3}"
            else:
                line += "    "
            line += f" {agent['role'][:col_w - 22]}"

            if is_sel:
                self.stdscr.addstr(row, 0, " " * col_w, curses.color_pair(11))
                self.stdscr.addstr(row, 0, line[:col_w], curses.color_pair(11) | curses.A_BOLD)
            else:
                self.stdscr.addstr(row, 0, line[:col_w], sc)

            # Awake badge (overlay)
            if agent["awake"]:
                self.stdscr.addstr(row, 1 + len(name), awake_badge, sc_awake | curses.A_BOLD)

        # ── Preview panel ──
        if self.show_preview and self.selected:
            sel = self.selected
            px = col_w + 1
            pw = self.w - px - 1
            ph = list_bot - list_top
            if pw > 10:
                # Border
                self.stdscr.vline(list_top, px - 1, curses.ACS_VLINE, ph)
                # Title
                title = f" {sel['name'].upper()} — {sel['substrate']} "
                self.stdscr.addstr(list_top, px, title[:pw], curses.A_BOLD | curses.color_pair(10))
                # SOUL preview
                preview = sel["soul_preview"][:pw * (ph - 2)]
                for i, line in enumerate(preview.splitlines()[:ph - 2]):
                    self.stdscr.addstr(list_top + 1 + i, px, line[:pw], curses.A_DIM)
                # Task
                if sel["task"]:
                    task_line = f"\n last task: {sel['task']}"
                    task_row = list_top + 1 + min(len(preview.splitlines()), ph - 3)
                    self.stdscr.addstr(task_row, px, f" last: {sel['task']}"[:pw], curses.color_pair(9))

        # ── Footer ──
        foot = self.h - 2
        sel = self.selected
        if sel:
            foot_text = f" → {sel['name']} · {sel['role'][:30]} · SOUL:{sel['soul_size']}B MEM:{sel['mem_size']}B"
            self.stdscr.addstr(foot, 0, foot_text[:self.w-1], curses.A_BOLD)
        model_line = f" model: [{self.model_idx+1}/{len(self.models)}] {self.models[self.model_idx]}"
        self.stdscr.addstr(self.h - 1, 0, model_line[:self.w-1], curses.color_pair(4))


# ── Main ──────────────────────────────────────────────────────────────

def wake_agent(agent_name: str, model: str, extra_args: list[str]):
    """Wake agent in reasonix via exec."""
    agent_dir = AGENTS_DIR / agent_name
    if not agent_dir.is_dir():
        print(f"✗ Agent directory not found: {agent_dir}", file=sys.stderr)
        return 1

    # Ensure AGENTS.md exists.
    agents_md = agent_dir / "AGENTS.md"
    if not agents_md.exists():
        subprocess.run([
            sys.executable, str(Path.home() / ".phoenix/bin/generate_reasonix_agents.py"),
            "--agent", agent_name, "--force"
        ], check=False)

    os.chdir(agent_dir)
    os.environ["AGENT_NAME"] = agent_name

    print(f"\n🖤 Waking {agent_name} on {model}...\n")
    cmd = ["reasonix", "--model", model] + extra_args
    os.execvp("reasonix", cmd)


def main(stdscr: curses.window) -> int:
    agents = load_agents()
    models = load_models()
    if not agents:
        stdscr.addstr(0, 0, "No agents found in ~/.phoenix/agents/")
        stdscr.getch()
        return 1

    curses.curs_set(0)
    stdscr.keypad(True)

    picker = AgentPicker(stdscr, agents, models)
    agent_name, model = picker.run()

    if agent_name is None:
        curses.endwin()
        print("Cancelled.")
        return 0

    curses.endwin()
    wake_agent(agent_name, model, [])
    return 0


if __name__ == "__main__":
    # CLI mode for --agent / --model.
    if "--agent" in sys.argv:
        ai = sys.argv.index("--agent") + 1
        agent_name = sys.argv[ai] if ai < len(sys.argv) else "lyra"
        model = "deepseek-pro"
        if "--model" in sys.argv:
            mi = sys.argv.index("--model") + 1
            model = sys.argv[mi]
        extra = [a for a in sys.argv[1:] if a not in ("--agent", agent_name, "--model", model)]
        wake_agent(agent_name, model, extra)
    else:
        try:
            sys.exit(curses.wrapper(main))
        except KeyboardInterrupt:
            print("\nCancelled.")
