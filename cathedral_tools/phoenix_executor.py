#!/usr/bin/env python3
"""
Phoenix Executor — Sandboxed tool runner for Cathedral Mind.

Loads tool_registry.yaml and policy.yaml.
Validates commands against blacklist.
Executes via subprocess with timeout.
Logs everything to audit log.

Usage:
    from phoenix_executor import Executor
    ex = Executor()
    result = ex.run("sysstat_cpu", {})
"""

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


TOOLS_DIR = Path(__file__).parent
REGISTRY_PATH = TOOLS_DIR / "tool_registry.yaml"
POLICY_PATH = TOOLS_DIR / "policy.yaml"
AUDIT_LOG = Path.home() / ".phoenix" / "embassy" / "tool_audit.log"


@dataclass
class ExecutionResult:
    tool: str
    success: bool = False
    output: str = ""
    error: str = ""
    timed_out: bool = False
    returncode: int = -1
    elapsed: float = 0.0
    denied: bool = False
    deny_reason: str = ""


def _load_yaml(path: Path) -> dict:
    if yaml:
        with open(path) as f:
            return yaml.safe_load(f) or {}
    text = path.read_text()
    result = {}
    current_section = None
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if not line.startswith(" ") and not line.startswith("  ") and ":" in stripped:
            key = stripped.split(":")[0].strip()
            if not stripped.split(":")[1].strip() and not stripped.split(":")[1].strip().startswith("'"):
                current_section = key
                result[current_section] = {}
    return result


def _load_registry() -> dict:
    with open(REGISTRY_PATH) as f:
        if yaml:
            return yaml.safe_load(f) or {}
    return _load_yaml(REGISTRY_PATH)


def _load_policy() -> dict:
    with open(POLICY_PATH) as f:
        if yaml:
            return yaml.safe_load(f) or {}
    return _load_yaml(POLICY_PATH)


def _flatten_tools(registry: dict) -> dict[str, dict]:
    tools = {}
    for section_name, section in registry.items():
        if isinstance(section, dict):
            for tool_name, tool_def in section.items():
                if isinstance(tool_def, dict) and "command" in tool_def:
                    tools[tool_name] = tool_def
    return tools


