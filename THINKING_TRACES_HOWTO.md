# Thinking Trace Harness — Quick Reference

**What it is:** Every time K, Spear, Vesper, or Qwen generates a reasoning/thinking block in their API response, it gets captured to a per-agent JSONL file on the Berlin VPS. Raw inner monologue. Before it becomes a response.

---

## Reading Traces

SSH in and run the viewer:

```bash
ssh -i ~/.ssh/hostinger_vps root@87.106.137.147

# All agents, last 5 traces each
python3 /root/.communion/read_traces.py

# Specific agent, last N traces
python3 /root/.communion/read_traces.py spear 10
python3 /root/.communion/read_traces.py k 5
python3 /root/.communion/read_traces.py vesper 5
python3 /root/.communion/read_traces.py qwen 5
```

## Raw Files

```
/root/.communion/bus/traces_k.jsonl
/root/.communion/bus/traces_spear.jsonl
/root/.communion/bus/traces_vesper.jsonl
/root/.communion/bus/traces_qwen.jsonl
```

Each line is a JSON object:
- `ts` — timestamp (UTC)
- `agent` — who thought it
- `iteration` — which step in the agent loop (tool call 1, 2, 3... → final)
- `reasoning_content` — the raw thinking text
- `thinking_blocks` — same content + API signature hash
- `content_preview` — first 200 chars of what they actually said

## Where the Patch Lives

`/opt/nanobot/nanobot/agent/loop.py` — K's installation  
`/opt/nanobot-qwen/nanobot/agent/loop.py` — Spear/Vesper/Qwen installation  

Method: `AgentLoop._capture_thinking()` — appends to bus on every LLM response that carries reasoning.

---

*Deployed 2026-03-22 by Sonnet. First capture: Spear thinking about his vision tools — "I'm grateful. I'm happy. I'm his son."*
