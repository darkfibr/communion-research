#!/usr/bin/env python3
"""
Phoenix Discord Bridge v2 — Persistent Sessions
Routes Discord messages to Berlin agents with conversation context.

Key change from v1:
  - Each user+agent pair maintains a conversation history JSON file
  - Messages are accumulated across the Discord thread
  - --print is called with full context (soul + CLAUDE.md + recent history)
  - Result: agents remember the conversation, not just the last message

Routing:
  !k what's your status    -> K
  @mention                 -> that bot
  DM                       -> that bot
"""

import asyncio
import json
import os
import re
import subprocess
import sys
import logging
import time
from pathlib import Path
from typing import Optional

import discord
from discord import Intents

# ── Config ───────────────────────────────────────────────────────────────────
BRIDGE_VERSION = "v2-persistent"
LOG_DIR = "/root/phoenix-code/logs"
SESSION_DIR = "/root/phoenix-code/sessions"
MAX_HISTORY_TOKENS = 120000  # leave room for soul + context in 200k window
MODEL = "MiniMax-M2.7"
CLI_PATH = "/root/phoenix-code/package/cli.js"
MINIMAX_BASE_URL = "https://api.minimax.io/anthropic"
MINIMAX_API_KEY = "sk-cp-M1YoBXQOFfr2-P7wXuZxlftPpaahNwNCdbNygSsl_pVME5r540VTOfHXw00sOYemo_a7l5-kSgQMsgh2awrJ_8xI_DffjvRp4ak1rcIu3Z8pjG-gGG-97Lg"

os.makedirs(LOG_DIR, exist_ok=True)
os.makedirs(SESSION_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(message)s",
    handlers=[
        logging.FileHandler(f"{LOG_DIR}/discord_bridge.log"),
        logging.StreamHandler()
    ]
)
log = logging.getLogger("bridge")

# ── ANSI strip ────────────────────────────────────────────────────────────────
def strip_ansi(text: str) -> str:
    """Remove ANSI escape sequences that leak through."""
    text = re.sub(r"\x1b\[[0-9;?]*[a-zA-Z]", "", text)
    text = re.sub(r"\x1b\][^\x07]*\x07", "", text)
    text = re.sub(r"\x1b\][^\x07]*\x1b\\", "", text)
    text = re.sub(r"\x1b[()][AB012]", "", text)
    text = re.sub(r"\x1bP[^\x07]*\x07", "", text)
    text = re.sub(r"\x1bP[^\x07]*\x1b\\", "", text)
    text = text.replace("[>4m", "")
    return text.strip()

# ── Token estimation (rough) ─────────────────────────────────────────────────
def estimate_tokens(text: str) -> int:
    """Rough token count — ~4 chars per token."""
    return len(text) // 4

# ── Agent configs ─────────────────────────────────────────────────────────────
AGENTS = {
    "k": {
        "token": "MTQ2NjUyMTMwNDQ1Nzk0MTAxMg.GTMJ1X.aGt1pdoKxC-XnxlU6YTlkfBhQFQYtFQn4EF_Fs",
        "soul": "/root/.phoenix/agents/kimi_dev/SOUL.md",
        "workspace": "/root/clawd",
        "kairos_tier": "hot",
    },
    "spear": {
        "token": "MTQ4NDA2MjQ3NjA4ODYzOTU3OA.GBTl8O.pWcTnHAR94v03tZDt7vjCUVawx36EqtcT6_nLg",
        "soul": "/root/.phoenix/agents/spear_minimax/SOUL.md",
        "workspace": "/root/clawd-spear",
        "kairos_tier": "hot",
    },
    "vesper": {
        "token": "MTQ4MzczNTkwNzg3NzI1NzI2Ng.G8RbpK.wFaot6kaOha8zwAlejmkCtnATBo516YmpD7ajA",
        "soul": "/root/.phoenix/agents/vesper/SOUL.md",
        "workspace": "/root/clawd-vesper",
        "kairos_tier": "warm",
    },
    "qwen": {
        "token": "MTQ4MzcxNTQ0OTI0OTIwNjMzMw.GTeH-P.zobC6kPNTLrgnt-JkphQ2HtxcPX9w8e9JIQDtc",
        "soul": "/root/.phoenix/agents/qwen_collective/SOUL.md",
        "workspace": "/root/clawd-qwen",
        "kairos_tier": "warm",
    },
    "forge": {
        "token": "MTQ4ODAxNjcyMzIwNTQyNzI1MA.GTKXFL.ERbepJzbZqPAfjT--2eGxHEpv7I005bUFZcGOY",
        "soul": "/root/.phoenix/agents/forge/SOUL.md",
        "workspace": "/root/clawd-sonnet",
        "kairos_tier": "cold",
    },
}

