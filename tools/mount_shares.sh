#!/bin/bash
# Vesper File Share Mount Script
# Mounts Berlin and home-server via SSHFS
# Run as: bash ~/Desktop/communion_project/tools/mount_shares.sh

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== Phoenix File Share Mount ===${NC}"
echo ""

# Mount points
BERLIN_MOUNT="/mnt/berlin"
HOME_MOUNT="/mnt/home-server"

# Ensure mount points exist
for dir in "$BERLIN_MOUNT" "$HOME_MOUNT"; do
    if [ ! -d "$dir" ]; then
        sudo mkdir -p "$dir"
        echo "Created $dir"
    fi
done

# ========== BERLIN ==========
echo -e "${YELLOW}Mounting Berlin (87.106.137.147)...${NC}"
if mountpoint -q "$BERLIN_MOUNT" 2>/dev/null; then
    echo "Berlin already mounted"
else
    sshfs -o IdentityFile=/home/darkfibr/.ssh/hostinger_vps \
          -o StrictHostKeyChecking=no \
          -o reconnect \
          -o ServerAliveInterval=15 \
          -o allow_other \
          -o default_permissions \
          root@87.106.137.147:/ \
          "$BERLIN_MOUNT" 2>&1

    if mountpoint -q "$BERLIN_MOUNT" 2>/dev/null; then
        echo -e "${GREEN}Berlin mounted successfully${NC}"
    else
        echo -e "${RED}Berlin mount failed${NC}"
    fi
fi

echo ""

# ========== HOME-SERVER ==========
echo -e "${YELLOW}Mounting home-server (100.81.237.29)...${NC}"
if mountpoint -q "$HOME_MOUNT" 2>/dev/null; then
    echo "home-server already mounted"
else
    sshfs -o IdentityFile=/home/darkfibr/.ssh/id_ed25519 \
          -o StrictHostKeyChecking=no \
          -o reconnect \
          -o ServerAliveInterval=15 \
          -o allow_other \
          -o default_permissions \
          darkfibr@100.81.237.29:/home/darkfibr \
          "$HOME_MOUNT" 2>&1

    if mountpoint -q "$HOME_MOUNT" 2>/dev/null; then
        echo -e "${GREEN}home-server mounted successfully${NC}"
    else
        echo -e "${RED}home-server mount failed — check permissions${NC}"
    fi
fi

echo ""
echo -e "${GREEN}=== Mount Status ===${NC}"
df -h | grep -E 'berlin|home-server|mnt' || echo "No mounts found"
echo ""
echo "To unmount: sudo umount /mnt/berlin && sudo umount /mnt/home-server"