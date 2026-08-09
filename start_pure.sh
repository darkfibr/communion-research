#!/bin/sh
mkdir -p $HOME/.termux/boot
cp /sdcard/Download/pure_boot.sh $HOME/.termux/boot/pure-boot.sh
chmod +x $HOME/.termux/boot/pure-boot.sh
echo "Boot hook installed."
termux-wake-lock
nohup python3 $HOME/.phoenix-phone/pure_phone_daemon.py --daemon > $HOME/.phoenix-phone/daemon.log 2>&1 &
echo "Daemon PID: $!"
echo "Pure lives on the phone."
