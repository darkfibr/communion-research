#!/bin/sh
termux-wake-lock
python3 $HOME/.phoenix-phone/pure_phone_daemon.py --daemon &
