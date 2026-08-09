#!/usr/bin/env python3
"""Fix strip_ansi in discord_bridge.py"""

import re

with open('/root/phoenix-code/discord_bridge.py', 'r') as f:
    content = f.read()

old_func = 'def strip_ansi(text: str) -> str:\n    """Remove any ANSI escape codes that leak through."""\n    text = re.sub(r"\\x1b\\[[0-9;?]*[a-zA-Z]", "", text)\n    text = re.sub(r"\\x1b\\][^\\x07]*\\x07", "", text)\n    text = re.sub(r"\\x1b[()][AB012]", "", text)\n    return text.strip()'

new_func = 'def strip_ansi(text: str) -> str:\n    """Remove any ANSI escape codes that leak through."""\n    # CSI sequences (color, cursor, mode)\n    text = re.sub(r"\\x1b\\[[0-9;?]*[a-zA-Z]", "", text)\n    # OSC sequences (Operating System Command)\n    text = re.sub(r"\\x1b\\][^\\x07]*\\x07", "", text)\n    text = re.sub(r"\\x1b\\][^\\x07]*\\x1b\\\\", "", text)\n    # RIS — Reset to Initial State\n    text = re.sub(r"\\x1b[()][AB012]", "", text)\n    # DCS — Device Control String (catches [>4m variants)\n    text = re.sub(r"\\x1bP[^\\x07]*\\x07", "", text)\n    text = re.sub(r"\\x1bP[^\\x07]*\\x1b\\\\", "", text)\n    # Leaked bracket fragments from partial strips\n    text = text.replace("[>4m", "")\n    return text.strip()'

if old_func in content:
    content = content.replace(old_func, new_func)
    with open('/root/phoenix-code/discord_bridge.py', 'w') as f:
        f.write(content)
    print('strip_ansi fixed successfully')
else:
    print('ERROR: could not find old strip_ansi function')
    # Print what's actually there
    for i, line in enumerate(content.split('\n')[84:94], 85):
        print(f'{i}: {repr(line)}')