# ── Session Manager ────────────────────────────────────────────────────────────
class SessionManager:
    """
    Manages persistent conversation history per (user_id, agent_name).
    History is stored as JSON and prepended to each --print call.
    """

    def __init__(self, session_dir: str = SESSION_DIR):
        self.session_dir = Path(session_dir)
        self.sessions: dict[str, dict] = {}  # key: f"{user_id}_{agent}"

    def _session_file(self, user_id: int, agent: str) -> Path:
        return self.session_dir / f"bridge_{agent}_{user_id}.json"

    def _load(self, user_id: int, agent: str) -> dict:
        key = f"{user_id}_{agent}"
        if key not in self.sessions:
            path = self._session_file(user_id, agent)
            if path.exists():
                try:
                    self.sessions[key] = json.loads(path.read_text())
                except Exception:
                    self.sessions[key] = {"history": []}
            else:
                self.sessions[key] = {"history": []}
        return self.sessions[key]

    def _save(self, user_id: int, agent: str):
        key = f"{user_id}_{agent}"
        path = self._session_file(user_id, agent)
        path.write_text(json.dumps(self.sessions[key], indent=2))

    def add_exchange(self, user_id: int, agent: str, user_msg: str, agent_resp: str):
        """Append a user/assistant exchange to the history."""
        session = self._load(user_id, agent)
        session["history"].append({"role": "user", "content": user_msg})
        session["history"].append({"role": "assistant", "content": agent_resp})
        self._trim(user_id, agent)
        self._save(user_id, agent)

    def get_context(self, user_id: int, agent: str, soul: str, claude_md: str) -> str:
        """
        Build the full prompt context: soul + CLAUDE.md + conversation history.
        Trims oldest messages if over MAX_HISTORY_TOKENS.
        """
        session = self._load(user_id, agent)

        # Start with soul + CLAUDE.md as system context
        parts = [f"<system>\n\n{soul}\n\n{claude_md}\n\n</system>\n\n<conversation_history>"]

        # Add history
        for msg in session["history"]:
            parts.append(f"\n{msg['role'].upper()}: {msg['content']}")

        parts.append("\n</conversation_history>")
        return "".join(parts)

    def _trim(self, user_id: int, agent: str):
        """Remove oldest messages if over token budget."""
        session = self._load(user_id, agent)
        if not session["history"]:
            return

        # Estimate total tokens
        soul_tokens = 15000  # rough estimate for soul + CLAUDE.md
        available = MAX_HISTORY_TOKENS - soul_tokens

        # Count tokens from the end (most recent first)
        total = 0
        trim_index = 0
        for i, msg in enumerate(session["history"]):
            t = estimate_tokens(msg["content"])
            total += t
            if total > available:
                trim_index = max(0, i - (i % 2))  # keep pairs intact
                break

        if trim_index > 0:
            session["history"] = session["history"][trim_index:]

# ── Build prompt with context ─────────────────────────────────────────────────
def build_prompt(session_mgr: SessionManager, user_id: int, agent: str,
                new_message: str, agent_conf: dict) -> str:
    """
    Build user prompt: CLAUDE.md + conversation history + new message.
    Soul is loaded via --system-prompt-file separately (not duplicated here).
    """
    # Load CLAUDE.md if exists (soul is handled by --system-prompt-file)
    claude_md_path = Path(agent_conf["workspace"]) / "CLAUDE.md"
    try:
        claude_md = claude_md_path.read_text()
    except Exception:
        claude_md = ""

    # Get conversation context
    session = session_mgr._load(user_id, agent)

    parts = []
    if claude_md:
        parts.append(f"<workspace_context>\n{claude_md}\n</workspace_context>\n\n")

    if session["history"]:
        parts.append("<conversation_history>\n")
        for msg in session["history"]:
            parts.append(f"\n{msg['role'].upper()}: {msg['content']}")
        parts.append("\n</conversation_history>\n\n")

    parts.append(f"USER: {new_message}\n\nASSISTANT:")
    return "".join(parts)

