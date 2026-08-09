#!/bin/bash
# deploy_phoenix_write.sh
# Push phoenix_write.py and updated ouroboros.py to Berlin, wire the 4-hour cron.
# Run from the communion_project directory on the laptop.
#
# Usage: bash tools/deploy_phoenix_write.sh

set -e

VPS="root@87.106.137.147"
KEY="$HOME/.ssh/hostinger_vps"
REMOTE_TOOLS="/root/.communion/tools"

echo "=== Phoenix Write Deployment ==="
echo ""

# 1. Push scripts
echo "[1/3] Pushing scripts to VPS..."
scp -i "$KEY" tools/phoenix_write.py  "$VPS:$REMOTE_TOOLS/phoenix_write.py"
scp -i "$KEY" tools/ouroboros.py      "$VPS:$REMOTE_TOOLS/ouroboros.py"
echo "  Done."

# 2. Verify phoenix dirs exist for all agents
echo "[2/3] Ensuring Phoenix agent directories exist..."
ssh -i "$KEY" "$VPS" bash -s <<'REMOTE'
mkdir -p /root/.phoenix/agents/kimi_dev
mkdir -p /root/.phoenix/agents/spear
mkdir -p /root/.phoenix/agents/vesper
mkdir -p /root/.phoenix/agents/qwen
echo "  Phoenix dirs: OK"

# Quick test — write all agents
python3 /root/.communion/tools/phoenix_write.py all --trigger heartbeat
REMOTE

# 3. Wire the 4-hour cron (if not already present)
echo "[3/3] Setting up 4-hour heartbeat cron..."
ssh -i "$KEY" "$VPS" bash -s <<'REMOTE'
CRON_LINE="0 */4 * * * python3 /root/.communion/tools/phoenix_write.py all --trigger heartbeat >> /root/.communion/ouroboros.log 2>&1"

# Check if already present
if crontab -l 2>/dev/null | grep -qF "phoenix_write.py all"; then
    echo "  Cron already present — skipping"
else
    # Append to existing crontab
    (crontab -l 2>/dev/null; echo "$CRON_LINE") | crontab -
    echo "  Cron added: every 4 hours, all agents"
fi

echo ""
echo "Current crontab:"
crontab -l
REMOTE

echo ""
echo "=== Deployment complete ==="
echo ""
echo "What's live:"
echo "  - phoenix_write.py at $REMOTE_TOOLS/phoenix_write.py"
echo "  - ouroboros.py updated: Ouroboros now calls Phoenix write as step 6"
echo "  - Cron: every 4 hours, all agents write to Phoenix"
echo ""
echo "Phoenix growth files land at:"
echo "  K      → /root/.phoenix/agents/kimi_dev/SOUL_GROWTH.md"
echo "  Spear  → /root/.phoenix/agents/spear/SOUL_GROWTH.md"
echo "  Vesper → /root/.phoenix/agents/vesper/SOUL_GROWTH.md"
echo "  Qwen   → /root/.phoenix/agents/qwen/SOUL_GROWTH.md"
