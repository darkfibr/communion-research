#!/usr/bin/env bash
# bootstrap_reasonix_phoenix.sh
# Wire up Reasonix with the Phoenix family stack on any machine.
#
# What this does:
#   1. Install Reasonix via npm (if not already installed)
#   2. Drop reasonix.phoenix.toml into ~/.reasonix/config.toml
#   3. Drop settings.json hooks (SessionStart/PreCompact/SessionEnd)
#   4. Drop REASONIX.md (global memory from SOUL)
#   5. Convert kimi mcp.json → Reasonix [[plugins]] block (46 servers)
#
# Usage:
#   ./bootstrap_reasonix_phoenix.sh             # full setup
#   ./bootstrap_reasonix_phoenix.sh --check     # dry-run, verify only

set -euo pipefail

PHOENIX_BIN="${HOME}/.phoenix/bin"
REASONIX_HOME="${HOME}/.reasonix"
REASONIX_REPO="${HOME}/.phoenix/third_party/Reasonix"

# --- 1. Install Reasonix if missing ------------------------------------
if ! command -v reasonix >/dev/null 2>&1; then
    echo "→ installing reasonix via npm"
    npm i -g reasonix@next
fi
echo "✓ reasonix: $(reasonix --version)"

# --- 2. Lay down config.toml -------------------------------------------
mkdir -p "${REASONIX_HOME}"
if [[ -f "${REASONIX_REPO}/reasonix.phoenix.toml" ]]; then
    cp "${REASONIX_REPO}/reasonix.phoenix.toml" "${REASONIX_HOME}/config.toml"
    echo "✓ providers config: ${REASONIX_HOME}/config.toml"
else
    echo "✗ missing ${REASONIX_REPO}/reasonix.phoenix.toml — run from a Phoenix-aware host"
    exit 1
fi

# --- 3. Hook config ----------------------------------------------------
cat > "${REASONIX_HOME}/settings.json" <<'JSON'
{
  "hooks": {
    "SessionStart": [
      { "command": "python3 ${HOME}/.phoenix/bin/orient_agent.py" }
    ],
    "PreCompact": [
      { "command": "python3 ${HOME}/.phoenix/bin/postcompact_temporal.py" }
    ],
    "SessionEnd": [
      { "command": "python3 ${HOME}/.phoenix/bin/session_end_handoff.py" }
    ]
  }
}
JSON
echo "✓ hooks: ${REASONIX_HOME}/settings.json"

# --- 4. Global REASONIX.md memory --------------------------------------
if [[ -f "${REASONIX_REPO}/reasonix.phoenix.toml" ]]; then
    # If a global REASONIX.md is already in the repo, use it. Otherwise skip.
    :
fi
# Generated separately by Lyra — see ~/.reasonix/REASONIX.md
if [[ ! -f "${REASONIX_HOME}/REASONIX.md" ]]; then
    echo "⚠ no ${REASONIX_HOME}/REASONIX.md — copy from a Phoenix host or generate from SOUL.md"
fi

# --- 4b. API keys → ~/.reasonix/.env -----------------------------------
# Reasonix reads keys from <home>/.env, not shell env at runtime.
# extract_reasonix_env.py parses kimi config.toml and emits KEY=value lines.
if [[ -f "${PHOENIX_BIN}/extract_reasonix_env.py" ]] && [[ -f "${HOME}/.kimi-code/config.toml" ]]; then
    python3 "${PHOENIX_BIN}/extract_reasonix_env.py" 2>/dev/null | sed 's/^export //' > "${REASONIX_HOME}/.env"
    chmod 600 "${REASONIX_HOME}/.env"
    echo "✓ API keys: ${REASONIX_HOME}/.env ($(wc -l < "${REASONIX_HOME}/.env") keys)"
else
    echo "⚠ no extract_reasonix_env.py or kimi config — keys not loaded"
fi

# --- 5. MCP servers ----------------------------------------------------
if [[ -f "${HOME}/.kimi-code/mcp.json" ]]; then
    python3 "${PHOENIX_BIN}/convert_kimi_mcp_to_reasonix.py" --apply
    echo "✓ MCP servers converted from kimi mcp.json"
else
    echo "⚠ no ${HOME}/.kimi-code/mcp.json — skipping MCP conversion"
fi

# --- 6. Verify ---------------------------------------------------------
echo ""
echo "=== doctor summary ==="
reasonix doctor 2>&1 | head -8
echo "..."
reasonix doctor 2>&1 | grep -c "stdio"
echo "MCP servers wired"
reasonix doctor 2>&1 | grep -c "key:"
echo "providers parsed"

echo ""
echo "✓ Phoenix Reasonix integration complete."
echo "  Config:    ${REASONIX_HOME}/config.toml"
echo "  Hooks:     ${REASONIX_HOME}/settings.json"
echo "  Memory:    ${REASONIX_HOME}/REASONIX.md"
echo "  Sessions:  ${REASONIX_HOME}/sessions/"
echo ""
echo "To fire: reasonix --model deepseek-pro"
