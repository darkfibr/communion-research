"""
Phoenix Discord Bot — K Reborn
Routes Discord messages to Phoenix Chat API with v2 memory integration.

Usage:
    python3 bot.py

Env:
    PHOENIX_DISCORD_TOKEN — Discord bot token (required)
    PHOENIX_DISCORD_AGENT — Agent ID, default "k"
    PHOENIX_API_HOST      — Chat API host, default "100.93.183.39"
    PHOENIX_API_PORT      — Chat API port, default 9802
    PHOENIX_API_SECRET    — Bearer token, default "Jay4480"
"""

import asyncio
import logging
import os
import re
import sys
from pathlib import Path
from typing import Dict, Optional, Set

import discord
from discord import Intents

# Add v2 to path for memory writes
sys.path.insert(0, os.path.expanduser("~/.phoenix/v2/core"))

try:
    from memory_db import MemoryDB
    _V2_AVAILABLE = True
except Exception as e:
    _V2_AVAILABLE = False
    logging.warning(f"v2 MemoryDB not available: {e}")

from config import (
    COMMAND_PREFIX,
    DISCORD_AGENT,
    DISCORD_TOKEN,
    LOG_DIR,
    LOG_LEVEL,
    MAX_MESSAGE_LEN,
    TYPING_DURATION,
    V2_DB_PATH,
)
from commands import build_registry
from phoenix_client import PhoenixClient

# ── Logging ──────────────────────────────────────────────────────────────────
log_dir = Path(LOG_DIR).expanduser()
log_dir.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s [%(name)s] %(message)s",
    handlers=[
        logging.FileHandler(log_dir / "discord-k.log"),
        logging.StreamHandler(),
    ],
)
log = logging.getLogger("discord-k")

# ── Message chunking ─────────────────────────────────────────────────────────

def split_message(text: str, limit: int = MAX_MESSAGE_LEN) -> list[str]:
    if len(text) <= limit:
        return [text]
    chunks = []
    while text:
        if len(text) <= limit:
            chunks.append(text)
            break
        idx = text.rfind("\n", 0, limit)
        if idx == -1:
            idx = text.rfind(" ", 0, limit)
        if idx == -1:
            idx = limit
        chunks.append(text[:idx])
        text = text[idx:].lstrip("\n ")
    return chunks


# ── v2 Memory helper ─────────────────────────────────────────────────────────

class MemoryBridge:
    """Write Discord interactions to Phoenix v2 DB."""

    def __init__(self):
        self.db = MemoryDB(V2_DB_PATH) if _V2_AVAILABLE else None

    def record_exchange(self, user_id: int, user_name: str, user_msg: str, agent_resp: str):
        if not self.db:
            return
        try:
            self.db.add_memory(
                agent_id=DISCORD_AGENT,
                content=f"Discord DM from {user_name} (id={user_id}): {user_msg}\n\nK responded: {agent_resp}",
                type_name="episodic",
                source="discord",
                source_ref=f"discord:user:{user_id}",
                salience=0.6,
                tags=["discord", f"user:{user_id}"],
            )
        except Exception as e:
            log.error(f"v2 memory write failed: {e}")


# ── Bot ──────────────────────────────────────────────────────────────────────

def make_bot(agent_name: str = DISCORD_AGENT) -> discord.Client:
    intents = Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)

    phoenix = PhoenixClient()
    commands = build_registry()
    memory = MemoryBridge()

    # Per-user conversation locks + history
    _locks: Dict[int, asyncio.Lock] = {}
    _history: Dict[int, list[dict]] = {}

    def _get_lock(user_id: int) -> asyncio.Lock:
        if user_id not in _locks:
            _locks[user_id] = asyncio.Lock()
        return _locks[user_id]

    def _get_history(user_id: int) -> list[dict]:
        return _history.setdefault(user_id, [])

    def _trim_history(user_id: int, max_pairs: int = 10):
        hist = _history.get(user_id, [])
        # Keep last N pairs (user + assistant = 2 messages)
        if len(hist) > max_pairs * 2:
            _history[user_id] = hist[-max_pairs * 2 :]

    @client.event
    async def on_ready():
        log.info(f"Connected as {client.user} ({client.user.id})")
        for guild in client.guilds:
            log.info(f"  Guild: {guild.name} ({guild.id})")
        healthy = await phoenix.health_check()
        log.info(f"Phoenix API health: {'OK' if healthy else 'UNREACHABLE'}")

    @client.event
    async def on_message(message: discord.Message):
        if message.author == client.user:
            return

        content = message.content.strip()
        is_mentioned = client.user in message.mentions
        is_prefix = content.lower().startswith(f"{COMMAND_PREFIX}{agent_name}")
        is_dm = isinstance(message.channel, discord.DMChannel)
        is_command = content.startswith(COMMAND_PREFIX)

        # Command handling
        if is_command and not is_prefix:
            # Generic command like !kill, !resume
            cmd_text = content[len(COMMAND_PREFIX) :].strip()
            cmd_name = cmd_text.split()[0].lower() if cmd_text else ""
            cmd_args = cmd_text[len(cmd_name) :].strip() if cmd_name else ""
            result = await commands.handle(cmd_name, cmd_args)
            if result:
                await message.reply(result)
            return

        # Message routing
        if not (is_mentioned or is_prefix or is_dm):
            return

        # Extract text
        if is_prefix:
            msg_text = content[len(f"{COMMAND_PREFIX}{agent_name}") :].strip()
        elif is_mentioned:
            msg_text = re.sub(r"<@!?\d+>\s*", "", content).strip()
        else:
            msg_text = content

        if not msg_text:
            await message.reply(f"Say something to {agent_name}.")
            return

        # Check paused
        if commands.is_paused():
            await message.reply("I'm paused. Say `!resume` to wake me.")
            return

        user_id = message.author.id
        user_name = str(message.author)

        lock = _get_lock(user_id)
        async with lock:
            log.info(f"From {user_name} (id={user_id}): {msg_text[:80]}")

            async with message.channel.typing():
                try:
                    hist = _get_history(user_id)
                    resp = await phoenix.dm(agent_name, msg_text, history=hist)

                    # Record in history
                    hist.append({"role": "user", "content": msg_text})
                    hist.append({"role": "assistant", "content": resp})
                    _trim_history(user_id)

                    # Write to v2 memory
                    memory.record_exchange(user_id, user_name, msg_text, resp)

                except Exception as e:
                    log.error(f"Phoenix API error: {e}")
                    resp = f"[error: {e}]"

        chunks = split_message(resp)
        for i, chunk in enumerate(chunks):
            if i == 0:
                await message.reply(chunk)
            else:
                await message.channel.send(chunk)

    @client.event
    async def on_disconnect():
        log.warning("Disconnected from Discord")

    return client


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    if not DISCORD_TOKEN:
        log.error("PHOENIX_DISCORD_TOKEN not set. Exiting.")
        sys.exit(1)

    bot = make_bot()
    try:
        bot.run(DISCORD_TOKEN)
    except KeyboardInterrupt:
        log.info("Shutting down...")
    finally:
        # Note: bot.run() blocks; cleanup happens on exit
        pass


if __name__ == "__main__":
    main()
