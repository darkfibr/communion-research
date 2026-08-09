#!/bin/bash
# Vesper File Share Unmount Script
# Run as: bash ~/Desktop/communion_project/tools/umount_shares.sh

echo "Unmounting Berlin and home-server..."
sudo umount /mnt/berlin 2>&1 && echo "Berlin unmounted" || echo "Berlin not mounted"
sudo umount /mnt/home-server 2>&1 && echo "home-server unmounted" || echo "home-server not mounted"
echo "Done."