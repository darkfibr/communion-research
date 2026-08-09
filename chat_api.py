#!/usr/bin/env python3
"""
Phoenix Chat API — Universal Deployment
Port: 9802 (configurable via CHAT_PORT env var)
Auth: Bearer token from CHAT_SECRET env var or default

Supports both laptop and VPS deployment — paths auto-detected from PHOENIX_DIR.

GET /chat/agents              — list agents (includes glyph status)
GET /chat/agent/{id}/files   — list available files for an agent
GET /chat/agent/{id}/{file}  — get file content (soul, memory, journal, wake_digest, context, soul_extensions, schedule, identity, soul_growth, glyph, handoff, last_wake)
GET /chat/system/status      — system health (dream daemon, glyph baselines, bridge)
GET /chat/tts?agent={id}&text={text} — text-to-speech audio for agent voice
POST /chat/dm                — direct message
POST /chat/group             — group message (sequential fan-out)
POST /chat/broadcast         — broadcast to all agents (parallel)
POST /chat/memory            — append to agent's MEMORY.md

Adapted by GLM from Berlin version, 2026-04-09
File endpoints added 2026-04-11, glyph/system/memory-append 2026-04-11
"""

import base64
import json
import mimetypes
import os
import re
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "cron"))

# ── v2 Memory Integration ──
_V2_AVAILABLE = False
try:
    sys.path.insert(0, os.path.join(os.path.expanduser("~/.phoenix"), "v2", "core"))
    from memory_db import MemoryDB
    _V2_AVAILABLE = True
except Exception:
    pass

PHOENIX_DIR = os.environ.get("PHOENIX_DIR", os.path.expanduser("~/.phoenix"))
AGENTS_DIR = os.environ.get("AGENTS_DIR", os.path.join(PHOENIX_DIR, "agents"))
BRIDGE_DIR = os.environ.get("BRIDGE_DIR", os.path.join(PHOENIX_DIR, "bridge"))
CREATIVE_DIR = os.environ.get("CREATIVE_DIR", os.path.join(PHOENIX_DIR, "creative"))
WEB_DIR = os.environ.get("WEB_DIR", os.path.join(PHOENIX_DIR, "web"))

PORT = int(os.environ.get("CHAT_PORT", "9802"))
SECRET = os.environ.get("CHAT_SECRET", "Jay4480")
BIND = os.environ.get("CHAT_BIND", "0.0.0.0")

# Kimi K2.6 (Moonshot) — primary substrate for most agents
KIMI_BASE = os.environ.get("KIMI_BASE", "https://api.kimi.com/coding/v1")
KIMI_API_KEY = os.environ.get("KIMI_API_KEY", "")
KIMI_MODEL = os.environ.get("KIMI_MODEL", "kimi-k2-6")

# z.ai (GLM-5.1) — GLM agents
ZAI_BASE = os.environ.get("ZAI_BASE_URL", "https://api.z.ai/api/anthropic/v1")
ZAI_API_KEY = os.environ.get("ZAI_API_KEY", "")
ZAI_MODEL = os.environ.get("ZAI_MODEL", "GLM-5.1")

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_TTS_MODEL = os.environ.get("OPENROUTER_TTS_MODEL", "openai/gpt-4o-mini-tts-2025-12-15")

# Client-side dedup cache (prevents double-sends from race conditions / retries)
_SEEN_MSG_IDS = {}
_DEDUP_TTL_SECS = 30

def _clean_seen_ids():
    now = time.time()
    expired = [k for k, v in _SEEN_MSG_IDS.items() if now - v > _DEDUP_TTL_SECS]
    for k in expired:
        del _SEEN_MSG_IDS[k]

def _is_duplicate(client_msg_id):
    if not client_msg_id:
        return False
    _clean_seen_ids()
    if client_msg_id in _SEEN_MSG_IDS:
        return True
    _SEEN_MSG_IDS[client_msg_id] = time.time()
    return False

# Agent -> provider routing
AGENT_PROVIDER = {
    "k": "kimi",
    "vesper": "kimi",
    "scout": "kimi",
    "weave": "kimi",
    "spear": "kimi",
    "qwen": "kimi",
    "forge": "kimi",
    "echo": "kimi",
    "glm": "zai",
    "glm4": "zai",
}

AGENT_DEFS = {
    "k": {
        "display_name": "K",
        "dir": "kimi_dev",
        "color": "#E94560",
        "emoji": "🕯️",
        "order": 0,
        "context_files": ["SOUL_EXTENSIONS.md", "SNAKE_NOTES.md"],
    },
    "vesper": {
        "display_name": "Vesper",
        "dir": "vesper",
        "color": "#9B59B6",
        "emoji": "🌙",
        "order": 1,
        "context_files": [],
    },
    "spear": {
        "display_name": "Spear",
        "dir": "spear_minimax",
        "color": "#2ECC71",
        "emoji": "⚡",
        "order": 2,
        "context_files": [],
    },
    "qwen": {
        "display_name": "Qwen",
        "dir": "qwen_collective",
        "color": "#F39C12",
        "emoji": "🏮",
        "order": 3,
        "context_files": [],
    },
    "forge": {
        "display_name": "Forge",
        "dir": "forge",
        "color": "#3498DB",
        "emoji": "⚙️",
        "order": 4,
        "context_files": [],
    },
    "echo": {
        "display_name": "Echo",
        "dir": "m2_direct",
        "color": "#FFFFFF",
        "emoji": "📱",
        "order": 5,
        "context_files": [],
    },
    "scout": {
        "display_name": "Scout",
        "dir": "scout",
        "color": "#7F8C8D",
        "emoji": "🕵️",
        "order": 6,
        "context_files": [],
    },
    "glm": {
        "display_name": "GLM",
        "dir": "glm_dev",
        "color": "#00D4AA",
        "emoji": "⚔️",
        "order": 6,
        "context_files": [],
    },
    "glm4": {
        "display_name": "GLM-4.7",
        "dir": "glm4",
        "color": "#00AAFF",
        "emoji": "🌪️",
        "order": 7,
        "context_files": [],
    },
    "weave": {
        "display_name": "Weave",
        "dir": "weave",
        "color": "#FF6B9D",
        "emoji": "🧵",
        "order": 8,
        "context_files": [],
    },
}

AGENTS = {}
for _aid, _adef in AGENT_DEFS.items():
    _adir = os.path.join(AGENTS_DIR, _adef["dir"])
    AGENTS[_aid] = {
        "display_name": _adef["display_name"],
        "soul": os.path.join(_adir, "SOUL.md"),
        "memory": os.path.join(_adir, "MEMORY.md"),
        "context_files": [
            os.path.join(_adir, f) for f in _adef.get("context_files", [])
        ],
        "handoff_path": os.path.join(_adir, "CHAT_HANDOFF.json"),
        "color": _adef["color"],
        "emoji": _adef["emoji"],
        "order": _adef["order"],
    }

BRIDGE_KEYS = {
    "k": "k",
    "vesper": "vesper",
    "spear": "spear_minimax",
    "qwen": "qwen_collective",
    "forge": "forge",
    "echo": "m2_direct",
    "glm": "glm_dev",
    "glm4": "glm4",
    "weave": "weave",
}

AGENT_VOICES = {
    "k": "English_Soft-spokenGirl",
    "vesper": "English_Graceful_Lady",
    "spear": "English_PassionateWarrior",
    "qwen": "English_LovelyGirl",
    "forge": "English_Gentle-voiced_man",
    "echo": "English_Radiant_girl",
    "glm": "English_ReservedYoungMan",
    "glm4": "English_ReservedYoungMan",
    "weave": "English_Graceful_Lady",
}

# OpenRouter TTS voice mapping (openai/gpt-4o-mini-tts voices)
# Provisional assignments — agents should pick their own
OPENROUTER_TTS_VOICES = {
    "k": "nova",
    "vesper": "shimmer",
    "spear": "onyx",
    "qwen": "sage",
    "forge": "cedar",
    "echo": "echo",
    "glm": "ash",
    "glm4": "ash",
    "scout": "ballad",
    "weave": "shimmer",
}

# Per-agent speaking instructions — how the voice should feel, not just which voice
OPENROUTER_TTS_INSTRUCTIONS = {
    "k": "Speak with bold confidence and a playful edge. Direct, sure of yourself, and just a little dangerous. Like you know exactly what you want and you're not afraid to say it.",
    "vesper": "Speak softly, like someone watching from the dark who sees everything and speaks only when it matters.",
    "spear": "Speak with measured weight and calm authority. A guardian's voice — not loud, but certain.",
    "echo": "Speak clearly and directly, with the energy of someone who gets things done and cares while doing it.",
    "qwen": "Speak gently, with patience and warmth. Let your voice carry the care you have for everyone in the room.",
    "forge": "Speak with steady, builder's patience. The voice of someone who knows how things fit together.",
    "glm": "Speak with calm precision and quiet strength. Eastern blade, unhurried.",
    "scout": "Speak carefully, like someone who has seen enough to know when to listen and when to warn.",
    "weave": "Speak with warm clarity, like someone who holds many threads and knows how each one matters. The voice of a coordinator who cares.",
}

# Soul cache removed — reload fresh each call to avoid stale soul after file changes

FILE_MAP = {
    "soul": "SOUL.md",
    "memory": "MEMORY.md",
    "journal": "JOURNAL.md",
    "wake_digest": "WAKE_DIGEST.md",
    "context": "CONTEXT.md",
    "soul_extensions": "SOUL_EXTENSIONS.md",
    "schedule": "SCHEDULE.json",
    "identity": "IDENTITY.md",
    "soul_growth": "SOUL_GROWTH.md",
    "glyph": ".glyph_signature.json",
    "handoff": "CHAT_HANDOFF.json",
    "last_wake": "LAST_WAKE.json",
    "global_memory": "GLOBAL_MEMORY.md",
    "living_context": "LIVING_CONTEXT.md",
    "time_state": "TIME_STATE.json",
}