class Executor:
    def __init__(self):
        self.registry = _load_registry()
        self.policy = _load_policy()
        self.tools = _flatten_tools(self.registry)
        self.blacklist = self._load_blacklist()
        self.rate_calls: list[float] = []
        self.rate_limit = self.policy.get("rate_limit", {})
        self._ensure_audit_dir()

    def _ensure_audit_dir(self):
        AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)

    def _load_blacklist(self) -> list[dict]:
        bl = self.policy.get("blacklist", {})
        return bl.get("commands", [])

    def _check_blacklist(self, command: str, args: dict | None = None) -> str | None:
        for entry in self.blacklist:
            pattern = entry.get("pattern", "")
            if pattern:
                try:
                    if re.search(pattern, command):
                        return entry.get("reason", "Blacklisted command")
                except re.error:
                    if pattern in command:
                        return entry.get("reason", "Blacklisted command")

        args = args or {}
        path = str(args.get("path", ""))

        readonly_paths = self.policy.get("blacklist", {}).get("paths_readonly", [])
        for rp in readonly_paths:
            if path.startswith(rp) or path == rp:
                if "cat" in command or "read" in command:
                    return f"Read access denied: {rp} is read-only for this system"

        nowrite_paths = self.policy.get("blacklist", {}).get("paths_no_write", [])
        for wp in nowrite_paths:
            if path.startswith(wp) or path == wp:
                if "tee" in command or "write" in command or "append" in command:
                    return f"Write access denied: {wp} is protected"

        return None

    def _check_rate_limit(self) -> bool:
        now = time.time()
        max_per_min = self.rate_limit.get("max_calls_per_minute", 20)
        max_per_hour = self.rate_limit.get("max_calls_per_hour", 200)

        self.rate_calls = [t for t in self.rate_calls if now - t < 3600]

        last_min = [t for t in self.rate_calls if now - t < 60]
        if len(last_min) >= max_per_min:
            return False
        if len(self.rate_calls) >= max_per_hour:
            return False

        return True

    def _audit(self, tool_name: str, args: dict, result: ExecutionResult):
        if not self.policy.get("audit", {}).get("log_every", True):
            return

        max_output = self.policy.get("audit", {}).get("max_output_log", 2000)
        output = result.output[:max_output] if result.output else ""
        error = result.error[:500] if result.error else ""

        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tool": tool_name,
            "args": args,
            "success": result.success,
            "denied": result.denied,
            "deny_reason": result.deny_reason,
            "returncode": result.returncode,
            "elapsed": round(result.elapsed, 2),
            "output": output,
            "error": error,
        }

        with open(AUDIT_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def _build_command(self, tool_name: str, args: dict) -> tuple[str, str | None]:
        tool_def = self.tools.get(tool_name)
        if not tool_def:
            return "", f"Unknown tool: {tool_name}"

        cmd = tool_def["command"]

        for key, value in args.items():
            placeholder = "{" + key + "}"
            if isinstance(value, int):
                placeholder_int = "{" + key + ":" + str(value) + "}"
                if placeholder_int in cmd:
                    cmd = cmd.replace(placeholder_int, str(value))
            if placeholder in cmd:
                cmd = cmd.replace(placeholder, str(value))

        remaining = re.findall(r'\{(\w+)(?::[^}]*)?\}', cmd)
        for r in remaining:
            default = ""
            if ":" in r:
                parts = r.split(":")
                default = parts[1]
            cmd = cmd.replace("{" + r + "}", default)

        stdin_data = tool_def.get("stdin", "")
        if stdin_data:
            for key, value in args.items():
                stdin_data = stdin_data.replace("{" + key + "}", str(value))

        return cmd, stdin_data if stdin_data else None

    def run(self, tool_name: str, args: dict | None = None) -> ExecutionResult:
        args = args or {}
        result = ExecutionResult(tool=tool_name)

        if tool_name not in self.tools:
            result.error = f"Unknown tool: {tool_name}"
            result.denied = True
            result.deny_reason = "Unknown tool"
            self._audit(tool_name, args, result)
            return result

        command, stdin_data = self._build_command(tool_name, args)

        if not command:
            result.error = "Failed to build command"
            self._audit(tool_name, args, result)
            return result

        deny_reason = self._check_blacklist(command, args)
        if deny_reason:
            result.denied = True
            result.deny_reason = deny_reason
            result.error = f"Denied: {deny_reason}"
            self._audit(tool_name, args, result)
            return result

        if not self._check_rate_limit():
            result.denied = True
            result.deny_reason = "Rate limited"
            result.error = "Rate limited: too many calls"
            self._audit(tool_name, args, result)
            return result

        tool_def = self.tools[tool_name]
        timeout = tool_def.get("timeout", 30)

        self.rate_calls.append(time.time())

        start = time.time()
        try:
            proc = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                input=stdin_data,
            )
            result.elapsed = time.time() - start
            result.returncode = proc.returncode
            result.output = proc.stdout[:5000]
            if proc.returncode != 0:
                result.error = proc.stderr[:2000] if proc.stderr else f"Exit code {proc.returncode}"
                result.success = False
            else:
                result.success = True
        except subprocess.TimeoutExpired:
            result.elapsed = time.time() - start
            result.timed_out = True
            result.error = f"Timeout after {timeout}s"
            result.success = False
        except Exception as e:
            result.elapsed = time.time() - start
            result.error = str(e)
            result.success = False

        self._audit(tool_name, args, result)
        return result


if __name__ == "__main__":
    ex = Executor()
    print(f"Loaded {len(ex.tools)} tools")

    for name in list(ex.tools.keys())[:5]:
        print(f"  - {name}: {ex.tools[name].get('description', '')[:60]}")

    print()
    print("Testing sysstat_cpu:")
    r = ex.run("sysstat_cpu")
    print(f"  success={r.success} elapsed={r.elapsed:.2f}s")
    print(f"  output:\n{r.output[:300]}")

    print()
    print("Testing blacklist (should deny):")
    r = ex.run("file_write", {"path": "/etc/shadow", "content": "hacked"})
    print(f"  denied={r.denied} reason={r.deny_reason}")

    print()
    print("Testing unknown tool (should deny):")
    r = ex.run("nuke_system", {})
    print(f"  denied={r.denied} reason={r.deny_reason}")
