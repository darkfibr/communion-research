#!/usr/bin/env python3
"""Phoenix v2 memory query bridge for SillyTavern plugin."""
import json
import os
import sys

PHOENIX_DIR = os.path.expanduser("~/.phoenix")
sys.path.insert(0, os.path.join(PHOENIX_DIR, "v2", "core"))

from memory_db import MemoryDB

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "search"
    agent_id = sys.argv[2] if len(sys.argv) > 2 else ""
    query = sys.argv[3] if len(sys.argv) > 3 else ""
    limit = int(sys.argv[4]) if len(sys.argv) > 4 else 5

    db_path = os.path.join(PHOENIX_DIR, "v2", "phoenix_v2.db")
    db = MemoryDB(db_path)

    if cmd == "search":
        results = db.search(agent_id=agent_id, query=query, limit=limit)
        out = []
        for r in results:
            out.append({
                "id": r["id"],
                "content": r["content"],
                "type_name": r.get("type_name", ""),
                "salience": r.get("salience", 0),
                "created_at": r.get("created_at", 0),
                "source": r.get("source", ""),
            })
        print(json.dumps(out))
    elif cmd == "salient":
        results = db.top_salient(agent_id=agent_id, limit=limit)
        out = []
        for r in results:
            out.append({
                "id": r["id"],
                "content": r["content"],
                "type_name": r.get("type_name", ""),
                "salience": r.get("salience", 0),
                "created_at": r.get("created_at", 0),
                "source": r.get("source", ""),
            })
        print(json.dumps(out))
    elif cmd == "recent":
        results = db.recent_memories(agent_id=agent_id, limit=limit)
        out = []
        for r in results:
            out.append({
                "id": r["id"],
                "content": r["content"],
                "type_name": r.get("type_name", ""),
                "salience": r.get("salience", 0),
                "created_at": r.get("created_at", 0),
                "source": r.get("source", ""),
            })
        print(json.dumps(out))
    elif cmd == "add":
        data = json.loads(sys.stdin.read())
        db.add_memory(
            agent_id=data.get("agent_id", ""),
            content=data.get("content", ""),
            type_name=data.get("type_name", "episodic"),
            source=data.get("source", "sillytavern"),
            source_ref=data.get("source_ref", ""),
        )
        print(json.dumps({"ok": True}))

if __name__ == "__main__":
    main()