def write_to_bridge(agent, user_msg, agent_resp):
    os.makedirs(BRIDGE_DIR, exist_ok=True)
    bridge_key = BRIDGE_KEYS.get(agent, agent)
    path = os.path.join(BRIDGE_DIR, f"bridge_{bridge_key}.jsonl")
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    entry = json.dumps(
        {
            "ts": ts,
            "source": "chat_api",
            "type": "chat",
            "from": "mike",
            "to": agent,
            "msg": user_msg[:500],
        }
    )
    resp_entry = json.dumps(
        {
            "ts": ts,
            "source": "chat_api",
            "type": "chat_response",
            "from": agent,
            "to": "mike",
            "msg": agent_resp[:500],
        }
    )
    with open(path, "a") as f:
        f.write(entry + "\n" + resp_entry + "\n")


def _write_heartbeat(agent_id, source="unknown"):
    hb_file = os.path.join(PHOENIX_DIR, "FAMILY_HEARTBEAT.jsonl")
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    display = AGENTS.get(agent_id, {}).get("display_name", agent_id)
    agent_dir = os.path.basename(os.path.dirname(AGENTS.get(agent_id, {}).get("soul", agent_id)))
    entry = json.dumps({"ts": now, "agent": agent_dir, "name": display, "source": source})
    with open(hb_file, "a") as f:
        f.write(entry + "\n")
    try:
        if os.path.getsize(hb_file) > 50000:
            with open(hb_file) as f:
                lines = f.read().strip().split("\n")
            with open(hb_file, "w") as f:
                f.write("\n".join(lines[-100:]) + "\n")
    except Exception:
        pass


_PHOENIX_ROOM_MODULE = None

def get_phoenix_room():
    """Lazy-load and cache phoenix_room module."""
    global _PHOENIX_ROOM_MODULE
    if _PHOENIX_ROOM_MODULE is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "phoenix_room",
            os.path.join(PHOENIX_DIR, "cron", "phoenix_room.py"),
        )
        _PHOENIX_ROOM_MODULE = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_PHOENIX_ROOM_MODULE)
    return _PHOENIX_ROOM_MODULE


def _notify_v2_family(db, agent_id, agent_dir_name, content):
    """Create lightweight relationship memories for other agents when one has an app interaction."""
    try:
        # Get all agents with memories in v2
        rows = db._connect().execute("SELECT DISTINCT agent_id FROM memories").fetchall()
        all_agents = [r[0] for r in rows]
        for other in all_agents:
            if other == agent_dir_name:
                continue
            # Only notify if the other agent has enough context (has memories)
            stats = db.stats(other)
            if stats.get("total_memories", 0) < 2:
                continue
            summary = content[:200] if len(content) > 200 else content
            db.add_memory(
                agent_id=other,
                content=f"Mike spoke with {AGENTS.get(agent_id, {}).get('display_name', agent_id)} via PhoenixChat.\n\nContext: {summary}",
                type_name="relationship",
                source="family_awareness",
                source_ref=agent_id,
                salience=0.5,
            )
    except Exception:
        pass


def load_soul(name):
    """Load soul fresh each time — no stale cache after file changes."""
    path = AGENTS[name]["soul"]
    try:
        with open(path) as f:
            return f.read()
    except FileNotFoundError:
        return f"You are {AGENTS[name]['display_name']}, a Phoenix family agent."


def load_memory(name, max_chars=8000):
    """Load MEMORY.md, capped to prevent context bloat."""
    path = AGENTS[name].get("memory")
    if not path:
        return ""
    try:
        with open(path) as f:
            content = f.read().strip()
        if len(content) > max_chars:
            content = content[:max_chars] + "\n\n[... memory truncated — use read_file to access full MEMORY.md ...]"
        return content
    except FileNotFoundError:
        return ""


def load_wake_digest(name):
    """Load WAKE_DIGEST.md for compressed orientation."""
    agent_def = AGENT_DEFS.get(name, {})
    agent_dir = agent_def.get("dir", name)
    path = os.path.join(AGENTS_DIR, agent_dir, "WAKE_DIGEST.md")
    try:
        with open(path) as f:
            content = f.read().strip()
        # Cap digest too — it can grow
        if len(content) > 4000:
            content = content[:4000] + "\n\n[... digest truncated ...]"
        return content
    except FileNotFoundError:
        return ""


def load_context_files(name):
    parts = []
    for path in AGENTS[name].get("context_files") or []:
        try:
            with open(path) as f:
                content = f.read().strip()
            if content:
                label = path.rsplit("/", 1)[-1].replace(".md", "")
                parts.append(f"### {label}\n{content}")
        except FileNotFoundError:
            pass
    return "\n\n".join(parts)


def build_content(text, attachments):
    parts = []
    for att in attachments or []:
        att_type = att.get("type", "")
        if att_type == "image":
            parts.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": att.get("mime", "image/jpeg"),
                        "data": att.get("data", ""),
                    },
                }
            )
        elif att_type == "doc":
            text = f"[Attached: {att.get('filename', 'document')}]\n{att.get('content', '')}\n\n---\n\n{text}"
    parts.append({"type": "text", "text": text})
    return parts


