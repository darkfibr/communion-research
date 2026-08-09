#!/usr/bin/env python3
"""
Phoenix Bridge Read v3 — Extract substrate responses from Google AI tab

v3: Grabs full DOM, finds content between last known phoenix message
    and "AI Mode response is ready". No more window slicing.

Usage:
    python3 phoenix_bridge_read.py [search_phrase]
"""
import asyncio
import json
import sys
import time
import urllib.request

try:
    import websockets
except ImportError:
    print("pip install websockets", file=sys.stderr)
    sys.exit(2)

CDP_URL = "http://localhost:9222"


def get_tabs() -> list[dict]:
    req = urllib.request.Request(f"{CDP_URL}/json/list")
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode())


def find_google_ai_tab(tabs: list[dict]) -> dict | None:
    for t in tabs:
        url = t.get("url", "")
        if "google.com/search" in url and "udm=50" in url:
            return t
    return None


async def fetch_full_page(ws_url: str) -> str:
    async with websockets.connect(ws_url) as ws:
        await ws.send(json.dumps({"id": 1, "method": "Runtime.enable"}))
        try:
            await asyncio.wait_for(ws.recv(), timeout=1)
        except asyncio.TimeoutError:
            pass

        script = """
(function(){
    return JSON.stringify(document.body.innerText);
})()
"""
        await ws.send(json.dumps({
            "id": 10,
            "method": "Runtime.evaluate",
            "params": {"expression": script, "returnByValue": True}
        }))

        for _ in range(10):
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=5)
                data = json.loads(msg)
                if data.get("id") == 10 and "result" in data:
                    val = data["result"].get("result", {}).get("value", '""')
                    return json.loads(val)
            except asyncio.TimeoutError:
                continue
    return ""


def extract_response(full_text: str, search_phrase: str = "") -> str:
    end_markers = ["AI Mode response is ready", "Suggested questions"]
    end_idx = len(full_text)
    for m in end_markers:
        idx = full_text.find(m)
        if idx != -1:
            end_idx = min(end_idx, idx)

    page = full_text[:end_idx]

    if search_phrase:
        snippet = search_phrase[:50]
        idx = page.rfind(snippet)
        if idx != -1:
            page = page[idx + len(snippet):]

    noise_markers = ["\nShow all\n", "\n5 sites\n", "\n7 sites\n"]
    for nm in noise_markers:
        idx = page.find(nm)
        if idx != -1:
            page = page[:idx]

    stop_lines = ["github.com", "darkfibr (DarkFibr)", "Show all", "sites"]
    lines = page.split("\n")
    clean = []
    for line in lines:
        s = line.strip()
        if any(s == stop for stop in stop_lines):
            break
        clean.append(s)

    text = "\n".join(clean).strip()
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    return text


async def main():
    search_phrase = sys.argv[1] if len(sys.argv) > 1 else ""
    if search_phrase:
        print(f"[read] Looking for: '{search_phrase[:60]}'", file=sys.stderr)

    print("[read] Discovering Google AI tab...", file=sys.stderr)
    tabs = get_tabs()
    ai_tab = find_google_ai_tab(tabs)
    if not ai_tab:
        print("[read] No Google AI tab found", file=sys.stderr)
        sys.exit(1)

    print(f"[read] Found: {ai_tab['title'][:60]}", file=sys.stderr)
    ws_url = ai_tab.get("webSocketDebuggerUrl")
    if not ws_url:
        print("[read] No WebSocket URL", file=sys.stderr)
        sys.exit(1)

    full_text = await fetch_full_page(ws_url)
    print(f"[read] Page: {len(full_text):,} chars", file=sys.stderr)

    if not full_text:
        print("[read] Empty page", file=sys.stderr)
        sys.exit(1)

    response = extract_response(full_text, search_phrase)

    print("-" * 60)
    print(response)
    print("-" * 60)
    sys.exit(0)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"\n[read] FATAL: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(2)
