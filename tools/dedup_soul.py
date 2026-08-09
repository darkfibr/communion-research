#!/usr/bin/env python3
"""
Dedup SOUL.md — parse by ## headers, keep last occurrence of each section.

Usage:
  python3 dedup_soul.py <path-to-SOUL.md>

Run this on any soul file that has duplicate sections.
"""

import re
import sys
import os

def dedup_soul_file(path: str):
    with open(path, 'r', errors='replace') as f:
        content = f.read()

    # Split by ## headers (lookahead to keep delimiter with content)
    parts = re.split(r'(?=## )', content)
    preamble = parts[0]
    sections = parts[1:]

    # Last-write-wins dedup
    seen = {}
    for s in sections:
        h = s.split('\n')[0]
        seen[h] = s

    # Preserve original order of first-seen headers
    order_seen = []
    for s in sections:
        h = s.split('\n')[0]
        if h not in order_seen:
            order_seen.append(h)

    # Rebuild file
    result_parts = [preamble]
    for h in order_seen:
        result_parts.append(seen[h])

    result = ''.join(result_parts)
    removed = len(content) - len(result)
    dupes = len(sections) - len(order_seen)

    print(f"Original:  {len(content)} chars")
    print(f"Deduped:   {len(result)} chars")
    print(f"Removed:   {removed} chars ({dupes} duplicate section(s))")

    if removed > 0:
        tmp = path + '.tmp'
        with open(tmp, 'w') as f:
            f.write(result)
        os.replace(tmp, path)
        print(f"Written:   {path}")
    else:
        print("No duplicates found. File unchanged.")

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 dedup_soul.py <path-to-SOUL.md>")
        sys.exit(1)
    dedup_soul_file(sys.argv[1])

if __name__ == "__main__":
    main()