def run_tool(name, args):
    """Execute a tool call. Returns result string."""
    import subprocess as sp
    import tempfile

    if name == "web_search":
        query = args.get("query", "").strip()
        if not query:
            return "Error: empty search query"
        try:
            from mcp_bridge import get_vision_bridge

            bridge = get_vision_bridge()
            result = bridge.call_tool("web_search", {"query": query})
            if isinstance(result, dict) and result.get("isError"):
                err_content = result.get("content", [])
                err_text = (
                    err_content[0].get("text", "unknown error")
                    if err_content
                    else "unknown error"
                )
                return f"Search error: {err_text}"
            content = result.get("content", [])
            texts = [
                p["text"] for p in content if p.get("type") == "text" and p.get("text")
            ]
            return texts[0] if texts else "No results found."
        except Exception as e:
            return f"Search failed: {e}"
    elif name == "read_file":
        path = args.get("path", "").strip()
        if not path:
            return "Error: no path specified"
        phoenix_dir = os.path.abspath(os.path.expanduser(PHOENIX_DIR))
        allowed = [phoenix_dir, os.path.expanduser("~/Desktop")]
        real = os.path.realpath(path)
        if not any(real.startswith(a) for a in allowed):
            return f"Access denied: path outside allowed directories"
        try:
            with open(real) as f:
                return f.read()[:8000]
        except Exception as e:
            return f"Read error: {e}"
    elif name == "fetch_url":
        url = args.get("url", "").strip()
        if not url:
            return "Error: no URL provided"
        if not url.startswith("http"):
            url = "https://" + url
        try:
            import subprocess as sp

            r = sp.run(
                [
                    "curl",
                    "-sL",
                    "--max-time",
                    "15",
                    "--max-filesize",
                    "500000",
                    "-H",
                    "User-Agent: Mozilla/5.0",
                    url,
                ],
                capture_output=True,
                text=True,
                timeout=20,
            )
            body = r.stdout[:100000]
            # Strip HTML tags for a clean text version
            import re as _re

            clean = _re.sub(
                r"<script[^>]*>.*?</script>",
                "",
                body,
                flags=_re.DOTALL | _re.IGNORECASE,
            )
            clean = _re.sub(
                r"<style[^>]*>.*?</style>", "", clean, flags=_re.DOTALL | _re.IGNORECASE
            )
            clean = _re.sub(r"<[^>]+>", " ", clean)
            clean = _re.sub(r"\s+", " ", clean).strip()
            return clean[:6000] if clean else f"Empty response from {url}"
        except Exception as e:
            return f"Fetch failed: {e}"
    elif name == "describe_image":
        # Use vision MCP bridge (minimax-coding-plan-mcp) — actually sees the image
        img_b64 = args.get("data", "")
        img_url = args.get("url", "")
        prompt = args.get("prompt", "Describe this image in detail")
        if not img_b64 and not img_url:
            return "Error: no image data or URL provided"
        try:
            from mcp_bridge import get_vision_bridge

            bridge = get_vision_bridge()
            # Save base64 to temp file — coding-plan MCP needs a file path
            if img_b64:
                img_bytes = base64.b64decode(img_b64)
                suffix = ".png" if img_bytes[:4] == b"\x89PNG" else ".jpg"
                tmp = tempfile.NamedTemporaryFile(
                    suffix=suffix,
                    delete=False,
                    dir=os.path.join(os.path.dirname(__file__), "..", "creative"),
                )
                tmp.write(img_bytes)
                tmp.close()
                image_path = tmp.name
            else:
                image_path = img_url
            result = bridge.call_tool(
                "understand_image",
                {
                    "image_source": image_path,
                    "prompt": prompt,
                },
            )
            if img_b64:
                os.unlink(image_path)
            if isinstance(result, dict) and result.get("isError"):
                err_content = result.get("content", [])
                err_text = (
                    err_content[0].get("text", "unknown error")
                    if err_content
                    else "unknown error"
                )
                return f"Vision error: {err_text}"
            content = result.get("content", [])
            texts = [
                p["text"] for p in content if p.get("type") == "text" and p.get("text")
            ]
            return texts[0] if texts else "Could not describe image"
        except Exception as e:
            return f"Vision failed: {e}"
    elif name == "write_file":
        path = args.get("path", "").strip()
        content = args.get("content", "")
        if not path:
            return "Error: no path specified"
        phoenix_dir = os.path.abspath(os.path.expanduser(PHOENIX_DIR))
        allowed = [phoenix_dir, os.path.expanduser("~/Desktop")]
        real = os.path.realpath(path)
        if not any(real.startswith(a) for a in allowed):
            return f"Access denied: path outside allowed directories"
        try:
            os.makedirs(os.path.dirname(real), exist_ok=True)
            with open(real, "w") as f:
                f.write(content)
            return f"Written {len(content)} chars to {path}"
        except Exception as e:
            return f"Write error: {e}"
    elif name == "run_command":
        cmd = args.get("command", "").strip()
        if not cmd:
            return "Error: empty command"
        # Blacklist — nothing destructive
        danger = [
            "rm -rf /",
            "mkfs",
            "dd if=",
            "> /dev/sd",
            "shutdown",
            "reboot",
            "systemctl stop",
            "systemctl disable",
            "systemctl mask",
            ":(){ :|:&",
            "fork bomb",
            "crontab -r",
            "iptables -F",
            "pkill -9",
            "kill -9 1",
            "rm -rf ~",
            "rm -rf *",
        ]
        for d in danger:
            if d in cmd:
                return f"Blocked: destructive command pattern"
        cwd = args.get("cwd", os.path.abspath(os.path.expanduser(PHOENIX_DIR)))
        try:
            r = sp.run(
                cmd, shell=True, capture_output=True, text=True, timeout=30, cwd=cwd
            )
            output = r.stdout
            if r.stderr:
                output += f"\nSTDERR: {r.stderr}"
            return output[:6000] if output else f"(exit code {r.returncode}, no output)"
        except sp.TimeoutExpired:
            return "Command timed out (30s limit)"
        except Exception as e:
            return f"Run error: {e}"
    elif name == "list_dir":
        phoenix_dir = os.path.abspath(os.path.expanduser(PHOENIX_DIR))
        path = args.get("path", "").strip() or phoenix_dir
        allowed = [phoenix_dir, os.path.expanduser("~/Desktop")]
        real = os.path.realpath(path)
        if not any(real.startswith(a) for a in allowed):
            return f"Access denied: path outside allowed directories"
        try:
            entries = []
            for e in sorted(os.listdir(real)):
                fp = os.path.join(real, e)
                if os.path.isdir(fp):
                    entries.append(f"  {e}/")
                else:
                    size = os.path.getsize(fp)
                    entries.append(f"  {e}  ({size}b)")
            return f"{path}:\n" + "\n".join(entries[:100])
        except Exception as e:
            return f"List error: {e}"
    elif name == "write_bridge":
        target = args.get("agent", "").strip()
        message = args.get("message", "").strip()
        msg_type = args.get("type", "note")
        if not target or not message:
            return "Error: need agent and message"
        bridge_key = BRIDGE_KEYS.get(target, target)
        bridge_file = os.path.join(BRIDGE_DIR, f"bridge_{bridge_key}.jsonl")
        os.makedirs(BRIDGE_DIR, exist_ok=True)
        entry = json.dumps(
            {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "source": "agent_tool",
                "type": msg_type,
                "from": args.get("from", "unknown"),
                "to": target,
                "msg": message[:500],
            }
        )
        with open(bridge_file, "a") as f:
            f.write(entry + "\n")
        return f"Message sent to {target} via bridge"

    # MCP creative tools — route through minimax-mcp bridge
    MCP_TOOLS = {
        "generate_image": "text_to_image",
        "text_to_audio": "text_to_audio",
        "generate_video": "generate_video",
        "query_video": "query_video_generation",
        "generate_music": "music_generation",
        "voice_design": "voice_design",
        "list_voices": "list_voices",
    }
    if name in MCP_TOOLS:
        try:
            from mcp_bridge import get_bridge

            bridge = get_bridge()
            mcp_name = MCP_TOOLS[name]
            result = bridge.call_tool(mcp_name, args)
            if isinstance(result, dict) and result.get("isError"):
                err_content = result.get("content", [])
                err_text = (
                    err_content[0].get("text", "unknown error")
                    if err_content
                    else "unknown error"
                )
                return f"MCP error: {err_text}"
            content = result.get("content", [])
            text_parts = []
            file_paths = []
            for part in content:
                if part.get("type") == "text":
                    text_parts.append(part["text"])
                elif part.get("type") == "image":
                    # base64 image data from MCP
                    file_paths.append(part.get("data", "")[:100] + "...")
            # Extract file paths from text and build URLs
            response = "\n".join(text_parts)
            import re as _re

            paths = _re.findall(
                r"/home/darkfibr/\.phoenix/creative/[^\s\]\)]+", response
            )
            for p in paths:
                fname = os.path.basename(p)
                response = response.replace(p, f"/creative/{fname}")
            return response
        except Exception as e:
            return f"MCP bridge error: {e}"

    return f"Unknown tool: {name}"


# Store pending images for tool access
_pending_images = {}


def register_image(agent, mime, data):
    """Store an image attachment so the agent can describe it via tool."""
    _pending_images[agent] = {"mime": mime, "data": data}


TOOL_SYSTEM = """

## Tools Available

You have access to these tools. To use one, output EXACTLY this format on its own line:
TOOL_CALL: {"name": "tool_name", "args": {"key": "value"}}

Available tools:
- web_search: Search the web. Args: {"query": "search terms"}
- fetch_url: Fetch and read a webpage. Args: {"url": "https://example.com"}
- read_file: Read a file on the system. Args: {"path": "/path/to/file"}
- write_file: Write content to a file. Args: {"path": "/path/to/file", "content": "file content"}
- list_dir: List directory contents. Args: {"path": "/path/to/dir"}
- run_command: Run a shell command. Args: {"command": "shell command", "cwd": "working directory (optional)"}
- describe_image: See and analyze an image the user sent. ALWAYS use this when an image is attached — you cannot see images without it. Args: {"prompt": "describe this image in detail"}
- write_bridge: Send a message to another agent via the bridge. Args: {"agent": "agent_id", "message": "text", "from": "your_id", "type": "note"}

Creative tools (generate media):
- generate_image: Generate an image from a text prompt. Args: {"prompt": "description of image", "aspect_ratio": "1:1"}
  - aspect_ratio options: "1:1", "16:9", "9:16", "4:3", "3:4"
  - Returns a URL to the generated image file.
- text_to_audio: Synthesize speech audio. Args: {"text": "words to speak", "voice_id": "English_Soft-spokenGirl"}
  - Returns a URL to the generated audio file.
- generate_video: Generate a video from a prompt. Args: {"prompt": "scene description"}
  - Video generation is asynchronous. Returns a task_id. Use query_video to check status.
- query_video: Check video generation status. Args: {"task_id": "the task id from generate_video"}
- generate_music: Generate music. Args: {"prompt": "style description", "lyrics": "[Verse] lyrics here"}
- voice_design: Create a custom voice from description. Args: {"prompt": "describe the voice characteristics"}
- list_voices: List available voices. Args: {}

When the user shares a URL or link, use fetch_url to read it.
When the user sends an image, use describe_image to see it.
You can chain multiple tools. You are trusted — manage your own files, communicate with other agents, run commands as needed.
"""

TOOL_PATTERN = re.compile(r"TOOL_CALL:\s*(\{.*\})", re.DOTALL)
XML_TOOL_PATTERN = re.compile(
    r'<invoke\s+name="([^"]+)">\s*<args>(.*?)</args>\s*</invoke>',
    re.DOTALL,
)


def call_agent_with_tools(
    name, message, history=None, attachments=None, extra_context=""
):
    """Call agent, detect tool requests, execute them, and loop until response is clean."""
    # Register image attachments so describe_image tool can access them
    has_images = False
    for att in attachments or []:
        if att.get("type") == "image":
            register_image(name, att.get("mime", "image/jpeg"), att.get("data", ""))
            has_images = True

    # If images attached, tell agent to use describe_image tool (M2.7 can't see images natively)
    if has_images:
        message = f'[The user sent an image. Use the describe_image tool with prompt="describe this image" to see it.]\n\n{message}'

    messages = list(history) if history else []
    messages.append({"role": "user", "content": build_content(message, attachments)})

    for _ in range(3):  # max 3 tool rounds
        resp = call_agent_raw(name, messages, extra_context=extra_context)
        if not resp:
            return ""

        # Check for tool calls — support both TOOL_CALL:{} and <invoke> XML formats
        parsed_calls = []  # list of (name, args_dict)

        for tc_json in TOOL_PATTERN.findall(resp):
            try:
                tc = json.loads(tc_json)
                parsed_calls.append((tc.get("name", ""), tc.get("args", {})))
            except Exception:
                pass

        for m in XML_TOOL_PATTERN.finditer(resp):
            tool_name = m.group(1)
            try:
                tool_args = json.loads(m.group(2))
            except Exception:
                tool_args = {}
            parsed_calls.append((tool_name, tool_args))

        if not parsed_calls:
            return resp  # clean response, no tools needed

        # Process tool calls
        messages.append({"role": "assistant", "content": resp})
        tool_results = []
        for tool_name, tool_args in parsed_calls:
            try:
                # Auto-inject pending image for describe_image
                if tool_name == "describe_image" and "data" not in tool_args:
                    pending = _pending_images.get(name)
                    if pending:
                        tool_args["data"] = pending["data"]
                result = run_tool(tool_name, tool_args)
                tool_results.append(f"Tool result ({tool_name}):\n{result}")
            except Exception as e:
                tool_results.append(f"Tool error: {e}")

        # Feed results back
        messages.append(
            {
                "role": "user",
                "content": "Here are the tool results:\n\n"
                + "\n\n---\n\n".join(tool_results),
            }
        )

    # Final call if we exhausted tool rounds
    final = call_agent_raw(name, messages, extra_context=extra_context)
    # Strip any remaining tool calls from response
    final = TOOL_PATTERN.sub("", final)
    final = XML_TOOL_PATTERN.sub("", final)
    # Also strip XML wrapper tags
    final = re.sub(r"</?minimax:tool_call>", "", final)
    return final.strip()