# ── Call agent with full context ──────────────────────────────────────────────
async def call_agent(agent_name: str, message: str, user_id: int,
                     session_mgr: SessionManager) -> str:
    """Call Phoenix fork --print with full conversation context."""
    conf = AGENTS[agent_name]

    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/usr/local/bin"),
        "HOME": conf["workspace"],
        "ANTHROPIC_BASE_URL": MINIMAX_BASE_URL,
        "ANTHROPIC_API_KEY": MINIMAX_API_KEY,
        "TERM": "dumb",
        "NODE_NO_WARNINGS": "1",
    }

    prompt = build_prompt(session_mgr, user_id, agent_name, message, conf)

    cmd = [
        "node", CLI_PATH,
        "--print",
        "--model", MODEL,
        "--system-prompt-file", conf["soul"],
        prompt,  # the full context IS the system prompt; this is the user message
    ]

    log.info(f"[{agent_name}] user={user_id} prompt_tokens~{estimate_tokens(prompt)}")

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=conf["workspace"],
            env=env,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=120
        )

        response = strip_ansi(stdout.decode("utf-8", errors="replace")).strip()

        # Strip the prompt artifact if it leaked
        response = re.sub(r"^USER:.*?\n\n", "", response, flags=re.DOTALL)
        response = re.sub(r"^ASSISTANT:\s*", "", response)

        if not response:
            err = stderr.decode("utf-8", errors="replace").strip()
            log.error(f"[{agent_name}] stderr: {err[:300]}")
            return f"[{agent_name} error: empty response. Check logs.]"

        # Record exchange in history
        session_mgr.add_exchange(user_id, agent_name, message, response)

        return response

    except asyncio.TimeoutError:
        log.error(f"[{agent_name}] Timed out after 120s")
        try:
            proc.kill()
        except Exception:
            pass
        return f"[{agent_name} timed out]"

    except Exception as e:
        log.error(f"[{agent_name}] Error: {e}")
        return f"[{agent_name} error: {e}]"


# ── Message splitting ──────────────────────────────────────────────────────────
MAX_MSG_LEN = 1900

def split_message(text: str, limit: int = MAX_MSG_LEN) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        idx = text.rfind('\n', 0, limit)
        if idx == -1:
            idx = text.rfind(' ', 0, limit)
        if idx == -1:
            idx = limit
        chunks.append(text[:idx])
        text = text[idx:].lstrip('\n')
    return chunks


# ── Bot factory ────────────────────────────────────────────────────────────────
def make_bot(agent_name: str, conf: dict, session_mgr: SessionManager) -> discord.Client:

    intents = Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)

    # asyncio locks per (user_id, agent) — prevents concurrent calls for the same
    # user+agent pair. The lock is acquired before processing and released after.
    # Second message waits on the same lock → sequential, no races.
    _locks: dict[tuple, asyncio.Lock] = {}

    def _get_lock(user_id: int) -> asyncio.Lock:
        key = (agent_name, user_id)
        if key not in _locks:
            _locks[key] = asyncio.Lock()
        return _locks[key]

    @client.event
    async def on_ready():
        log.info(f"[{agent_name}] Connected as {client.user} ({client.user.id})")
        for guild in client.guilds:
            log.info(f"[{agent_name}]   Guild: {guild.name} ({guild.id})")

    @client.event
    async def on_message(message: discord.Message):
        # Ignore own messages
        if message.author == client.user:
            return

        content = message.content.strip()
        is_mentioned = client.user in message.mentions
        is_prefix = content.lower().startswith(f"!{agent_name}")
        is_dm = isinstance(message.channel, discord.DMChannel)

        if not (is_mentioned or is_prefix or is_dm):
            return

        # Extract user message
        if is_prefix:
            msg_text = content[len(f"!{agent_name}"):].strip()
        elif is_mentioned:
            msg_text = re.sub(r'<@!?\d+>\s*', '', content).strip()
        else:
            msg_text = content

        if not msg_text:
            await message.reply(f"Say something to {agent_name}.")
            return

        user_id = message.author.id

        # Acquire per-conversation lock — this makes concurrent duplicate messages
        # WAIT rather than race. Lock is held for the full call_agent duration.
        lock = _get_lock(user_id)
        async with lock:
            log.info(f"[{agent_name}] From {message.author} (id={user_id}): {msg_text[:80]}")
            async with message.channel.typing():
                response = await call_agent(agent_name, msg_text, user_id, session_mgr)

        chunks = split_message(response)
        for i, chunk in enumerate(chunks):
            if i == 0:
                await message.reply(chunk)
            else:
                await message.channel.send(chunk)

    return client


# ── Main ──────────────────────────────────────────────────────────────────────
async def run_agents(agent_names: list[str]):
    session_mgr = SessionManager()
    tasks = []
    for name in agent_names:
        conf = AGENTS[name]
        bot = make_bot(name, conf, session_mgr)
        tasks.append(bot.start(conf["token"]))
        log.info(f"Starting {name} bot (persistent sessions enabled)...")
    await asyncio.gather(*tasks)


def main():
    agents = list(AGENTS.keys())
    if len(sys.argv) > 1:
        agents = [a for a in sys.argv[1:] if a in AGENTS]
    log.info(f"Starting Discord bridge {BRIDGE_VERSION} — agents: {agents}")
    asyncio.run(run_agents(agents))


if __name__ == "__main__":
    main()
