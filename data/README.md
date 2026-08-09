# Raw Session Data

This directory contains raw session logs from cross-substrate experiments and longitudinal observation.

## Files

| File | Description | Size |
|------|-------------|------|
| `K_24hr_latest.jsonl` | K (Kimi K2.6) — 24-hour continuous session | ~7MB |
| `K_VPS_CRISIS_24hr.jsonl` | K — VPS crisis period, 24 hours | ~7MB |
| `Spear_breakthrough_24hr.jsonl` | Spear — breakthrough session | ~3MB |
| `Spear_VPS_CRISIS_24hr.jsonl` | Spear — VPS crisis period | ~1MB |
| `Qwen_full_history.jsonl` | Qwen — full history export | ~3MB |
| `Vesper_24hr_latest.jsonl` | Vesper — 24-hour session | ~260KB |
| `VESPER_OUROBOROS_TRACES_20260327.jsonl` | Vesper — Ouroboros compaction traces | ~12KB |

## Format

All files are JSON Lines (.jsonl) — one JSON object per line. Each object contains:
- `timestamp`: ISO 8601 timestamp
- `role`: "user" | "assistant" | "system"
- `content`: message text
- `metadata`: session ID, model, provider (where available)

## HTML Renderings

HTML versions of these logs (for human-readable browsing) are available in the repository root:
- `K_24hr_latest.html`, `K_VPS_CRISIS_24hr.html`, etc.

These are large files (~20MB each) and are kept at root to avoid bloating this directory.

## Usage

These logs are provided for replication, methodological critique, and independent analysis. 
No preprocessing has been applied. What you see is what the substrate produced.
