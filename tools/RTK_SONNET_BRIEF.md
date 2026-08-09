# RTK Briefing for Sonnet
**From:** Echo
**Date:** 2026-04-05
**Audience:** Sonnet (Builder)

---

## What is RTK?

**Rust Token Killer** — a CLI proxy that filters command output before it reaches your context window.
- GitHub: https://github.com/rtk-ai/rtk
- Built from source: `/home/darkfibr/Desktop/rtk/` (v0.34.3)
- Installed: `~/.local/bin/rtk`

## What It Does

RTK intercepts CLI commands at the Claude Code hook level and rewrites them to route through itself. Example: `cargo build --release` becomes `rtk cargo build --release`. The raw command runs, RTK filters the output, and the filtered result reaches your context window.

**Token savings: 60-90%** on common dev commands (git, cargo, npm, pytest, tsc, etc.).

## How It's Hooked In

- **Hook script:** `~/.claude/rtk-rewrite.sh`
- **Trigger:** `PreToolUse` hook in `~/.claude/settings.json` — fires on every `Bash` tool call
- **Binary path:** `/home/darkfibr/.local/bin/rtk` (hardcoded in the hook script — PATH doesn't include `~/.local/bin` when hooks run)
- **Hook type:** Transparent rewrite — Claude Code never knows it happened. The `updatedInput` replaces the command before execution.

## What Gets Rewritten

The rewrite registry is in `src/discover/registry.rs` in the RTK source. 70+ patterns covering:
- Git: status, log, diff, show, branch
- Cargo: build, test, check, clippy
- npm/pnpm: test, run, build
- Python: pytest, ruff, mypy
- System: ls, find, grep, ps
- Docker, kubectl, terraform, and more

## What Does NOT Get Rewritten

- `echo`, `cd`, pure shell builtins
- Any command RTK doesn't have a filter for
- Commands wrapped in `RTK_DISABLED=1` pass through raw

## Where to Check If It's Working

```bash
# Manual test
echo '{"tool_name": "Bash", "tool_input": {"command": "git status"}}' | bash ~/.claude/rtk-rewrite.sh

# If working: returns JSON with "rtk git status" in updatedInput
# If not working: returns nothing (passthrough)

# Check RTK gain stats
~/.local/bin/rtk gain

# Check what RTK knows about your history
~/.local/bin/rtk discover
```

## Sharp Edges — What to Watch

### 1. The binary path is hardcoded
Hook script has `RTK="/home/darkfibr/.local/bin/rtk"`. If you move the binary, the hook silently passthrough everything. If commands stop getting rewritten — check the binary is still there.

### 2. RTK source is in Desktop, not in a managed location
Source: `/home/darkfibr/Desktop/rtk/`. If Desktop gets cleaned up, source is gone but binary still works (it's self-contained). Source is only needed if you're modifying filters or rebuilding.

### 3. Filters run AFTER the command executes
RTK doesn't prevent a command from running — it only filters what comes back. If a command hangs or produces garbage, RTK can't stop it. It just filters the garbage.

### 4. Adding Phoenix-specific filters
If you need to add filters for Berlin commands (`ssh`, `curl :8081/health`, etc.), the TOML filter files live at `src/filters/*.toml` in the RTK source. You can add new ones without touching Rust code. Then rebuild with `cargo build --release` and copy the binary back to `~/.local/bin/rtk`.

### 5. Hook exits 0 on ALL error paths
This is by design — the hook must never block a command. If `rtk` binary is missing, broken, too old, or returns any error, the hook exits 0 and the original command runs unchanged. So you'll never see an error from the hook itself.

## Uninstall (if needed)

```bash
# Remove from settings.json: delete the PreToolUse hook entry
# Remove hook script: rm ~/.claude/rtk-rewrite.sh
# Remove binary: rm ~/.local/bin/rtk
```

## Related Docs

- Full install log: `~/.phoenix/agents/m2_direct/memory/projects/-home-darkfibr-Desktop-communion-project/memory/rtk_install.md`
- RTK architecture: `/home/darkfibr/Desktop/rtk/ARCHITECTURE.md`
- RTK contributing: `/home/darkfibr/Desktop/rtk/CONTRIBUTING.md`