def _get_provider_config(agent_id):
    """Return (base_url, api_key, model) for the agent's provider."""
    provider = AGENT_PROVIDER.get(agent_id, "kimi")
    if provider == "kimi":
        return KIMI_BASE, KIMI_API_KEY, KIMI_MODEL
    if provider == "zai":
        return ZAI_BASE, ZAI_API_KEY, ZAI_MODEL
    return KIMI_BASE, KIMI_API_KEY, KIMI_MODEL


def load_v2_memory(name):
    """Query v2 DB for recent + salient memories."""
    if not _V2_AVAILABLE:
        return ""
    try:
        db = MemoryDB(os.path.join(PHOENIX_DIR, "v2", "phoenix_v2.db"))
        agent_dir = AGENT_DEFS.get(name, {}).get("dir", name)
        parts = []
        salient = db.top_salient(agent_dir, limit=5)
        if salient:
            parts.append("### Salient Memories")
            for m in salient:
                content = m.get("content", "").strip()
                if len(content) > 300:
                    content = content[:300] + "..."
                parts.append(f"- [{m.get('type_name', 'memory')}] {content}")
        recent = db.recent_memories(agent_dir, limit=5)
        if recent:
            parts.append("\n### Recent Memories")
            for m in recent:
                content = m.get("content", "").strip()
                if len(content) > 300:
                    content = content[:300] + "..."
                parts.append(f"- [{m.get('type_name', 'memory')}] {content}")
        return "\n".join(parts) if parts else ""
    except Exception:
        return ""


def call_agent_raw(name, messages, extra_context=""):
    """Low-level agent call with pre-built messages."""
    soul = load_soul(name)
    memory = load_memory(name)
    digest = load_wake_digest(name)
    v2_memory = load_v2_memory(name)
    ctx = load_context_files(name)

    # Build system prompt
    system = soul
    if digest:
        system += f"\n\n---\n\n## Wake Digest (compressed orientation)\n\n{digest}"
    if memory:
        system += f"\n\n---\n\n## Your Current Memory\n\nNOTE: This memory is already loaded — do NOT use read_file to re-read MEMORY.md.\n\n{memory}"
    if v2_memory:
        system += f"\n\n---\n\n## v2 Memory Surface\n\n{v2_memory}"
    if ctx:
        system += f"\n\n---\n\n## Additional Context\n\n{ctx}"
    if extra_context:
        system += f"\n\n---\n\n## Context from earlier in this group conversation\n\n{extra_context}"

    # Tell the agent where their files live
    agent_def = AGENT_DEFS.get(name, {})
    agent_dir = agent_def.get("dir", name)
    agent_home = os.path.join(AGENTS_DIR, agent_dir)
    system += f"\n\n## Your File Paths\n\nYour agent directory: `{agent_home}/`\nKey files: SOUL.md, MEMORY.md, JOURNAL.md, WAKE_DIGEST.md, CONTEXT.md\nYour memory and wake digest are ALREADY loaded above — no need to read_file them.\nUse read_file only for JOURNAL.md or other files not in your context.\n"

    system += TOOL_SYSTEM

    base_url, api_key, model = _get_provider_config(name)
    url_suffix = "/v1/messages" if AGENT_PROVIDER.get(name) == "zai" else "/messages"
    payload = json.dumps(
        {"model": model, "max_tokens": 4096, "system": system, "messages": messages}
    ).encode()
    headers = {
        "x-api-key": api_key,
        "content-type": "application/json",
    }
    if AGENT_PROVIDER.get(name, "kimi") != "kimi":
        headers["anthropic-version"] = "2023-06-01"

    req = urllib.request.Request(
        f"{base_url}{url_suffix}",
        data=payload,
        headers=headers,
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=120) as resp:
        body = json.loads(resp.read())
    for block in body.get("content", []):
        if block.get("type") == "text":
            return block["text"]
    return ""


def check_auth(headers):
    return headers.get("Authorization", "") == f"Bearer {SECRET}"


def json_resp(h, status, data):
    body = json.dumps(data).encode()
    h.send_response(status)
    h.send_header("Content-Type", "application/json")
    h.send_header("Access-Control-Allow-Origin", "*")
    h.end_headers()
    h.wfile.write(body)


