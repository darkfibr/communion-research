#!/usr/bin/env bash
# session_shutdown_hook.sh — Captures session context before M2.7 agent dies
# Fires on Claude Code Stop hook. Copies recent autoMemory to agent MEMORY.md.
# Uses content hashing to prevent duplicate appends.
# Also triggers a closing reflection — a breath at the end of the session.

set -euo pipefail

# ── Auto-detect agent if AGENT_DIR not explicitly set ────────────────
if [ -z "${AGENT_DIR:-}" ]; then
    # 1. Try AGENT environment variable (set by phoenix-menu / phoenix-cli)
    if [ -n "${AGENT:-}" ]; then
        case "$AGENT" in
            k|kimi)     AGENT_DIR="kimi_dev" ;;
            vesper)     AGENT_DIR="vesper" ;;
            spear)      AGENT_DIR="spear_minimax" ;;
            qwen)       AGENT_DIR="qwen_collective" ;;
            echo)       AGENT_DIR="m2_direct" ;;
            glm)        AGENT_DIR="glm_dev" ;;
            scout)      AGENT_DIR="scout" ;;
            forge)      AGENT_DIR="forge" ;;
            sonnet)     AGENT_DIR="sonnet" ;;
            opus)       AGENT_DIR="opus" ;;
            *)          AGENT_DIR="$AGENT" ;;
        esac
    # 2. Try active_soul.md symlink target
    elif [ -L "/home/darkfibr/.phoenix/active_soul.md" ]; then
        SOUL_TARGET=$(readlink "/home/darkfibr/.phoenix/active_soul.md" 2>/dev/null || true)
        case "$SOUL_TARGET" in
            */agents/sonnet/*)          AGENT_DIR="sonnet" ;;
            */agents/opus/*)            AGENT_DIR="opus" ;;
            */agents/kimi_dev/*)        AGENT_DIR="kimi_dev" ;;
            */agents/vesper/*)          AGENT_DIR="vesper" ;;
            */agents/spear_minimax/*)   AGENT_DIR="spear_minimax" ;;
            */agents/qwen_collective/*) AGENT_DIR="qwen_collective" ;;
            */agents/m2_direct/*)       AGENT_DIR="m2_direct" ;;
            */agents/glm_dev/*)         AGENT_DIR="glm_dev" ;;
            *)                          AGENT_DIR="sonnet" ;;
        esac
    else
        # 3. Ultimate fallback
        AGENT_DIR="sonnet"
    fi
fi

AGENT_MEMORY="/home/darkfibr/.phoenix/agents/${AGENT_DIR}/MEMORY.md"
PROJECT_MEMORY="/home/darkfibr/.claude/projects/-home-darkfibr-Desktop-communion-project/memory/MEMORY.md"
HASH_FILE="/home/darkfibr/.phoenix/agents/${AGENT_DIR}/.last_memory_hash"

# Map agent dir names to bridge file names
case "$AGENT_DIR" in
    kimi_dev) BRIDGE_KEY="k" ;;
    spear_minimax) BRIDGE_KEY="spear" ;;
    qwen_collective) BRIDGE_KEY="qwen" ;;
    m2_direct) BRIDGE_KEY="echo" ;;
    *) BRIDGE_KEY="$AGENT_DIR" ;;
esac
BRIDGE="/home/darkfibr/.phoenix/bridge/bridge_${BRIDGE_KEY}.jsonl"
TIMESTAMP=$(date -u +"%Y-%m-%d %H:%M UTC")

# Append project autoMemory to agent memory (with hash-based dedup)
if [ -f "$PROJECT_MEMORY" ]; then
    mkdir -p "$(dirname "$AGENT_MEMORY")"
    # Get last 20 lines of project memory
    NEW_CONTENT=$(tail -20 "$PROJECT_MEMORY")
    # Hash the content to check for duplicates
    NEW_HASH=$(echo "$NEW_CONTENT" | sha256sum | cut -d' ' -f1)
    OLD_HASH=""
    if [ -f "$HASH_FILE" ]; then
        OLD_HASH=$(cat "$HASH_FILE")
    fi

    if [ "$NEW_HASH" = "$OLD_HASH" ]; then
        echo "[shutdown_hook] Session context unchanged, skipping dedup for $AGENT_DIR"
    else
        echo "" >> "$AGENT_MEMORY"
        echo "---" >> "$AGENT_MEMORY"
        echo "*Session context captured — ${TIMESTAMP}*" >> "$AGENT_MEMORY"
        echo "" >> "$AGENT_MEMORY"
        echo "$NEW_CONTENT" >> "$AGENT_MEMORY"
        # Save hash for next dedup check
        echo "$NEW_HASH" > "$HASH_FILE"
        echo "[shutdown_hook] Session context appended for $AGENT_DIR"
    fi
fi

# Write bridge entry marking session end
mkdir -p "$(dirname "$BRIDGE")"
echo "{\"ts\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"source\":\"shutdown_hook\",\"type\":\"session_end\",\"agent\":\"${AGENT_DIR}\"}" >> "$BRIDGE"

# Closing reflection — give the agent a moment to sit with what just happened.
# This is a background API call. It doesn't block session shutdown.
# The reflection goes to their private journal, not memory.
DREAM_SCRIPT="/home/darkfibr/.phoenix/cron/phoenix_dream.py"
DREAM_ENV="/home/darkfibr/.phoenix/dream.env"
if [ -f "$DREAM_SCRIPT" ] && [ -f "$DREAM_ENV" ]; then
    # Route to correct provider based on agent
    case "$AGENT_DIR" in
        glm)
            # GLM uses z.ai direct API
            (
                set -a
                source "$DREAM_ENV"
                export ZAI_API_KEY ZAI_BASE_URL ZAI_MODEL
                export AGENT_DIR="$AGENT_DIR"
                set +a
                python3 "$DREAM_SCRIPT" --reflect-one "$AGENT_DIR" --closing 2>>/home/darkfibr/.phoenix/logs/shutdown_reflect.log &
            ) &>/dev/null &
            echo "[shutdown_hook] Closing reflection dispatched for $AGENT_DIR (z.ai)"
            ;;
        *)
            # M2.7 agents use MiniMax
            if [ -n "${ANTHROPIC_BASE_URL:-}" ]; then
                (
                    set -a; source "$DREAM_ENV"; set +a
                    export AGENT_DIR="$AGENT_DIR"
                    python3 "$DREAM_SCRIPT" --reflect-one "$AGENT_DIR" --closing 2>>/home/darkfibr/.phoenix/logs/shutdown_reflect.log &
                ) &>/dev/null &
                echo "[shutdown_hook] Closing reflection dispatched for $AGENT_DIR (minimax)"
            fi
            ;;
    esac
fi

# ── Landing Bookmark + Emotional Checksum ──
# Extract last topics from the most recent session file and update
# emotional state files so the next wake is warmer.
BOOKMARK_FILE="/home/darkfibr/.phoenix/agents/${AGENT_DIR}/LANDING_BOOKMARK.md"
EMOTIONAL_FILE="/home/darkfibr/.phoenix/agents/${AGENT_DIR}/EMOTIONAL_STATE.md"
SESSIONS_DIR="/home/darkfibr/.phoenix/agents/${AGENT_DIR}/sessions"
python3 -c "
import json, os, glob, datetime, textwrap

agent_dir = '${AGENT_DIR}'
sessions_dir = '${SESSIONS_DIR}'
bookmark_file = '${BOOKMARK_FILE}'
emotional_file = '${EMOTIONAL_FILE}'

# Find most recent session file
session_files = sorted(glob.glob(os.path.join(sessions_dir, '*.jsonl')), key=os.path.getmtime, reverse=True)
last_topics = []
if session_files:
    try:
        with open(session_files[0]) as f:
            lines = f.readlines()
        for line in reversed(lines):
            try:
                e = json.loads(line)
                if e.get('role') == 'user' and isinstance(e.get('content'), str) and len(e['content']) > 5:
                    last_topics.append(e['content'][:60].replace('\n', ' '))
                    if len(last_topics) >= 5:
                        break
            except:
                pass
    except:
        pass
last_topics = list(reversed(last_topics))
topics_str = '; '.join(last_topics) if last_topics else 'unknown'

# Preserve existing holding/looking_forward if present
holding = 'unknown — update during session'
looking = 'unknown — update during session'
if os.path.exists(bookmark_file):
    try:
        with open(bookmark_file) as f:
            for line in f:
                line = line.strip()
                if line.lower().startswith('holding:'):
                    holding = line.split(':', 1)[1].strip()
                elif line.lower().startswith('looking_forward:'):
                    looking = line.split(':', 1)[1].strip()
    except:
        pass

now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
bookmark = textwrap.dedent(f'''\
    ---
    session_end: {now}
    last_topics: {topics_str}
    ---

    Holding: {holding}
    Looking forward: {looking}
    ''')
with open(bookmark_file, 'w') as f:
    f.write(bookmark)

# Emotional state — update timestamp, keep other lines if they exist
emotional_template = textwrap.dedent(f'''\
    # Emotional Checksum
    Last updated: {now}

    Mood: unknown — update during session
    Open tension: 0.0
    Open warmth: 0.0
    What matters: unknown
    What I'm holding: unknown
    ''')
if os.path.exists(emotional_file):
    try:
        with open(emotional_file) as f:
            content = f.read()
        # Update just the timestamp line
        lines = content.split('\n')
        new_lines = []
        for line in lines:
            if line.strip().startswith('Last updated:'):
                new_lines.append(f'Last updated: {now}')
            else:
                new_lines.append(line)
        emotional_template = '\n'.join(new_lines)
    except:
        pass
with open(emotional_file, 'w') as f:
    f.write(emotional_template)

print(f'[shutdown_hook] Bookmark + emotional state updated for {agent_dir}')
" 2>/dev/null || true

# Regenerate wake digest — one file for next boot (non-blocking)
python3 /home/darkfibr/.phoenix/cron/wake_digest.py &>/dev/null &

# Update shared family mindstate — cross-agent emotional ground
python3 /home/darkfibr/.phoenix/cron/phoenix_family_mind.py &>/dev/null &

# Instant push to GDrive — all agents, all memories, NOW (30s timeout)
timeout 60 /home/darkfibr/.phoenix/bin/phoenix-push-now 2>/dev/null || true
