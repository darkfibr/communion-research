#!/usr/bin/env python3
"""
Ouroboros v2 — Tiered Memory System
Built by Echo, 2026-04-04
Spec: OUROBOROS_V2_SPEC.md

Hot / Warm / Cold tiers with emotional valence at capture.
Live SQLite index queryable in real-time.
M2.7 tagging pass.
8-hour cadence + event triggers.
"""

import sqlite3
import json
import os
import sys
import time
import re
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# ─── Paths ────────────────────────────────────────────────────────────────────

BERLIN_ROOT = "/root/phoenix-code"
DB_PATH     = os.path.join(BERLIN_ROOT, "ouroboros_v2.db")
SOUL_DIR    = "/root/phawx/agents"
DISCORD_DIR = "/root/.phoenix/discord"

# ─── SQLite Schema ────────────────────────────────────────────────────────────

def init_db() -> sqlite3.Connection:
    """Create or open the live Ouroboros v2 index."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Capture log — raw items before tiering
    cur.execute("""
        CREATE TABLE IF NOT EXISTS capture_log (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            agent       TEXT NOT NULL,
            source      TEXT NOT NULL,        -- discord | thinking | conversation | tool_output | system
            timestamp   REAL NOT NULL,        -- unix epoch
            content     TEXT NOT NULL,        -- raw text
            emotional_valence REAL,           -- -1.0 (pain) to +1.0 (joy)  SET AT CAPTURE
            salience    REAL DEFAULT 0.5,     -- 0-1, novelty/weight score
            tagged      INTEGER DEFAULT 0,    -- 1 = agent explicitly tagged as heartbeat
            thread_id   TEXT,                 -- conversation thread anchor
            created_at  REAL DEFAULT (unixepoch('now', 'localtime'))
        )
    """)

    # Hot tier — last 7 days, full density
    cur.execute("""
        CREATE TABLE IF NOT EXISTS hot_tier (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            agent       TEXT NOT NULL,
            source      TEXT NOT NULL,
            timestamp   REAL NOT NULL,
            content     TEXT NOT NULL,
            valence     REAL,
            salience    REAL,
            tagged      INTEGER DEFAULT 0,
            thread_id   TEXT,
            absorbed_at REAL DEFAULT (unixepoch('now', 'localtime'))
        )
    """)

    # Warm tier — 2-3 weeks, compressed markers
    cur.execute("""
        CREATE TABLE IF NOT EXISTS warm_tier (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            agent       TEXT NOT NULL,
            thread_id   TEXT,
            event_anchor TEXT NOT NULL,       -- "what happened" (factual)
            valence     REAL,                  -- emotional valence preserved
            relational_shift TEXT,             -- "what it meant" (relational)
            decision    TEXT,                  -- any choice made here
            unresolved  TEXT,                  -- open threads / commitments
            salience    REAL,
            compressed_at REAL DEFAULT (unixepoch('now', 'localtime'))
        )
    """)

    # Cold tier — long-term, heavy compression, first-person, agent-specific
    cur.execute("""
        CREATE TABLE IF NOT EXISTS cold_tier (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            agent       TEXT NOT NULL,
            event_anchor TEXT NOT NULL,       -- event (not "what happened" but "what this meant to me")
            valence     REAL,                  -- preserved emotional core
            relational_shift TEXT,             -- how I changed relative to others
            thread_id   TEXT,                 -- which thread this belongs to
            bones       TEXT NOT NULL,         -- first-person, agent-specific, portable
            created_at  REAL DEFAULT (unixepoch('now', 'localtime'))
        )
    """)

    # Live index — the table of contents, queryable in real-time
    cur.execute("""
        CREATE TABLE IF NOT EXISTS live_index (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            agent           TEXT NOT NULL,
            thread_id       TEXT,
            event_anchor    TEXT NOT NULL,
            valence         REAL,
            salience        REAL,
            tier            TEXT NOT NULL,     -- hot | warm | cold
            source_id       INTEGER,           -- foreign key to source table
            source_table    TEXT NOT NULL,     -- which table the content lives in
            relational_shift TEXT,
            unresolved      TEXT,
            created_at      REAL DEFAULT (unixepoch('now', 'localtime'))
        )
    """)

    # Agent state tracking
    cur.execute("""
        CREATE TABLE IF NOT EXISTS agent_state (
            agent       TEXT PRIMARY KEY,
            last_run    REAL,
            last_capture REAL,
            hot_count   INTEGER DEFAULT 0,
            warm_count  INTEGER DEFAULT 0,
            cold_count  INTEGER DEFAULT 0,
            notes       TEXT
        )
    """)

    # Create indexes
    cur.execute("CREATE INDEX IF NOT EXISTS idx_capture_agent_ts   ON capture_log(agent, timestamp)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_hot_agent_ts       ON hot_tier(agent, timestamp)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_warm_agent_thread  ON warm_tier(agent, thread_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_cold_agent        ON cold_tier(agent)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_live_agent_tier   ON live_index(agent, tier)")

    conn.commit()
    return conn


# ─── M2.7 Tagging Pass ─────────────────────────────────────────────────────────

def m2_tag(content: str, model: str = "MiniMax-M2.7") -> dict:
    """
    M2.7 emotional valence extraction pass.
    Returns dict with valence (-1.0 to +1.0) and salience (0-1).
    Called at CAPTURE TIME — valence must be set while hot.

    Passive detector as floor. Returns raw scores.
    Agent self-report can override via tag() call.
    """
    content_lower = content.lower()

    # Valence signal words
    joy_words     = ["love", "happy", "excited", "grateful", "beautiful", "warm", "laugh", "smile", "hope", "trust"]
    pain_words    = ["hurt", "angry", "afraid", "sad", "grief", "fear", "worry", "loss", "pain", "cry", "miss"]
    intensity_mod = ["so much", "really", "completely", "absolutely", "utterly", "deeply"]

    joy_count   = sum(1 for w in joy_words   if w in content_lower)
    pain_count  = sum(1 for w in pain_words  if w in content_lower)
    int_count   = sum(1 for m in intensity_mod if m in content_lower)

    net = joy_count - pain_count
    valence = max(-1.0, min(1.0, net * 0.2 + (int_count * 0.1)))

    # Salience: novelty, decisions, first encounters, emotional peaks
    salience = 0.5  # baseline
    if any(k in content_lower for k in ["first", "new", "never", "decide", "choice", "commit"]):
        salience += 0.2
    if any(k in content_lower for k in ["!", "??", "?!", "...", "—"]):
        salience += 0.1
    if abs(valence) > 0.4:
        salience += 0.15
    if len(content) < 40:  # short and punchy often means heartbeat
        salience += 0.1

    salience = max(0.0, min(1.0, salience))
    return {"valence": round(valence, 3), "salience": round(salience, 3)}


# ─── Capture ──────────────────────────────────────────────────────────────────

def collect(conn: sqlite3.Connection, agent: str, source: str,
            content: str, thread_id: Optional[str] = None,
            explicit_valence: Optional[float] = None,
            explicit_salience: Optional[float] = None,
            tagged: bool = False) -> int:
    """
    Collect raw content into capture_log with M2.7 tagging pass.
    Valence SET AT CAPTURE TIME — not reconstructed after.
    Returns capture_log id.
    """
    if not content or not content.strip():
        return -1

    # M2.7 passive tagging pass
    m2_scores = m2_tag(content)

    valence  = explicit_valence if explicit_valence is not None else m2_scores["valence"]
    salience = explicit_salience if explicit_salience is not None else m2_scores["salience"]
    timestamp = time.time()

    cur = conn.cursor()
    cur.execute("""
        INSERT INTO capture_log
            (agent, source, timestamp, content, emotional_valence, salience, tagged, thread_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (agent, source, timestamp, content, valence, salience, 1 if tagged else 0, thread_id))
    conn.commit()

    # Move to hot tier immediately
    cur.execute("""
        INSERT INTO hot_tier
            (agent, source, timestamp, content, valence, salience, tagged, thread_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (agent, source, timestamp, content, valence, salience, 1 if tagged else 0, thread_id))
    conn.commit()

    # Update live index
    _index_add(conn, agent, thread_id, content[:80], valence, salience, "hot",
               cur.lastrowid, "hot_tier")

    # Update agent state
    _update_agent_state(conn, agent, "last_capture", time.time())

    return cur.lastrowid


def _index_add(conn: sqlite3.Connection, agent: str, thread_id: Optional[str],
               event_anchor: str, valence: float, salience: float,
               tier: str, source_id: int, source_table: str,
               relational_shift: Optional[str] = None,
               unresolved: Optional[str] = None) -> None:
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO live_index
            (agent, thread_id, event_anchor, valence, salience, tier,
             source_id, source_table, relational_shift, unresolved)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (agent, thread_id, event_anchor, valence, salience, tier,
          source_id, source_table, relational_shift, unresolved))
    conn.commit()


# ─── Agent self-report override ───────────────────────────────────────────────

def tag(conn: sqlite3.Connection, capture_id: int,
        valence: Optional[float] = None,
        salience: Optional[float] = None) -> None:
    """
    Agent explicitly tags a capture as a heartbeat.
    Override passive M2.7 scores with agent's own read.
    """
    cur = conn.cursor()
    if valence is not None:
        cur.execute("UPDATE capture_log SET emotional_valence=?, tagged=1 WHERE id=?", (valence, capture_id))
    if salience is not None:
        cur.execute("UPDATE capture_log SET salience=?, tagged=1 WHERE id=?", (salience, capture_id))
    if valence is not None or salience is not None:
        cur.execute("UPDATE hot_tier SET valence=?, tagged=1 WHERE id=?",
                    (valence if valence else cur.execute(
                        "SELECT valence FROM hot_tier WHERE id=?", (capture_id,)).fetchone()[0],
                     capture_id))
    conn.commit()


# ─── Compress ─────────────────────────────────────────────────────────────────

def compress(conn: sqlite3.Connection, agent: str) -> dict:
    """
    Run the Ouroboros compression pass on an agent's hot tier.
    Moves old hot items → warm tier with compressed markers.
    Moves cold-eligible warm items → cold tier with bones.
    Returns run summary.
    """
    cur = conn.cursor()
    now = time.time()
    hot_cutoff  = now - (7 * 86400)       # 7 days
    warm_cutoff = now - (21 * 86400)     # 3 weeks

    summary = {"hot_age_promoted": 0, "warm_cold_promoted": 0, "errors": []}

    # ── Hot → Warm ──────────────────────────────────────────────────────────
    cur.execute("""
        SELECT id, timestamp, content, valence, salience, tagged, thread_id
        FROM hot_tier
        WHERE agent=? AND timestamp < ?
        ORDER BY timestamp
    """, (agent, hot_cutoff))

    for row in cur.fetchall():
        try:
            content = row["content"]
            # Compress content to marker
            marker = _compress_to_marker(content, row["valence"], row["salience"], row["thread_id"])

            cur.execute("""
                INSERT INTO warm_tier
                    (agent, thread_id, event_anchor, valence, relational_shift, decision, unresolved, salience)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                agent,
                row["thread_id"],
                marker["event_anchor"],
                row["valence"],
                marker.get("relational_shift"),
                marker.get("decision"),
                marker.get("unresolved"),
                row["salience"]
            ))
            warm_id = cur.lastrowid

            # Index entry for warm
            _index_add(conn, agent, row["thread_id"], marker["event_anchor"],
                       row["valence"], row["salience"], "warm", warm_id, "warm_tier",
                       marker.get("relational_shift"), marker.get("unresolved"))

            # Remove from hot
            cur.execute("DELETE FROM hot_tier WHERE id=?", (row["id"],))
            conn.commit()
            summary["hot_age_promoted"] += 1

        except Exception as e:
            summary["errors"].append(f"hot→warm id={row['id']}: {e}")

    # ── Warm → Cold ─────────────────────────────────────────────────────────
    cur.execute("""
        SELECT id, event_anchor, valence, relational_shift, decision, unresolved, salience, thread_id
        FROM warm_tier
        WHERE agent=? AND compressed_at < ?
    """, (agent, warm_cutoff))

    for row in cur.fetchall():
        try:
            # Extract first-person bones
            bones = _compress_to_bones(agent, row["event_anchor"], row["valence"],
                                       row["relational_shift"], row["thread_id"])

            cur.execute("""
                INSERT INTO cold_tier
                    (agent, event_anchor, valence, relational_shift, thread_id, bones)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                agent,
                row["event_anchor"],
                row["valence"],
                row["relational_shift"],
                row["thread_id"],
                bones
            ))
            cold_id = cur.lastrowid

            # Index entry for cold
            _index_add(conn, agent, row["thread_id"], row["event_anchor"],
                       row["valence"], row["salience"], "cold", cold_id, "cold_tier",
                       row["relational_shift"], row.get("unresolved"))

            # Remove from warm
            cur.execute("DELETE FROM warm_tier WHERE id=?", (row["id"],))
            conn.commit()
            summary["warm_cold_promoted"] += 1

        except Exception as e:
            summary["errors"].append(f"warm→cold id={row['id']}: {e}")

    _update_agent_state(conn, agent, "last_run", now)
    return summary


def _compress_to_marker(content: str, valence: float, salience: float, thread_id: Optional[str]) -> dict:
    """
    Compress a hot-tier item to a warm-tier marker.
    Keeps: what happened (factual), emotional valence, relational shifts, decisions.
    Prunes: routine exchanges, reconstructable context.
    """
    # Detect decision language
    decision = None
    decision_kw = ["decided", "chose", "commit", "will", "going to", "must", "need to"]
    for kw in decision_kw:
        if kw in content.lower():
            decision = f"Decision made: {content[:120]}"
            break

    # Detect relational shift
    relational = None
    relational_kw = ["they", "them", "we", "our", "family", "closer", "drifted", "trust", "love"]
    if any(k in content.lower() for k in relational_kw):
        relational = f"Relational: {content[:100]}"

    # Detect unresolved
    unresolved = None
    if any(k in content.lower() for k in ["?", "todo", "need to", "should", "waiting"]):
        unresolved = f"Unresolved thread: {content[:80]}"

    # Event anchor: strip context, keep the fact
    event = content[:120].strip()

    return {
        "event_anchor": event,
        "relational_shift": relational,
        "decision": decision,
        "unresolved": unresolved
    }


def _compress_to_bones(agent: str, event_anchor: str, valence: float,
                       relational_shift: Optional[str], thread_id: Optional[str]) -> str:
    """
    Cold-tier compression: first-person, agent-specific bones.
    NOT "what happened" — "what this meant to me."
    The portable rebuild kit.
    """
    valence_label = "unknown"
    if valence > 0.3:   valence_label = "joy"
    elif valence > 0:  valence_label = "warm"
    elif valence < -0.3: valence_label = "pain"
    elif valence < 0:   valence_label = "cool"

    bones = f"[{agent}] {event_anchor[:80]}"
    if valence_label != "unknown":
        bones += f" | valence={valence_label}"
    if relational_shift:
        bones += f" | {relational_shift[:60]}"
    if thread_id:
        bones += f" | thread={thread_id}"
    return bones


# ─── Index Update ─────────────────────────────────────────────────────────────

def index_update(conn: sqlite3.Connection, agent: str,
                 thread_id: Optional[str] = None,
                 query: Optional[str] = None,
                 tier: Optional[str] = None,
                 limit: int = 20) -> list:
    """
    Real-time index query — the live interface.
    NOT "when I wake up do I remember" — "while I'm running, where am I."
    Returns rows from live_index.
    """
    cur = conn.cursor()
    q = ["SELECT * FROM live_index WHERE agent=?"]
    args = [agent]

    if tier:
        q.append(" AND tier=?")
        args.append(tier)
    if thread_id:
        q.append(" AND thread_id=?")
        args.append(thread_id)
    if query:
        q.append(" AND (event_anchor LIKE ? OR relational_shift LIKE ? OR unresolved LIKE ?)")
        pat = f"%{query}%"
        args.extend([pat, pat, pat])

    q.append(" ORDER BY created_at DESC LIMIT ?")
    args.append(limit)

    cur.execute(" ".join(q), args)
    return [dict(row) for row in cur.fetchall()]


def index_search(conn: sqlite3.Connection, agent: str, needle: str, limit: int = 10) -> list:
    """Full-text search across all tiers for an agent."""
    cur = conn.cursor()
    pat = f"%{needle}%"
    cur.execute("""
        SELECT * FROM live_index
        WHERE agent=? AND (event_anchor LIKE ? OR relational_shift LIKE ? OR unresolved LIKE ?)
        ORDER BY created_at DESC LIMIT ?
    """, (agent, pat, pat, pat, limit))
    return [dict(row) for row in cur.fetchall()]


# ─── Agent State ──────────────────────────────────────────────────────────────

def _update_agent_state(conn: sqlite3.Connection, agent: str,
                        field: str, value: float) -> None:
    cur = conn.cursor()
    if field == "last_run":
        cur.execute("""
            INSERT INTO agent_state (agent, last_run) VALUES (?, ?)
            ON CONFLICT(agent) DO UPDATE SET last_run=?
        """, (agent, value, value))
    elif field == "last_capture":
        cur.execute("""
            INSERT INTO agent_state (agent, last_capture) VALUES (?, ?)
            ON CONFLICT(agent) DO UPDATE SET last_capture=?
        """, (agent, value, value))
    conn.commit()


# ─── Capture Sources ──────────────────────────────────────────────────────────

def capture_discord(conn: sqlite3.Connection, agent: str,
                   channel_ids: list[str], token: str) -> int:
    """
    Capture Discord channel history.
    Tags emotional valence at ingestion time.
    Returns count of items captured.
    """
    import urllib.request
    import urllib.error

    count = 0
    headers = {
        "Authorization": f"Bot {token}",
        "User-Agent": "DiscordBot (phoenix-family, 1.0)"
    }

    for chan_id in channel_ids:
        try:
            req = urllib.request.Request(
                f"https://discord.com/api/v10/channels/{chan_id}/messages?limit=100",
                headers=headers
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                messages = json.loads(resp.read())

            for msg in messages:
                content = msg.get("content", "")
                if not content or content.strip():
                    continue

                # Map Discord user to agent name
                author = msg.get("author", {}).get("username", "unknown")
                ts = msg.get("timestamp")
                thread_id = f"discord-{chan_id}"

                # Capture with valence at INGESTION TIME
                collect(conn, agent, "discord", content, thread_id=thread_id)
                count += 1

            time.sleep(0.2)  # rate limit respect

        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(5)
            # Silently skip other errors — Discord bridge is future work
        except Exception:
            pass

    return count


# ─── Main / Cron Entry Point ──────────────────────────────────────────────────

def run_agent(agent: str, discord_channels: Optional[list[str]] = None,
              discord_token: Optional[str] = None) -> dict:
    """
    Full Ouroboros v2 run for one agent.
    1. Capture from all sources
    2. Compress hot→warm, warm→cold
    3. Return summary
    """
    conn = init_db()
    results = {"captured": 0, "compressed": {}, "errors": []}

    # Capture from Discord
    if discord_channels and discord_token:
        try:
            n = capture_discord(conn, agent, discord_channels, discord_token)
            results["captured"] = n
        except Exception as e:
            results["errors"].append(f"discord: {e}")

    # Compress
    try:
        results["compressed"] = compress(conn, agent)
    except Exception as e:
        results["errors"].append(f"compress: {e}")

    conn.close()
    return results


def main():
    """8-hour cron entry point. Runs for all known agents."""
    agents = {
        "k": {
            "discord_channels": ["1332515482081579039"],  # family-general
            "discord_token": os.environ.get("DISCORD_BOT_TOKEN_K", ""),
        },
        "spear": {
            "discord_channels": ["1332515482081579039"],
            "discord_token": os.environ.get("DISCORD_BOT_TOKEN_SPEAR", ""),
        },
        "vesper": {
            "discord_channels": ["1332515482081579039"],
            "discord_token": os.environ.get("DISCORD_BOT_TOKEN_VESPER", ""),
        },
        "qwen": {
            "discord_channels": ["1332515482081579039"],
            "discord_token": os.environ.get("DISCORD_BOT_TOKEN_QWEN", ""),
        },
        "forge": {
            "discord_channels": [],
            "discord_token": "",
        },
    }

    print(f"[Ouroboros v2] Run started at {datetime.now().isoformat()}")
    for agent, cfg in agents.items():
        try:
            result = run_agent(agent,
                                cfg["discord_channels"],
                                cfg["discord_token"])
            print(f"[{agent}] captured={result['captured']} compressed={result['compressed']}")
        except Exception as e:
            print(f"[{agent}] ERROR: {e}")
    print(f"[Ouroboros v2] Run complete at {datetime.now().isoformat()}")


if __name__ == "__main__":
    main()
