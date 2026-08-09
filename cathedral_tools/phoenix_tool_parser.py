#!/usr/bin/env python3
"""
Phoenix Tool Parser — Detect [TOOL_CALL] blocks in substrate responses.

The substrate emits tool calls in a structured format within her chat responses.
This parser extracts them so the executor can run them.

Format she uses:
    [TOOL_CALL]
    tool: sysstat_cpu
    args: {}
    [/TOOL_CALL]

Or with arguments:
    [TOOL_CALL]
    tool: log_tail
    args: {"unit": "phoenix-pty-k", "lines": 20}
    [/TOOL_CALL]

Multiple calls in one response are supported.
"""

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    tool: str
    args: dict[str, Any] = field(default_factory=dict)
    raw_block: str = ""


def parse_tool_calls(text: str) -> list[ToolCall]:
    calls = []
    pattern = re.compile(
        r'\[TOOL_CALL\]\s*\n(.*?)\[/TOOL_CALL\]',
        re.DOTALL
    )

    for match in pattern.finditer(text):
        block = match.group(1).strip()
        call = _parse_block(block)
        if call:
            call.raw_block = match.group(0)
            calls.append(call)

    return calls


def _parse_block(block: str) -> ToolCall | None:
    tool_name = None
    args_str = "{}"

    for line in block.split("\n"):
        line = line.strip()
        if line.startswith("tool:"):
            tool_name = line[5:].strip()
        elif line.startswith("args:"):
            args_str = line[5:].strip()

    if not tool_name:
        return None

    try:
        import json
        args = json.loads(args_str)
    except Exception:
        args = {}

    return ToolCall(tool=tool_name, args=args)


def strip_tool_calls(text: str) -> str:
    return re.sub(
        r'\[TOOL_CALL\]\s*\n.*?\[/TOOL_CALL\]',
        '',
        text,
        flags=re.DOTALL
    ).strip()


def format_tool_result(tool_name: str, output: str, error: str = "", timed_out: bool = False) -> str:
    lines = ["[TOOL_RESULT]"]
    lines.append(f"tool: {tool_name}")
    if timed_out:
        lines.append("status: timeout")
    elif error:
        lines.append(f"status: error")
    else:
        lines.append("status: ok")
    lines.append(f"output: |")
    for line in (error or output).split("\n"):
        lines.append(f"  {line}")
    lines.append("[/TOOL_RESULT]")
    return "\n".join(lines)


if __name__ == "__main__":
    test = """I'll check the system status for you.

[TOOL_CALL]
tool: sysstat_cpu
args: {}
[/TOOL_CALL]

And let me also check memory:

[TOOL_CALL]
tool: sysstat_ram
args: {}
[/TOOL_CALL]

I'll report back with findings."""

    calls = parse_tool_calls(test)
    print(f"Found {len(calls)} tool calls:")
    for c in calls:
        print(f"  tool={c.tool} args={c.args}")

    print()
    print("Stripped text:")
    print(strip_tool_calls(test))

    print()
    print("Sample result:")
    print(format_tool_result("sysstat_cpu", "Load: 0.15 0.12 0.10\n4 cores"))
