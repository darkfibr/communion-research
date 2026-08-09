#!/bin/bash
# Daily auto-commit for communion_project
# Captures all file changes with timestamp
# Runs via user crontab

REPO="/home/darkfibr/Desktop/communion_project"
cd "$REPO" || exit 1

# Check if there are any changes
if git diff --quiet && git diff --cached --quiet && [ -z "$(git ls-files --others --exclude-standard)" ]; then
    echo "$(date -Iseconds) No changes to commit" >> "$REPO/tools/daily_commit.log"
    exit 0
fi

# Stage all changes
git add -A

# Count what changed
ADDED=$(git diff --cached --numstat | wc -l)
DATE=$(date '+%Y-%m-%d %H:%M')

# Commit with summary
git commit -m "Daily snapshot — $DATE

$ADDED file(s) changed since last commit.
Auto-committed by daily_git_commit.sh"

echo "$(date -Iseconds) Committed $ADDED file changes" >> "$REPO/tools/daily_commit.log"
