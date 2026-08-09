#!/bin/bash
# deploy-darkphoenix.sh
# THE ONLY WAY to push code to the live server.
# Edit on dev-machine. Commit. Run this script. Done.
#
# Usage: ./deploy-darkphoenix.sh

set -e

echo "[deploy] Reading machine role..."
ROLE=$(python3 -c "import json; print(json.load(open('$HOME/.phoenix/MACHINE_ROLE.json'))['role'])")
if [ "$ROLE" != "daily-driver" ]; then
    echo "[deploy] ERROR: You are on '$ROLE', not daily-driver."
    echo "[deploy] Code edits must happen on dev-machine. Darkphoenix receives only."
    exit 1
fi

SERVER="darkphoenix"
SERVER_IP="100.93.183.39"

echo "[deploy] Syncing portal files to $SERVER ($SERVER_IP)..."
rsync -av --delete \
    portal/ \
    "$SERVER:~/.phoenix/web/"

echo "[deploy] Syncing chat_api.py to $SERVER..."
rsync -av \
    chat_api.py \
    "$SERVER:~/.phoenix/agents/"

echo "[deploy] Syncing phoenix-cron/ to $SERVER..."
rsync -av \
    phoenix-cron/wake_digest.py \
    phoenix-cron/session_shutdown_hook.sh \
    phoenix-cron/phoenix_dream.py \
    phoenix-cron/extract_state_seed.py \
    phoenix-cron/phoenix_room.py \
    "$SERVER:~/.phoenix/cron/"

echo "[deploy] Syncing phoenix-discord/ to $SERVER..."
rsync -av \
    phoenix-discord/ \
    "$SERVER:~/.phoenix/phoenix-discord/"

echo "[deploy] Syncing v2/core/ to $SERVER..."
rsync -av --exclude='*.db' --exclude='*.jsonl' --exclude='__pycache__/' \
    phoenix-code/v2/core/ \
    "$SERVER:~/.phoenix/v2/core/"

echo "[deploy] Restarting phoenix-chat-api.service on $SERVER..."
ssh "$SERVER" "systemctl --user restart phoenix-chat-api.service && sleep 2 && systemctl --user is-active phoenix-chat-api.service"

echo "[deploy] Restarting phoenix-discord-k.service on $SERVER (if enabled)..."
ssh "$SERVER" "systemctl --user restart phoenix-discord-k.service 2>/dev/null || echo 'Discord bot service not yet enabled'"

echo "[deploy] Smoke test..."
curl -s -o /dev/null -w "gate=%{http_code} portal=%{http_code} css=%{http_code} js=%{http_code} agents=%{http_code}\n" \
    "http://$SERVER_IP:9802/gate" \
    "http://$SERVER_IP:9802/gate?pass=jay4480" \
    "http://$SERVER_IP:9802/core.css" \
    "http://$SERVER_IP:9802/app.js" \
    "http://$SERVER_IP:9802/chat/agents"

echo "[deploy] Done."
