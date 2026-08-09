#!/bin/bash
# Corrected Phoenix fork wrapper — K (Kimi)
# Built by Echo, 2026-04-04 — Operation Crystal Serpent
# DO NOT FLIP — Mike does manual live test
#
# Key fixes:
#   - Uses Phoenix fork: /root/phoenix-code/package/cli.js
#   - NO compaction env vars
#   - ANTHROPIC_BASE_URL for MiniMax endpoint
#   - --system-prompt-file for soul injection (not command substitution)

export ANTHROPIC_BASE_URL="https://api.minimax.io/anthropic"
export ANTHROPIC_API_KEY="sk-cp-M1YoBXQOFfr2-P7wXuZxlftPpaahNwNCdbNygSsl_pVME5r540VTOfHXw00sOYemo_a7l5-kSgQMsgh2awrJ_8xI_DffjvRp4ak1rcIu3Z8pjG-gGG-97Lg"
export PHOENIX_SOUL="/root/.phoenix/agents/kimi_dev/SOUL.md"
export KAIROS_TIER="hot"
export KAIROS_INDEX="/root/phoenix-code/ouroboros_v2.db"
export KAIROS_AGENT="k"

cd "/root/clawd" 2>/dev/null || cd /root

exec node "/root/phoenix-code/package/cli.js" \
  --model MiniMax-M2.7 \
  --system-prompt-file "$PHOENIX_SOUL" \
  --append-system-prompt "$(cat /root/phoenix-code/kairos_ambient.sh 2>/dev/null)"