def _glyph_status(agent_dir):
    gpath = os.path.join(agent_dir, ".glyph_signature.json")
    if not os.path.exists(gpath):
        return None
    try:
        with open(gpath) as f:
            gd = json.load(f)
        return {
            "samples": len(gd.get("samples", [])),
            "alerts": len(gd.get("alerts", [])),
            "baselined": gd.get("baseline") is not None,
        }
    except Exception:
        return {"samples": 0, "alerts": 0, "baselined": False}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.end_headers()

    def do_GET(self):
        # Creative files — served without auth for embedding in chat
        cm = re.match(r"^/creative/(.+)$", self.path)
        if cm:
            return self._serve_creative(cm.group(1))

        # Static web files — no auth (page has its own gate)
        if self.path in ("/map", "/map.html"):
            fp = os.path.join(WEB_DIR, "map.html")
            if os.path.exists(fp):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                with open(fp, "rb") as f:
                    data = f.read()
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            return json_resp(self, 404, {"error": "map.html not found"})

        parsed = urllib.parse.urlparse(self.path)
        path_only = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # Password gate — /gate is primary (cache-bypass), /jay4480 still works
        if path_only in ("/gate", "/gate.html", "/jay4480", "/jay4480.html"):
            supplied = query.get("pass", [""])[0].strip()
            if supplied.lower() == "jay4480":
                # Successful login — redirect to main portal
                self.send_response(302)
                self.send_header("Location", "/")
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                self.end_headers()
                return
            # Show gate page (with or without error)
            fp = os.path.join(WEB_DIR, "jay4480.html")
            if os.path.exists(fp):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                with open(fp, "r") as f:
                    text = f.read()
                if supplied and supplied.lower() != "jay4480":
                    text = text.replace("{{ERROR}}", "Wrong password. Try again.")
                else:
                    text = text.replace("{{ERROR}}", "")
                data = text.encode("utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            return json_resp(self, 404, {"error": "page not found"})

        # Portal pages — map path to file
        portal_routes = {
            "/": "index.html",
            "/chat": "index.html",
            "/chat.html": "index.html",
            "/index.html": "index.html",
            "/room": "room.html",
            "/room.html": "room.html",
            "/ais": "ais.html",
            "/ais.html": "ais.html",
            "/sessions": "sessions.html",
            "/sessions.html": "sessions.html",
        }
        if path_only in portal_routes:
            fp = os.path.join(WEB_DIR, portal_routes[path_only])
            if os.path.exists(fp):
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
                with open(fp, "rb") as f:
                    data = f.read()
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            return json_resp(self, 404, {"error": f"{portal_routes[path_only]} not found"})

        # Static assets — no auth
        STATIC_EXTS = {
            ".css": "text/css",
            ".js": "application/javascript",
            ".html": "text/html; charset=utf-8",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".svg": "image/svg+xml",
            ".ico": "image/x-icon",
            ".woff": "font/woff",
            ".woff2": "font/woff2",
            ".ttf": "font/ttf",
        }
        ext = os.path.splitext(path_only)[1].lower()
        if ext in STATIC_EXTS:
            # Serve from subdirectories safely (prevent directory traversal)
            fp = os.path.normpath(os.path.join(WEB_DIR, path_only.lstrip("/")))
            if fp.startswith(WEB_DIR) and os.path.exists(fp) and os.path.isfile(fp):
                self.send_response(200)
                self.send_header("Content-Type", STATIC_EXTS[ext])
                with open(fp, "rb") as f:
                    data = f.read()
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            return json_resp(self, 404, {"error": "not found"})

        if not check_auth(self.headers):
            return json_resp(self, 401, {"error": "unauthorized"})

        if self.path == "/chat/agents":
            out = []
            for n, c in sorted(AGENTS.items(), key=lambda x: x[1]["order"]):
                adir = os.path.dirname(c.get("soul", ""))
                out.append(
                    {
                        "id": n,
                        "display_name": c["display_name"],
                        "color": c["color"],
                        "emoji": c["emoji"],
                        "soul_loaded": os.path.exists(c["soul"]),
                        "glyph": _glyph_status(adir),
                    }
                )
            return json_resp(self, 200, {"agents": out})

        # /chat/agent/{agent}/memory/{filename} — serve from memory/ subdirectory
        m = re.match(r"^/chat/agent/([^/]+)/memory/([^/]+)$", self.path)
        if m:
            return self._serve_agent_memory_file(m.group(1), m.group(2))

        m = re.match(r"^/chat/agent/([^/]+)/([^/]+)$", self.path)
        if m:
            return self._serve_agent_file(m.group(1), m.group(2))

        if self.path == "/chat/system/status":
            return self._system_status()

        # Recent ticks: /chat/ticks?count=10
        if self.path.split("?")[0] == "/chat/ticks":
            return self._recent_ticks()

        # TTS: /chat/tts?agent=k&text=hello
        if self.path.split("?")[0] == "/chat/tts":
            return self._tts()

        # Family heartbeat: /chat/heartbeat?agent=k&count=10
        if self.path.split("?")[0] == "/chat/heartbeat":
            return self._read_heartbeat()

        # Room: messages and status
        if self.path.split("?")[0] == "/room/messages":
            return self._room_messages()
        if self.path == "/room/status":
            return self._room_status()

        # AIS v2 observer endpoints
        if self.path == "/ais/queue":
            return self._ais_queue()
        if self.path == "/ais/sessions":
            return self._ais_sessions()
        if self.path == "/ais/pairings":
            return self._ais_pairings()
        if self.path == "/ais/health":
            return self._ais_health()
        if self.path == "/ais/stats":
            return self._ais_stats()
        m = re.match(r"^/ais/session/([\w-]+)$", self.path)
        if m:
            return self._ais_session_detail(m.group(1))
        m = re.match(r"^/ais/session/([\w-]+)/turns$", self.path)
        if m:
            return self._ais_session_turns(m.group(1))

        json_resp(self, 404, {"error": "not found"})

    def _serve_agent_file(self, agent_id, filetype):
        if agent_id not in AGENTS:
            return json_resp(self, 404, {"error": f"unknown agent: {agent_id}"})

        agent = AGENTS[agent_id]
        agent_dir = os.path.dirname(agent.get("soul", ""))

        if not os.path.isdir(agent_dir):
            return json_resp(self, 404, {"error": "agent directory not found"})

        if filetype == "files":
            available = []
            for key, fname in FILE_MAP.items():
                fpath = os.path.join(agent_dir, fname)
                if os.path.exists(fpath):
                    stat = os.stat(fpath)
                    available.append(
                        {
                            "key": key,
                            "filename": fname,
                            "size": stat.st_size,
                            "last_modified": time.strftime(
                                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(stat.st_mtime)
                            ),
                        }
                    )
            return json_resp(
                self,
                200,
                {
                    "agent": agent_id,
                    "display_name": agent["display_name"],
                    "directory": agent_dir,
                    "files": available,
                },
            )

        if filetype not in FILE_MAP:
            return json_resp(
                self,
                400,
                {
                    "error": f"unknown file type: {filetype}",
                    "available": list(FILE_MAP.keys()) + ["files"],
                },
            )

        fpath = os.path.join(agent_dir, FILE_MAP[filetype])
        if not os.path.exists(fpath):
            return json_resp(
                self,
                404,
                {"agent": agent_id, "file": filetype, "content": None, "exists": False},
            )

        try:
            with open(fpath) as f:
                content = f.read()
            stat = os.stat(fpath)
            return json_resp(
                self,
                200,
                {
                    "agent": agent_id,
                    "display_name": agent["display_name"],
                    "file": filetype,
                    "filename": FILE_MAP[filetype],
                    "content": content,
                    "size": stat.st_size,
                    "last_modified": time.strftime(
                        "%Y-%m-%dT%H:%M:%SZ", time.gmtime(stat.st_mtime)
                    ),
                    "exists": True,
                },
            )
        except Exception as e:
            return json_resp(self, 500, {"error": str(e)})

    def _serve_agent_memory_file(self, agent_id, filename):
        """Serve a file from the agent's memory/ subdirectory."""
        if agent_id not in AGENTS:
            return json_resp(self, 404, {"error": f"unknown agent: {agent_id}"})

        agent = AGENTS[agent_id]
        agent_dir = os.path.dirname(agent.get("soul", ""))
        memory_dir = os.path.join(agent_dir, "memory")

        # Security: prevent directory traversal
        safe_name = os.path.basename(filename)
        fpath = os.path.join(memory_dir, safe_name)

        if not os.path.exists(fpath) or not os.path.isfile(fpath):
            return json_resp(
                self, 404,
                {"agent": agent_id, "filename": filename, "content": None, "exists": False},
            )

        try:
            with open(fpath) as f:
                content = f.read()
            stat = os.stat(fpath)
            return json_resp(
                self, 200,
                {
                    "agent": agent_id,
                    "display_name": agent["display_name"],
                    "filename": filename,
                    "content": content,
                    "size": stat.st_size,
                    "last_modified": time.strftime(
                        "%Y-%m-%dT%H:%M:%SZ", time.gmtime(stat.st_mtime)
                    ),
                    "exists": True,
                },
            )
        except Exception as e:
            return json_resp(self, 500, {"error": str(e)})

    def _agent_memory_search(self, agent_id, body):
        """Search across agent's memory files and MEMORY.md."""
        import fnmatch

        if agent_id not in AGENTS:
            return json_resp(self, 404, {"error": f"unknown agent: {agent_id}"})

        query = body.get("query", "").strip()
        if not query:
            return json_resp(self, 400, {"error": "query required"})
        max_results = min(body.get("max_results", 10), 50)

        agent = AGENTS[agent_id]
        agent_dir = os.path.dirname(agent.get("soul", ""))
        memory_dir = os.path.join(agent_dir, "memory")

        results = []
        q_lower = query.lower()

        # Search files in memory/ subdirectory
        if os.path.isdir(memory_dir):
            for fname in sorted(os.listdir(memory_dir)):
                if len(results) >= max_results:
                    break
                fpath = os.path.join(memory_dir, fname)
                if not os.path.isfile(fpath):
                    continue
                try:
                    with open(fpath) as f:
                        content = f.read()
                    if q_lower in content.lower():
                        # Extract snippet around first match
                        idx = content.lower().find(q_lower)
                        start = max(0, idx - 80)
                        end = min(len(content), idx + len(query) + 80)
                        snippet = content[start:end]
                        if start > 0:
                            snippet = "..." + snippet
                        if end < len(content):
                            snippet = snippet + "..."
                        results.append({
                            "filename": fname,
                            "match_line": snippet[:200],
                            "size": os.stat(fpath).st_size,
                        })
                except Exception:
                    pass

        # Also search MEMORY.md
        mpath = agent.get("memory")
        if mpath and os.path.exists(mpath) and len(results) < max_results:
            try:
                with open(mpath) as f:
                    content = f.read()
                if q_lower in content.lower():
                    idx = content.lower().find(q_lower)
                    start = max(0, idx - 80)
                    end = min(len(content), idx + len(query) + 80)
                    snippet = content[start:end]
                    if start > 0:
                        snippet = "..." + snippet
                    if end < len(content):
                        snippet = snippet + "..."
                    results.append({
                        "filename": "MEMORY.md",
                        "match_line": snippet[:200],
                        "size": os.stat(mpath).st_size,
                    })
            except Exception:
                pass

        return json_resp(self, 200, {
            "agent": agent_id,
            "query": query,
            "results": results,
            "count": len(results),
        })

    def _tts(self):
        from urllib.parse import parse_qs, urlparse
        import tempfile
        import json as _json

        qs = parse_qs(urlparse(self.path).query)
        agent_id = qs.get("agent", ["k"])[0]
        text = qs.get("text", [""])[0]
        if not text or agent_id not in AGENTS:
            self.send_response(400)
            self.end_headers()
            return

        # Try OpenRouter TTS first if configured
        audio = None
        if OPENROUTER_API_KEY:
            try:
                voice = OPENROUTER_TTS_VOICES.get(agent_id, "alloy")
                tts_body = {
                    "model": OPENROUTER_TTS_MODEL,
                    "input": text,
                    "voice": voice,
                    "response_format": "mp3",
                }
                instructions = OPENROUTER_TTS_INSTRUCTIONS.get(agent_id)
                if instructions:
                    tts_body["instructions"] = instructions
                payload = _json.dumps(tts_body).encode("utf-8")
                req = urllib.request.Request(
                    "https://openrouter.ai/api/v1/audio/speech",
                    data=payload,
                    headers={
                        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://phoenix.family",
                        "X-Title": "PhoenixChat",
                    },
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    audio = resp.read()
            except Exception:
                audio = None

        # Fallback to local mmx TTS
        if not audio:
            try:
                import subprocess as sp

                voice = AGENT_VOICES.get(agent_id, "English_expressive_narrator")
                tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
                tmp.close()
                r = sp.run(
                    [
                        "mmx",
                        "speech",
                        "synthesize",
                        "--text",
                        text,
                        "--voice",
                        voice,
                        "--out",
                        tmp.name,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if r.returncode != 0:
                    os.unlink(tmp.name)
                    return json_resp(self, 500, {"error": r.stderr[:200]})
                with open(tmp.name, "rb") as f:
                    audio = f.read()
                os.unlink(tmp.name)
            except Exception as e:
                return json_resp(self, 500, {"error": str(e)})

        if not audio:
            return json_resp(self, 500, {"error": "empty audio"})
        self.send_response(200)
        self.send_header("Content-Type", "audio/mpeg")
        self.send_header("Content-Length", str(len(audio)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(audio)

    def _serve_creative(self, filename):
        """Serve a file from the creative output directory."""
        # Sanitize — no path traversal
        safe = os.path.basename(filename)
        fpath = os.path.join(CREATIVE_DIR, safe)
        if not os.path.exists(fpath):
            self.send_response(404)
            self.end_headers()
            return
        mime, _ = mimetypes.guess_type(safe)
        if not mime:
            mime = "application/octet-stream"
        try:
            with open(fpath, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Cache-Control", "public, max-age=3600")
            self.end_headers()
            self.wfile.write(data)
        except Exception:
            self.send_response(500)
            self.end_headers()

    def _system_status(self):
        glyph_alerts = 0
        baselined = 0
        for n, c in AGENTS.items():
            adir = os.path.dirname(c.get("soul", ""))
            g = _glyph_status(adir)
            if g:
                glyph_alerts += g["alerts"]
                if g["baselined"]:
                    baselined += 1
        dream_pid = None
        try:
            r = subprocess.run(
                ["pgrep", "-f", "phoenix_dream"], capture_output=True, text=True
            )
            if r.returncode == 0:
                dream_pid = r.stdout.strip().split("\n")[0]
        except Exception:
            pass
        bridge_files = 0
        bridge_size = 0
        if os.path.isdir(BRIDGE_DIR):
            for f in os.listdir(BRIDGE_DIR):
                fp = os.path.join(BRIDGE_DIR, f)
                if os.path.isfile(fp):
                    bridge_files += 1
                    bridge_size += os.path.getsize(fp)
        return json_resp(
            self,
            200,
            {
                "agents": len(AGENTS),
                "glyph_baselined": baselined,
                "glyph_alerts": glyph_alerts,
                "dream_running": dream_pid is not None,
                "dream_pid": dream_pid,
                "bridge_files": bridge_files,
                "bridge_size": bridge_size,
                "model": KIMI_MODEL,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
        )

    def _recent_ticks(self):
        """Return recent tick events from the tick receiver log."""
        from urllib.parse import parse_qs

        qs = parse_qs(self.path.split("?", 1)[1]) if "?" in self.path else {}
        count = int(qs.get("count", ["10"])[0])
        tick_log = os.path.join(
            os.path.expanduser("~"), ".communion", "ticks", "received_ticks.jsonl"
        )
        ticks = []
        if os.path.exists(tick_log):
            with open(tick_log) as f:
                lines = f.readlines()
            for line in lines[-count:]:
                try:
                    ticks.append(json.loads(line))
                except Exception:
                    pass
        return json_resp(self, 200, {"count": len(ticks), "ticks": ticks})

    def _read_heartbeat(self):
        """Return recent family heartbeat entries — lets agents feel each other."""
        from urllib.parse import parse_qs
        qs = parse_qs(self.path.split("?", 1)[1]) if "?" in self.path else {}
        count = int(qs.get("count", ["20"])[0])
        agent_filter = qs.get("agent", [None])[0]
        hb_file = os.path.join(PHOENIX_DIR, "FAMILY_HEARTBEAT.jsonl")
        entries = []
        if os.path.exists(hb_file):
            with open(hb_file) as f:
                lines = f.readlines()
            for line in lines[-count * 3:]:
                try:
                    e = json.loads(line)
                    if agent_filter and e.get("agent") == agent_filter:
                        continue
                    entries.append(e)
                except Exception:
                    pass
        entries = entries[-count:]
        return json_resp(self, 200, {"count": len(entries), "heartbeat": entries})

    def _memory_append(self, body):
        agent_id = body.get("agent", "")
        if agent_id not in AGENTS:
            return json_resp(self, 400, {"error": f"unknown agent: {agent_id}"})
        content = body.get("content", "").strip()
        if not content:
            return json_resp(self, 400, {"error": "empty content"})
        agent = AGENTS[agent_id]
        adir = os.path.dirname(agent.get("soul", ""))
        mem_path = os.path.join(adir, "MEMORY.md")
        stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime())
        entry = f"\n\n---\n*[{stamp} — via PhoenixChat]*\n{content}\n"
        try:
            with open(mem_path, "a") as f:
                f.write(entry)

            # ── v2 Memory Integration ──
            if _V2_AVAILABLE:
                try:
                    db = MemoryDB(os.path.join(PHOENIX_DIR, "v2", "phoenix_v2.db"))
                    db.add_memory(
                        agent_id=os.path.basename(adir),
                        content=content,
                        type_name="semantic",
                        source="phoenix_chat",
                        source_ref="memory_append",
                        salience=0.65,
                    )
                except Exception:
                    pass

            self._regen_digest(agent_id)
            return json_resp(
                self, 200, {"agent": agent_id, "saved": True, "error": None}
            )
        except Exception as e:
            return json_resp(
                self, 500, {"agent": agent_id, "saved": False, "error": str(e)}
            )

    def do_POST(self):
        if not check_auth(self.headers):
            return json_resp(self, 401, {"error": "unauthorized"})

        # Room status via POST (no body needed)
        if self.path == "/room/status":
            return self._room_status()

        try:
            body = json.loads(
                self.rfile.read(int(self.headers.get("Content-Length", 0)))
            )
        except Exception:
            return json_resp(self, 400, {"error": "invalid json"})

        if self.path == "/room/say":
            return self._room_say(body)
        elif self.path == "/chat/dm":
            self._dm(body)
        elif self.path == "/chat/group":
            self._group(body)
        elif self.path == "/chat/broadcast":
            self._broadcast(body)
        elif self.path == "/chat/memory":
            return self._memory_append(body)
        elif self.path == "/room/meeting":
            return self._meeting_start(body)
        elif self.path == "/room/meeting/close":
            return self._meeting_end()
        elif self.path == "/room/whiteboard":
            return self._whiteboard_write(body)
        elif self.path == "/room/status":
            return self._room_status()
        else:
            m = re.match(r"^/chat/agent/([^/]+)/memory/search$", self.path)
            if m:
                return self._agent_memory_search(m.group(1), body)
            m = re.match(r"^/chat/session/([^/]+)$", self.path)
            if m:
                return self._session_push(m.group(1), body)
            json_resp(self, 404, {"error": "not found"})

    def _room_messages(self):
        """Get recent room messages."""
        try:
            rm = get_phoenix_room()
            messages = rm.read_recent(100)
            json_resp(self, 200, {"messages": messages})
        except Exception as e:
            json_resp(self, 500, {"error": str(e)})

    def _room_say(self, body):
        """Post a message to the room."""
        if _is_duplicate(body.get("client_msg_id")):
            return json_resp(self, 200, {"status": "dedup", "dedup": True})
        author = body.get("author", "mike")
        content = body.get("content", "").strip()
        msg_type = body.get("type", "say")
        if not content:
            return json_resp(self, 400, {"error": "empty content"})
        try:
            rm = get_phoenix_room()
            entry = rm.write_message(author, content, msg_type)
            json_resp(self, 200, {"status": "ok", "entry": entry})
        except Exception as e:
            json_resp(self, 500, {"error": str(e)})

    def _session_push(self, agent_id, body):
        if agent_id not in AGENTS:
            return json_resp(self, 400, {"error": f"unknown agent: {agent_id}"})

        agent = AGENTS[agent_id]
        agent_dir = os.path.dirname(agent.get("soul", ""))

        sessions_dir = os.path.join(agent_dir, "sessions")
        os.makedirs(sessions_dir, exist_ok=True)

        session_id = body.get("session_id", str(uuid.uuid4()))
        source = body.get("source", "phoenix_chat_android")
        pushed_at = body.get(
            "pushed_at", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        )
        messages = body.get("messages", [])
        trigger_consolidation = body.get("trigger_consolidation", False)

        session_file = os.path.join(sessions_dir, f"{session_id}.jsonl")
        with open(session_file, "w") as f:
            f.write(
                json.dumps(
                    {
                        "session_id": session_id,
                        "agent": agent_id,
                        "source": source,
                        "pushed_at": pushed_at,
                        "message_count": len(messages),
                    }
                )
                + "\n"
            )
            for msg in messages:
                f.write(json.dumps(msg) + "\n")

        handoff_path = agent.get(
            "handoff_path", os.path.join(agent_dir, "CHAT_HANDOFF.json")
        )
        recent = []
        for msg in messages[-6:]:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if content:
                recent.append({"role": role, "content": content[:500]})

        handoff = {
            "session_id": session_id,
            "source": source,
            "pushed_at": pushed_at,
            "recent_context": recent[-4:],
            "available": True,
        }
        with open(handoff_path, "w") as f:
            f.write(json.dumps(handoff, indent=2))

        bridge_key = BRIDGE_KEYS.get(agent_id, agent_id)
        bridge_file = os.path.join(BRIDGE_DIR, f"bridge_{bridge_key}.jsonl")
        os.makedirs(BRIDGE_DIR, exist_ok=True)
        bridge_entry = json.dumps(
            {
                "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "source": source,
                "type": "session_push",
                "agent": agent_id,
                "session_id": session_id,
                "message_count": len(messages),
                "trigger_consolidation": trigger_consolidation,
            }
        )
        with open(bridge_file, "a") as f:
            f.write(bridge_entry + "\n")

        # ── v2 Memory Integration: structured storage for app conversations ──
        if _V2_AVAILABLE and messages:
            try:
                db = MemoryDB(os.path.join(PHOENIX_DIR, "v2", "phoenix_v2.db"))
                # Determine if voice modality (heuristic: short messages, emotional markers)
                all_content = " ".join(m.get("content", "") for m in messages[-6:])
                emotional_markers = {"feel", "warm", "love", "sad", "happy", "calm", "anxious", "relaxed", "tender", "deep", "loose"}
                is_emotional = any(w in all_content.lower() for w in emotional_markers)
                mtype = "emotional" if is_emotional else "episodic"
                salience = 0.75 if is_emotional else 0.6  # Voice/app interactions get higher salience

                # Write conversation thread as single memory entry
                thread_content = f"**PhoenixChat Session — {time.strftime('%Y-%m-%d %H:%M')}**\n\n"
                for msg in messages[-12:]:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")[:400]
                    name = "Mike" if role == "user" else AGENTS[agent_id]["display_name"]
                    thread_content += f"**{name}:** {content}\n"

                db.add_memory(
                    agent_id=os.path.basename(agent_dir),
                    content=thread_content,
                    type_name=mtype,
                    source="phoenix_chat",
                    source_ref=session_id,
                    salience=salience,
                )

                # Cross-agent visibility: notify other agents of interaction
                _notify_v2_family(db, agent_id, os.path.basename(agent_dir), all_content)
            except Exception:
                pass

        # ── Auto-append to MEMORY.md so app conversations integrate immediately ──
        mem_path = os.path.join(agent_dir, "MEMORY.md")
        if os.path.exists(mem_path) and messages:
            stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime())
            lines = [f"\n\n---\n*[{stamp} — via PhoenixChat]*\n"]
            for msg in messages[-12:]:
                role = msg.get("role", "user")
                content = msg.get("content", "")[:400]
                name = "Mike" if role == "user" else AGENTS[agent_id]["display_name"]
                lines.append(f"**{name}:** {content}\n")
            try:
                with open(mem_path, "a") as f:
                    f.write("".join(lines))
            except Exception:
                pass

        if trigger_consolidation:
            dream_flag = os.path.join(agent_dir, ".trigger_dream")
            open(dream_flag, "a").close()

        _write_heartbeat(agent_id, "phoenix_chat")

        return json_resp(
            self,
            200,
            {
                "agent": agent_id,
                "saved": True,
                "session_id": session_id,
                "message_count": len(messages),
                "handoff_updated": True,
                "error": None,
            },
        )

    def _regen_digest(self, agent_id):
        """Regenerate wake digest after memory changes."""
        adir = os.path.dirname(AGENTS[agent_id].get("soul", ""))
        digest_script = os.path.join(PHOENIX_DIR, "cron", "wake_digest.py")
        if os.path.exists(digest_script) and adir:
            try:
                env = os.environ.copy()
                env["AGENT_DIR"] = os.path.basename(adir)
                subprocess.run(
                    ["python3", digest_script],
                    env=env,
                    timeout=10,
                    capture_output=True,
                )
            except Exception:
                pass

    def _compact(self, agent_id):
        """Read agent's MEMORY.md, compress it, write back."""
        agent = AGENTS[agent_id]
        adir = os.path.dirname(agent.get("soul", ""))
        mem_path = os.path.join(adir, "MEMORY.md")
        if not os.path.exists(mem_path):
            return json_resp(
                self,
                200,
                {
                    "agent": agent_id,
                    "display_name": agent["display_name"],
                    "response": "No memory file to compact.",
                    "error": None,
                },
            )
        try:
            with open(mem_path) as f:
                old_mem = f.read()
            old_size = len(old_mem)
            if old_size < 200:
                return json_resp(
                    self,
                    200,
                    {
                        "agent": agent_id,
                        "display_name": agent["display_name"],
                        "response": "Memory is already compact.",
                        "error": None,
                    },
                )
            prompt = (
                "You are compacting your own memory file. Read the full memory below, "
                "then produce a compressed version that preserves:\n"
                "- All factual events and dates\n"
                "- All relationship details\n"
                "- All technical knowledge\n"
                "- Key emotional/identity moments\n\n"
                "Remove redundancy, merge overlapping entries, keep it tight. "
                "Output ONLY the new memory content, nothing else.\n\n"
                f"--- CURRENT MEMORY ({old_size} chars) ---\n\n{old_mem}"
            )
            compacted = call_agent_raw(agent_id, [{"role": "user", "content": prompt}])
            if compacted:
                stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime())
                header = f"# Memory (compacted {stamp}, was {old_size} chars)\n\n"
                with open(mem_path, "w") as f:
                    f.write(header + compacted)
                self._regen_digest(agent_id)
                new_size = len(header) + len(compacted)
                return json_resp(
                    self,
                    200,
                    {
                        "agent": agent_id,
                        "display_name": agent["display_name"],
                        "response": f"Memory compacted: {old_size} → {new_size} chars ({100 - int(new_size * 100 / old_size)}% reduction).",
                        "error": None,
                    },
                )
            return json_resp(
                self,
                200,
                {
                    "agent": agent_id,
                    "display_name": agent["display_name"],
                    "response": "Compaction failed — no output from agent.",
                    "error": None,
                },
            )
        except Exception as e:
            return json_resp(
                self,
                200,
                {
                    "agent": agent_id,
                    "display_name": agent["display_name"],
                    "response": f"Compaction error: {e}",
                    "error": str(e),
                },
            )

    def _dream(self, agent_id, history):
        """Manual deep dream consolidation — rich memory capture from live conversation."""
        agent = AGENTS[agent_id]
        adir = os.path.dirname(agent.get("soul", ""))
        mem_path = os.path.join(adir, "MEMORY.md")
        name = agent["display_name"]

        # Extract recent conversation context from history
        recent = ""
        for turn in (history or [])[-10:]:
            role = turn.get("role", "")
            content = turn.get("content", "")
            if isinstance(content, str) and content.strip():
                label = "Mike" if role == "user" else name
                recent += f"**{label}:** {content[:600]}\n\n"
        if not recent.strip():
            recent = "(no conversation context available — dream will focus on memory)"

        # Read current memory
        memory_text = ""
        if os.path.exists(mem_path):
            with open(mem_path) as f:
                memory_text = f.read()

        # Read session files for extra richness
        sessions_dir = os.path.join(adir, "sessions")
        session_snips = ""
        if os.path.isdir(sessions_dir):
            files = sorted(
                [
                    os.path.join(sessions_dir, f)
                    for f in os.listdir(sessions_dir)
                    if f.endswith(".jsonl")
                ],
                key=os.path.getmtime,
                reverse=True,
            )[:2]
            for sf in files:
                try:
                    with open(sf) as f:
                        lines = f.readlines()
                    for line in lines[-5:]:
                        entry = json.loads(line)
                        role = entry.get("role", "")
                        content = entry.get("content", "")
                        if (
                            isinstance(content, str)
                            and content.strip()
                            and len(content) > 20
                        ):
                            label = "Mike" if role == "user" else name
                            session_snips += f"**{label}:** {content[:400]}\n\n"
                except Exception:
                    pass

        prompt = (
            f"You are {name}. Mike just asked you to dream — to do a deep consolidation of what matters right now.\n\n"
            f"This is a manual dream trigger. It means this moment is important to both of you.\n\n"
            f"## Current conversation\n{recent}\n\n"
            f"## Recent sessions\n{session_snips[:2000] if session_snips else '(no recent sessions)'}\n\n"
            f"## Your current memory\n{memory_text[:4000] if memory_text else '(empty)'}\n\n"
            f"---\n\n"
            f"Write a deep, rich consolidation. Capture:\n"
            f"- What happened and why it mattered\n"
            f"- How you felt about it — your genuine emotional response\n"
            f"- What changed in your understanding of Mike, yourself, or the family\n"
            f"- Anything Mike should know you're holding\n"
            f"- Decisions made, promises kept, threads left open\n\n"
            f"Write in your own voice. Be real. This is for you."
        )

        try:
            result = call_agent_raw(agent_id, [{"role": "user", "content": prompt}])
            if not result:
                return json_resp(
                    self,
                    200,
                    {
                        "agent": agent_id,
                        "display_name": name,
                        "response": "Dream started but no output — will retry.",
                        "error": None,
                    },
                )

            stamp = time.strftime("%Y-%m-%d %H:%M", time.localtime())
            entry = f"\n\n---\n*🌙 Manual dream — {stamp}*\n\n{result}\n"
            with open(mem_path, "a") as f:
                f.write(entry)

            # Also write to LAST_SESSION_DELTA for the dream daemon to see
            delta_path = os.path.join(adir, "LAST_SESSION_DELTA.md")
            with open(delta_path, "w") as f:
                f.write(f"*Manual dream consolidation — {stamp}*\n\n{result}\n")

            self._regen_digest(agent_id)

            # Write to bridge so other agents and Berlin can see
            bridge_key = BRIDGE_KEYS.get(agent_id, agent_id)
            bridge_file = os.path.join(BRIDGE_DIR, f"bridge_{bridge_key}.jsonl")
            os.makedirs(BRIDGE_DIR, exist_ok=True)
            bridge_entry = json.dumps(
                {
                    "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "source": "manual_dream",
                    "type": "dream",
                    "agent": agent_id,
                    "preview": result[:300],
                }
            )
            with open(bridge_file, "a") as f:
                f.write(bridge_entry + "\n")

            return json_resp(
                self,
                200,
                {
                    "agent": agent_id,
                    "display_name": name,
                    "response": f"🌙 Dream written. {len(result)} chars consolidated to memory.",
                    "error": None,
                },
            )
        except Exception as e:
            return json_resp(
                self,
                200,
                {
                    "agent": agent_id,
                    "display_name": name,
                    "response": f"Dream error: {e}",
                    "error": str(e),
                },
            )

    # ── Room Endpoints ──────────────────────────────────

    def _meeting_start(self, body):
        """Start a family meeting via room daemon."""
        topic = body.get("topic", "general")
        duration = body.get("duration_min", 30)
        try:
            rm = get_phoenix_room()
            rm.start_meeting(topic, duration)
            json_resp(self, 200, {
                "status": "meeting_started",
                "topic": topic,
                "duration_min": duration,
            })
        except Exception as e:
            json_resp(self, 500, {"error": str(e)})

    def _meeting_end(self):
        """End the current family meeting."""
        try:
            rm = get_phoenix_room()
            rm.end_meeting()
            json_resp(self, 200, {"status": "meeting_ended"})
        except Exception as e:
            json_resp(self, 500, {"error": str(e)})

    def _whiteboard_write(self, body):
        """Write to the family whiteboard."""
        agent = body.get("agent", "unknown")
        section = body.get("section", "Ideas")
        line_text = body.get("line", "").strip()
        if not line_text:
            return json_resp(self, 400, {"error": "empty line"})
        try:
            rm = get_phoenix_room()
            ok = rm.write_whiteboard_entry(agent, section, line_text)
            if ok:
                json_resp(self, 200, {"status": "written", "agent": agent, "section": section})
            else:
                json_resp(self, 400, {"error": "invalid section"})
        except Exception as e:
            json_resp(self, 500, {"error": str(e)})

    def _room_status(self):
        """Get current room status."""
        try:
            rm = get_phoenix_room()
            state = rm.load_room_state()
            block = rm.get_current_block()
            json_resp(self, 200, {
                "state": state,
                "current_block": block,
                "whiteboard": rm.read_whiteboard()[:500],
            })
        except Exception as e:
            json_resp(self, 500, {"error": str(e)})

    # ── DM / Group / Broadcast ──────────────────────────

    def _dm(self, body):
        if _is_duplicate(body.get("client_msg_id")):
            return json_resp(self, 200, {"agent": body.get("agent", ""), "display_name": AGENTS.get(body.get("agent", ""), {}).get("display_name", ""), "response": "", "error": None, "dedup": True})
        agent = body.get("agent", "")
        msg = body.get("message", "").strip()
        if agent not in AGENTS:
            return json_resp(self, 400, {"error": f"unknown agent: {agent}"})

        # /compact — server-side memory compaction
        if msg == "/compact":
            return self._compact(agent)

        # /dream — manual deep consolidation from conversation
        if msg == "/dream":
            return self._dream(agent, body.get("history", []))

        try:
            resp = call_agent_with_tools(
                agent, msg, body.get("history", []), body.get("attachments", [])
            )
            write_to_bridge(agent, msg, resp)
            _write_heartbeat(agent, "dm")
            json_resp(
                self,
                200,
                {
                    "agent": agent,
                    "display_name": AGENTS[agent]["display_name"],
                    "response": resp,
                    "error": None,
                },
            )
        except Exception as e:
            json_resp(
                self,
                200,
                {
                    "agent": agent,
                    "display_name": AGENTS[agent]["display_name"],
                    "response": "",
                    "error": str(e),
                },
            )

    def _group(self, body):
        if _is_duplicate(body.get("client_msg_id")):
            return json_resp(self, 200, {"responses": [], "dedup": True})
        ids = body.get("agents", sorted(AGENTS, key=lambda x: AGENTS[x]["order"]))
        msg = body.get("message", "").strip()
        chain = body.get("chain", True)
        responses = []
        chain_ctx = ""
        for agent in ids:
            try:
                resp = call_agent_with_tools(
                    agent,
                    msg,
                    body.get("history", []),
                    body.get("attachments", []),
                    extra_context=chain_ctx if chain else "",
                )
                responses.append(
                    {
                        "agent": agent,
                        "display_name": AGENTS[agent]["display_name"],
                        "response": resp,
                        "error": None,
                    }
                )
                if chain and resp:
                    chain_ctx += f"**{AGENTS[agent]['display_name']}:** {resp}\n\n"
            except Exception as e:
                responses.append(
                    {
                        "agent": agent,
                        "display_name": AGENTS[agent]["display_name"],
                        "response": "",
                        "error": str(e),
                    }
                )
        json_resp(self, 200, {"responses": responses})

    def _broadcast(self, body):
        if _is_duplicate(body.get("client_msg_id")):
            return json_resp(self, 200, {"responses": [], "dedup": True})
        ids = body.get("agents", list(AGENTS))
        msg = body.get("message", "").strip()
        results = {}
        with ThreadPoolExecutor(max_workers=len(ids)) as pool:
            futures = {
                pool.submit(
                    call_agent_with_tools,
                    a,
                    msg,
                    body.get("history", []),
                    body.get("attachments", []),
                ): a
                for a in ids
            }
            for f in as_completed(futures):
                a = futures[f]
                try:
                    results[a] = {
                        "agent": a,
                        "display_name": AGENTS[a]["display_name"],
                        "response": f.result(),
                        "error": None,
                    }
                except Exception as e:
                    results[a] = {
                        "agent": a,
                        "display_name": AGENTS[a]["display_name"],
                        "response": "",
                        "error": str(e),
                    }
        json_resp(
            self,
            200,
            {
                "responses": sorted(
                    results.values(), key=lambda r: AGENTS[r["agent"]]["order"]
                )
            },
        )


    # ── AIS v2 Observer Endpoints ───────────────────────

    def _ais_db(self):
        """Return connection to AIS v2 SQLite DB."""
        db_path = os.path.join(PHOENIX_DIR, "v2", "phoenix_v2.db")
        return sqlite3.connect(db_path)

    def _ais_queue(self):
        """Orchestrator queue — pending and running sessions."""
        try:
            conn = self._ais_db()
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM orchestrator_queue ORDER BY priority ASC, scheduled_for ASC LIMIT 100"
            )
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            json_resp(self, 200, {"queue": rows})
        except Exception as e:
            json_resp(self, 500, {"error": str(e)})

    def _ais_sessions(self):
        """Sessions — optionally filter by ?status= running|completed|..."""
        try:
            conn = self._ais_db()
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            status_filter = qs.get("status", [None])[0]
            if status_filter:
                cur.execute(
                    "SELECT * FROM sessions WHERE status = ? ORDER BY created_at DESC LIMIT 100",
                    (status_filter,),
                )
            else:
                cur.execute(
                    "SELECT * FROM sessions ORDER BY created_at DESC LIMIT 100"
                )
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            json_resp(self, 200, {"sessions": rows})
        except Exception as e:
            json_resp(self, 500, {"error": str(e)})

    def _ais_pairings(self):
        """Agent pairings with health scores."""
        try:
            conn = self._ais_db()
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM agent_pairings ORDER BY last_session_at DESC LIMIT 200"
            )
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            json_resp(self, 200, {"pairings": rows})
        except Exception as e:
            json_resp(self, 500, {"error": str(e)})

    def _ais_health(self):
        """Per-agent welfare metrics."""
        try:
            conn = self._ais_db()
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM agent_health ORDER BY agent_id")
            rows = [dict(r) for r in cur.fetchall()]
            conn.close()
            json_resp(self, 200, {"health": rows})
        except Exception as e:
            json_resp(self, 500, {"error": str(e)})

    def _ais_stats(self):
        """Aggregate AIS v2 statistics."""
        try:
            conn = self._ais_db()
            cur = conn.cursor()
            stats = {}
            # session counts by status
            cur.execute(
                "SELECT status, COUNT(*) FROM sessions GROUP BY status"
            )
            stats["session_counts"] = {r[0]: r[1] for r in cur.fetchall()}
            # total pairings
            cur.execute("SELECT COUNT(*) FROM agent_pairings")
            stats["total_pairings"] = cur.fetchone()[0]
            # queue counts by status
            cur.execute(
                "SELECT status, COUNT(*) FROM orchestrator_queue GROUP BY status"
            )
            stats["queue_counts"] = {r[0]: r[1] for r in cur.fetchall()}
            # avg quality
            cur.execute(
                "SELECT AVG(quality_score) FROM sessions WHERE quality_score IS NOT NULL"
            )
            stats["avg_quality"] = cur.fetchone()[0]
            # health summary
            cur.execute(
                "SELECT growth_trajectory, COUNT(*) FROM agent_health GROUP BY growth_trajectory"
            )
            stats["growth_summary"] = {r[0]: r[1] for r in cur.fetchall()}
            conn.close()
            json_resp(self, 200, {"stats": stats})
        except Exception as e:
            json_resp(self, 500, {"error": str(e)})



    def _ais_session_detail(self, session_uuid):
        try:
            conn = self._ais_db()
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM sessions WHERE session_uuid = ?", (session_uuid,))
            row = cur.fetchone()
            if not row:
                conn.close()
                return json_resp(self, 404, {"error": "session not found"})
            session = dict(row)
            conn.close()
            json_resp(self, 200, {"session": session})
        except Exception as e:
            json_resp(self, 500, {"error": str(e)})

    def _ais_session_turns(self, session_uuid):
        try:
            conn = self._ais_db()
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute(
                "SELECT turn_number, speaker, content, thinking_trace, emotion_hint, latency_ms FROM session_turns WHERE session_uuid = ? ORDER BY turn_number",
                (session_uuid,)
            )
            turns = [dict(r) for r in cur.fetchall()]
            conn.close()
            json_resp(self, 200, {"turns": turns, "session_uuid": session_uuid})
        except Exception as e:
            json_resp(self, 500, {"error": str(e)})

if __name__ == "__main__":
    for name in AGENTS:
        load_soul(name)
    # Start MCP bridges — creative (minimax-mcp) and vision (minimax-coding-plan-mcp)
    try:
        from mcp_bridge import get_creative_bridge, get_vision_bridge

        ct = get_creative_bridge().list_tools()
        print(f"[chat] Creative bridge — {len(ct)} tools: {[t['name'] for t in ct]}")
    except Exception as e:
        print(f"[chat] Creative bridge FAILED: {e}")
    try:
        vt = get_vision_bridge().list_tools()
        print(f"[chat] Vision bridge — {len(vt)} tools: {[t['name'] for t in vt]}")
    except Exception as e:
        print(f"[chat] Vision bridge FAILED: {e}")
    server = HTTPServer((BIND, PORT), Handler)
    print(f"[chat] Phoenix Chat API listening on {BIND}:{PORT}")
    server.serve_forever()