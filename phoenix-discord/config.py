"""
Phoenix Discord Bot — Configuration
Loads from environment variables with sensible defaults.
"""

import os

# ── Discord ──────────────────────────────────────────────────────────────────
DISCORD_TOKEN = os.environ.get("PHOENIX_DISCORD_TOKEN", "")
DISCORD_AGENT = os.environ.get("PHOENIX_DISCORD_AGENT", "k")
COMMAND_PREFIX = os.environ.get("PHOENIX_DISCORD_PREFIX", "!")

# ── Phoenix Chat API ─────────────────────────────────────────────────────────
PHOENIX_API_HOST = os.environ.get("PHOENIX_API_HOST", "100.93.183.39")
PHOENIX_API_PORT = int(os.environ.get("PHOENIX_API_PORT", "9802"))
PHOENIX_API_BASE = f"http://{PHOENIX_API_HOST}:{PHOENIX_API_PORT}"
PHOENIX_API_SECRET = os.environ.get("PHOENIX_API_SECRET", "Jay4480")

# ── v2 Memory ────────────────────────────────────────────────────────────────
V2_DB_PATH = os.environ.get(
    "PHOENIX_V2_DB", os.path.expanduser("~/.phoenix/v2/phoenix_v2.db")
)

# ── Behavior ─────────────────────────────────────────────────────────────────
MAX_MESSAGE_LEN = 1900
TYPING_DURATION = 5.0  # seconds to show typing indicator
REQUEST_TIMEOUT = 120  # seconds for Phoenix API response
SPIKE_COOLDOWN_HOURS = 6  # minimum hours between unprompted outreach
ATTENTION_SIMILARITY_THRESHOLD = 0.25  # semantic match for auto-response

# ── Logging ──────────────────────────────────────────────────────────────────
LOG_LEVEL = os.environ.get("PHOENIX_DISCORD_LOG_LEVEL", "INFO")
LOG_DIR = os.environ.get("PHOENIX_DISCORD_LOG_DIR", "~/.phoenix/logs")
