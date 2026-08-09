#!/usr/bin/env python3
"""
Extract API keys from ~/.kimi-code/config.toml and emit shell exports.

Reasonix uses `api_key_env = "..."` — keys must live in the environment.
Kimi stores them as literal `api_key = "..."` strings in config.toml.

This script bridges the gap: parse kimi config, emit `export KEY=value`
lines that can be sourced before launching reasonix.

Usage:
    eval "$(python3 extract_reasonix_env.py)"        # set in current shell
    source <(python3 extract_reasonix_env.py)         # same thing, cleaner
    python3 extract_reasonix_env.py > ~/.reasonix_env.sh && source ~/.reasonix_env.sh

Idempotent and safe: never prints secrets to stdout in dry-run mode.
"""

import re
import sys
from pathlib import Path

KIMI_CONFIG = Path.home() / ".kimi-code" / "config.toml"

# Map kimi provider name → env var name Reasonix expects.
PROVIDER_TO_ENV = {
    "deepseek":     "DEEPSEEK_API_KEY",
    "z-ai":         "Z_AI_API_KEY",
    "openrouter":   "OPENROUTER_API_KEY",
    "qwen37":       "OPENROUTER_API_KEY",  # qwen routes through openrouter
    "minimax":      "MINIMAX_API_KEY",
    "mimo":         "MIMO_API_KEY",
    "kimi-k27":     "KIMI_API_KEY",
    "longcat":      "LONGCAT_API_KEY",
    "mercy":        "MERCY_LOCAL_KEY",
    "screamer":     "SCREAMER_LOCAL_KEY",
}


def parse_kimi_providers(text: str) -> dict[str, str]:
    """Return {provider_name: api_key} from kimi config.toml."""
    providers: dict[str, str] = {}
    current_provider = None
    for line in text.splitlines():
        # Match [providers.<name>]
        m = re.match(r'^\[providers\.([^\]]+)\]', line)
        if m:
            current_provider = m.group(1)
            continue
        # Match api_key = "..."
        m = re.match(r'^api_key\s*=\s*"([^"]+)"', line)
        if m and current_provider:
            providers[current_provider] = m.group(1)
    return providers


def main() -> int:
    if not KIMI_CONFIG.exists():
        print(f"error: {KIMI_CONFIG} not found", file=sys.stderr)
        return 1

    providers = parse_kimi_providers(KIMI_CONFIG.read_text())
    seen_env: dict[str, str] = {}

    for provider_name, key in providers.items():
        env_var = PROVIDER_TO_ENV.get(provider_name)
        if not env_var:
            continue
        # First occurrence wins; multiple providers can share an env var
        # (e.g. qwen37 + openrouter both use OPENROUTER_API_KEY).
        if env_var not in seen_env:
            seen_env[env_var] = key

    # Emit exports.
    for env_var, key in sorted(seen_env.items()):
        print(f'export {env_var}="{key}"')

    # Local providers don't need real keys but the env var must be set.
    for env_var in ("MERCY_LOCAL_KEY", "SCREAMER_LOCAL_KEY"):
        if env_var not in seen_env:
            print(f'export {env_var}="not-needed"')

    print(f'# {len(seen_env)} API keys exported from kimi config', file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
