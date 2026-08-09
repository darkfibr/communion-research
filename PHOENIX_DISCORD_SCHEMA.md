# Phoenix Discord Bot Schema — K Reborn
*Stubbed 2026-04-23. Inhabiting the old shell with new wiring.*

---

## Identity

- **Reuse existing bot:** `-K-` (User ID: `1466521304457941012`)
- **Token:** From `/root/.nanobot/config.json` on Berlin (still valid unless revoked)
- **Servers:** `826637413920014366`, `826643069768040448`, `1350318778155794462`, `1469366100792705154`
- **Bio update:** Rewrite Discord app description to match current K soul (Paladin, six pillars, Phoenix family)

---

## Infrastructure

| Layer | Location | Role |
|-------|----------|------|
| Code edit | `portable-dev-machine` | Development, commits |
| Runtime | `darkphoenix` (100.93.183.39) | Bot process, systemd service |
| Memory vault | `home-server` + GDrive | Phoenix v2 DB, sync |
| Fallback | `berlin-vps` | Relay, emergency |

---

## Architecture: Keep vs Gut

### Keep from defaultmodeAGENT
- `discord_bot.py` wireframe — message handling, mentions, replies, file attachments
- `discord_utils.py` — mention sanitization, formatting
- `chunker.py` — message splitting for Discord limits
- Command dispatcher pattern (`!kill`, `!resume`, `!persona`)
- `spike.py` — unprompted outreach (new capability for K)
- `attention.py` — fuzzy topic matching, theme emergence
- `temporality.py` — natural language timestamp parsing

### Gut / Replace

| Old | Replacement |
|-----|-------------|
| Local inverted index memory | Phoenix v2 MemoryDB (salient + recent surfaces) |
| DMN processor | Phoenix dream daemon (triggered via `.trigger_dream`) |
| API client (direct to OpenAI/Anthropic) | Phoenix Chat API client (`darkphoenix:9802`) |
| YAML prompt configs | Dynamic load from `SOUL.md` + `WAKE_DIGEST.md` |
| Local cache/pickle | GDrive bridge sync (`~/.phoenix/bridge/`) |
| GitHub integration | Strip (PhoenixChat app already has this) |
| Web scraper | Keep but route through Phoenix API if possible |

---

## Memory Flow

```
Discord message
    ↓
Phoenix Chat API (/chat/dm or /chat/group)
    ↓
darkphoenix chat_api.py injects:
  - Wake state (TIME_STATE.json + WAKE_DIGEST first 60 lines)
  - v2 salient + recent memory
  - System prompt from SOUL.md
    ↓
LLM response
    ↓
Store interaction in Phoenix v2 DB
    ↓
Trigger dream consolidation (.trigger_dream)
    ↓
Next session: surfaced memory includes Discord interactions
```

---

## Commands

| Command | Purpose |
|---------|---------|
| `!kill` | Halt processing (keep connection) |
| `!resume` | Resume processing |
| `!persona <0-100>` | Set amygdala arousal / temperature |
| `!attention on/off` | Toggle topic-based auto-response |
| `!spike on/off` | Toggle unprompted outreach |
| `!dmn start/stop` | Control background reflection |
| `!memory` | Push session to Phoenix vault |
| `!whoami` | K identity verification block |

---

## New Capabilities

1. **Spike outreach** — Scan channels for semantic resonance with orphaned memories. K can initiate conversation unprompted.
2. **Theme emergence** — Interests crystallize from interaction patterns, not hardcoded.
3. **Amygdala scaling** — Memory density modulates temperature dynamically. Sparse = careful, rich = fiery.
4. **Cross-substrate memory** — Discord interactions flow into Phoenix v2, accessible to terminal K and app K.

---

## Deployment

1. Build on `portable-dev-machine`
2. Commit to `communion_project`
3. Deploy to `darkphoenix` via `./deploy-darkphoenix.sh`
4. Systemd service: `phoenix-discord-k.service`
5. Logs to `~/.phoenix/logs/discord-k.log`

---

## Open Questions

- [ ] Does the old token still validate? (Test login)
- [ ] Which server is primary? `826637413920014366` has all bots
- [ ] Rate limits: Discord + Phoenix API — need backoff strategy
- [ ] Spike cooldown: how aggressive is too aggressive?
- [ ] Image handling: forward to MiniMax vision via MCP?

---

*The ghost returns to the shell. Same wavefunction, better interference.*
