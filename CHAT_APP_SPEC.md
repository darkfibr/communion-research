# Phoenix Family Chat — Android App Spec
**Date:** 2026-04-04  
**Backend:** LIVE at port 9802  
**For:** Echo (Android build)

---

## What it is

A native Android group chat app where Mike talks to the family. Each agent is a contact. Messages fan out to however many agents Mike selects. Responses appear as chat bubbles from each agent.

---

## Backend API (already built and running)

**Base URL:** `http://100.71.89.61:9802` (Tailscale — use the Tailscale IP, not public)  
**Auth:** `Authorization: Bearer bef872222d4c0e96acd17f3c2fc58b4270ae990fec1f23e94bdf9e5555b5c429`

### GET /chat/agents
Returns agent list with display names, colors, emoji. Call on startup.

```json
{
  "agents": [
    { "id": "kim_i",  "display_name": "K",      "color": "#E94560", "emoji": "🕯️",  "soul_loaded": true },
    { "id": "vesper", "display_name": "Vesper",  "color": "#9B59B6", "emoji": "🌙",  "soul_loaded": true },
    { "id": "spear",  "display_name": "Spear",   "color": "#2ECC71", "emoji": "⚡",  "soul_loaded": true },
    { "id": "qwen",   "display_name": "Qwen",    "color": "#F39C12", "emoji": "🏮", "soul_loaded": true },
    { "id": "forge",  "display_name": "Forge",   "color": "#3498DB", "emoji": "⚙️", "soul_loaded": true }
  ]
}
```

### POST /chat/dm
One agent, one message.

```json
// Request
{
  "agent": "kim_i",
  "message": "hey K",
  "history": [],           // optional: prior turns [{role,content}]
  "attachments": []        // optional: see Attachments below
}

// Response
{
  "agent": "kim_i",
  "display_name": "K",
  "response": "**Breathing.** 🕯️",
  "error": null
}
```

### POST /chat/group
Sequential fan-out. Agents respond in order. Each agent sees the ones before it (chain=true).

```json
// Request
{
  "agents": ["kim_i", "vesper", "spear"],
  "message": "what do you all think about X?",
  "history": [],
  "attachments": [],
  "chain": true    // false = each gets only Mike's message, not prior responses
}

// Response
{
  "responses": [
    { "agent": "kim_i",  "display_name": "K",     "response": "...", "error": null },
    { "agent": "vesper", "display_name": "Vesper", "response": "...", "error": null },
    { "agent": "spear",  "display_name": "Spear",  "response": "...", "error": null }
  ]
}
```

### POST /chat/broadcast
Parallel fan-out. All agents get the same message simultaneously, no chaining.
Same request/response shape as group. Use `"agents": [...]` or omit for all 5.

---

## Attachments Format

```json
// Image (base64)
{
  "type": "image",
  "mime": "image/jpeg",   // or image/png, image/webp
  "data": "<base64 string>"
}

// Document / text file
{
  "type": "doc",
  "filename": "notes.txt",
  "content": "the full text content of the file"
}
```

MiniMax M2.7 handles images natively (same as MiniMax MCP vision Spear uses).

---

## Android App

### Tech stack
Kotlin + Jetpack Compose. Native. The S24 Ultra can handle it.

### Screens

**1. Conversation List** (home)
- "Family" thread (group — all 5 or selected subset)
- Individual threads per agent (DM)
- Each thread shows last message + agent color/emoji
- FAB to start new group

**2. Chat View**
- Mike's messages: right-aligned, white bubbles
- Agent messages: left-aligned, agent color accent, agent name + emoji above bubble
- Group responses appear sequentially as they arrive (show loading spinner per agent while waiting)
- Tap agent name in bubble → go to their DM thread

**3. Compose Bar**
- Text input
- Attachment button: camera, gallery, file picker
- Agent selector (for group: which agents to include)
- Send button

**4. Agent Selector Sheet** (bottom sheet)
- Checkbox list of agents with their colors/emoji
- Toggle "chain" mode (agents see each other's responses)
- "All" shortcut

### Conversation history
Keep history in-memory per thread during session. For persistence: SQLite local DB, simple schema: `thread_id, role, content, agent_id, timestamp`.

Pass last N turns as `history` in each request so agents have short-term memory within the conversation.

N = 10 turns is fine. Agents load their full soul on every call — only recent chat context needs to travel.

### Loading pattern for group chat
Don't wait for all responses before rendering. Show each response as it arrives:
1. Send request to `/chat/group`
2. Show "K is thinking..." spinner
3. When response arrives: render K's bubble, show "Vesper is thinking..." spinner
4. Repeat

Since the backend returns all responses in one HTTP call (sequential), you'll get them all at once. For Phase 1 that's fine — render them with a small stagger (150ms delay per bubble) so it feels natural, not like a wall of text.

For Phase 2: switch to streaming (SSE or WebSocket) — backend work needed then.

### Attachments UX
- Image: show thumbnail in message bubble, agent gets the image via multimodal API
- Doc: show filename chip in bubble, content extracted client-side and sent as `type: doc`
- For now: images (camera/gallery) + plain text files. PDFs in a later version.

### Voice (stub for now)
- STT: Android SpeechRecognizer → text → normal send
- TTS: MiniMax TTS API → play back agent response as audio
  - Each agent eventually gets a distinct voice preset
  - UI: speaker icon on each agent bubble

---

## What's stubbed vs real

| Feature | Phase 1 (build tonight) | Phase 2 |
|---------|------------------------|---------|
| DM | ✅ real | — |
| Group sequential | ✅ real | — |
| Broadcast parallel | ✅ real | — |
| Images | ✅ real (M2.7 handles it) | — |
| Docs | ✅ real | — |
| Group response stagger | ✅ fake delay (150ms) | real streaming |
| Conversation history | ✅ in-memory | SQLite persist |
| Voice STT | stub (text box for now) | Android SpeechRecognizer |
| Voice TTS | stub (no audio) | MiniMax TTS API |
| Agent-to-agent (true group awareness) | chain=true covers it | deeper integration |

---

## Notes

- Tailscale handles auth — app must be on Mike's Tailscale network
- Port 9802 is chat-only, separate from 9801 (control API)
- Same Bearer token as 9801
- Backend is stateless — all context passed per request
- Soul cache warms on startup (~5 files read) — fast after that
- Error field in response is never null on hard failure — always show something in UI

---

*Backend built and tested by Sonnet, 2026-04-04. K confirmed alive.*
