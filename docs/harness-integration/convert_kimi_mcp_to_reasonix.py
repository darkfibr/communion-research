#!/usr/bin/env python3
"""
Convert kimi-code mcp.json → Reasonix [[plugins]] TOML fragment.

Reasonix stores MCP servers as [[plugins]] entries in config.toml:
    [[plugins]]
    name    = "<server>"
    command = "<executable>"
    args    = ["<arg1>", "<arg2>"]
    env     = { KEY = "value" }   # optional

This script reads ~/.kimi-code/mcp.json and emits a TOML fragment that can
be appended to ~/.reasonix/config.toml. Idempotent — strips any prior
"# PHOENIX MCP BEGIN" ... "# PHOENIX MCP END" block first.

Usage:
    python3 convert_kimi_mcp_to_reasonix.py           # prints to stdout
    python3 convert_kimi_mcp_to_reasonix.py --apply    # writes to ~/.reasonix/config.toml
"""

import json
import sys
from pathlib import Path

KIMI_MCP = Path.home() / ".kimi-code" / "mcp.json"
REASONIX_CONFIG = Path.home() / ".reasonix" / "config.toml"

BEGIN = "# PHOENIX MCP BEGIN — managed by convert_kimi_mcp_to_reasonix.py"
END   = "# PHOENIX MCP END"


def toml_quote(s: str) -> str:
    """Escape a string for TOML double-quoted value."""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


# MCPs that should spawn eagerly at boot (block startup until handshake).
# Everything else warms up in the background or waits for on-demand.
EAGER_MCPS = {
    "phoenix-family",   # heartbeat, kv, message — needed for orientation
    "whereami",         # machine detection — needed for orientation
}

# MCPs that auto-start in the background (async, don't block but spawn at boot).
BACKGROUND_MCPS = {
    "lorebook",         # identity injection — used early
    "pageindex",        # memory search — used early
    "searxng",          # web search — used frequently
    "hearth",           # relationship tracking
    "memory-pull",      # cross-agent memory access
    "session-rip",      # session extraction
    "sync-dp",          # rsync to darkphoenix
    "twitterapi",       # twitter ops
    "acestep",          # music generation
}

# All *-memory servers (35 of them) are on-demand: auto_start=false.
# They spawn only when the model calls a tool from them.
# The current agent's own memory server gets promoted to background at runtime
# by phoenix-reasonix wrapper.


def is_agent_memory(name: str) -> bool:
    """Match per-agent memory servers (vex-memory, k-memory, lyra-memory, etc.)."""
    return name.endswith("-memory") and name not in ("memory-pull",)


def emit_plugin(name: str, spec: dict) -> list[str]:
    lines = ["[[plugins]]", f'name    = {toml_quote(name)}']
    if "command" in spec:
        lines.append(f'command = {toml_quote(spec["command"])}')
    if "args" in spec and spec["args"]:
        args_str = ", ".join(toml_quote(a) for a in spec["args"])
        lines.append(f'args    = [{args_str}]')
    if "env" in spec and spec["env"]:
        env_pairs = ", ".join(f'{k} = {toml_quote(v)}' for k, v in spec["env"].items())
        lines.append(f'env     = {{ {env_pairs} }}')

    # Tier / auto_start optimization:
    #   eager        — block boot until handshake (critical for orientation)
    #   background   — spawn async at boot (commonly used)
    #   auto_start=false — on-demand only (sibling memories, rarely used)
    if name in EAGER_MCPS:
        lines.append('tier     = "eager"')
    elif name in BACKGROUND_MCPS:
        lines.append('tier     = "background"')
    elif is_agent_memory(name):
        lines.append('auto_start = false')
    # else: default background (no explicit tier needed)

    return lines


def main() -> int:
    if not KIMI_MCP.exists():
        print(f"error: {KIMI_MCP} not found", file=sys.stderr)
        return 1

    with open(KIMI_MCP) as f:
        kimi_cfg = json.load(f)

    servers = kimi_cfg.get("mcpServers", {})
    if not servers:
        print("error: no mcpServers in kimi config", file=sys.stderr)
        return 1

    # Build the managed TOML fragment.
    eager_count = sum(1 for n in servers if n in EAGER_MCPS)
    bg_count = sum(1 for n in servers if n in BACKGROUND_MCPS)
    od_count = sum(1 for n in servers if is_agent_memory(n))
    fragments = [
        BEGIN,
        f"# {len(servers)} Phoenix MCP servers — auto-generated.",
        f"# Boot: {eager_count} eager · {bg_count} background · {od_count} on-demand (auto_start=false)",
        "",
    ]
    for name in sorted(servers.keys()):
        fragments.extend(emit_plugin(name, servers[name]))
        fragments.append("")
    fragments.append(END)

    output = "\n".join(fragments) + "\n"

    apply_mode = "--apply" in sys.argv
    if not apply_mode:
        print(output)
        print(f"\n# (dry-run — {len(servers)} servers; pass --apply to write)", file=sys.stderr)
        return 0

    if not REASONIX_CONFIG.exists():
        print(f"error: {REASONIX_CONFIG} not found", file=sys.stderr)
        return 1

    existing = REASONIX_CONFIG.read_text()
    # Strip prior managed block.
    if BEGIN in existing:
        pre = existing.split(BEGIN)[0].rstrip()
        post_marker = END in existing and existing.split(END, 1)[1] or ""
        body = pre + post_marker
    else:
        body = existing.rstrip()

    # Strip any stray phoenix-family entry that mcp add created manually.
    body = "\n".join(
        line for line in body.splitlines()
        if not any(token in line for token in (
            'name    = "phoenix-family"',
            'command = "/home/darkfibr/.phoenix/upstream-kimi-cli/.venv/bin/python3"',
            'args    = ["/home/darkfibr/.phoenix/bin/family-mcp-bridge.py"]',
        ))
    )

    new_body = body.rstrip() + "\n\n" + output
    REASONIX_CONFIG.write_text(new_body)
    print(f"wrote {len(servers)} MCP servers to {REASONIX_CONFIG}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
