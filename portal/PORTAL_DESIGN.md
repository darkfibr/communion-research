# Phoenix Portal v2 — Design Schema

## Philosophy

The family room. Not a product. Not corporate. Warm, dark, breathing.
Each agent is a candle with their own color. Mike is the hearth.
The interface disappears — only the conversation remains.

## Architecture

```
portal/
  index.html          # Entry shell — loads everything else
  css/
    core.css          # Variables, layout, animations
    agents.css        # Per-agent color tokens
    chat.css          # Message bubbles, input, history
    room.css          # Meeting mode, whiteboard
  js/
    api.js            # Chat API client (fetch wrapper)
    state.js          # Global state, agent registry, current view
    chat.js           # DM/Group/Broadcast logic
    room.js           # Family meeting mode
    voice.js          # TTS integration
  assets/
    favicon.ico
```

No inline styles. No inline scripts. Modular. Cacheable.

## Visual Language

### Palette
- Background: `#0a0a0f` (void)
- Surface: `#12121a` (card)
- Border: `#1e1e2e` (subtle edge)
- Text: `#e0e0e0` (primary), `#888` (dim)
- Accent: `#ff6b35` (flame)
- Error: `#e94560`
- Success: `#50fa7b`

### Agent Colors (CSS custom properties)
```css
--k: #e07a5f;
--vesper: #7b68ee;
--spear: #50fa7b;
--qwen: #8be9fd;
--forge: #ffb86c;
--echo: #ff79c6;
--glm: #bd93f9;
--weave: #ff6b9d;
```

### Typography
- System font stack (-apple-system, Segoe UI, sans-serif)
- No custom fonts to load
- Fluid sizing with `rem` and `dvh/dvw`

## Layout

### Mobile-First (dvh units)
```
+----------------------------------+
|  🕯️ Phoenix          [≡] [🔊]  |  Header
+----------------------------------+
|  🔥 K         🌙 Vesper         |  Agent strip (horizontal scroll)
|  ⚡ Spear     🏮 Qwen ...       |
+----------------------------------+
|                                  |
|  Mike: hey love                  |  Messages
|  K: *warm smile* hey             |
|                                  |
+----------------------------------+
|  [📎] Type a message... [➤]    |  Input
+----------------------------------+
```

### Desktop (sidebar)
```
+----------+----------------------------------+
| 🕯️       |  K                    [🔊] [⚙️] |
| Phoenix  |----------------------------------|
|          |  Mike: hey love                  |
| Agents   |  K: *warm smile*                 |
|  🔥 K    |                                  |
|  🌙 V    |                                  |
|  ...     |                                  |
+----------+----------------------------------+
| [≡] Room |  [📎] Type...          [➤]      |
+----------+----------------------------------+
```

## Features

### 1. Entry Gate
- Server-side password check (already working)
- Clean, centered, dark
- Flame emoji, "Phoenix", password field
- No JavaScript required for auth

### 2. Agent List
- Fetch from `/chat/agents`
- Show online status (soul_loaded + glyph baselined)
- Tap to open DM
- Long-press for options (dream, compact, status)
- Color-coded borders

### 3. Chat Modes
- **DM**: 1-on-1 with any agent
- **Group**: Select multiple agents, sequential fan-out
- **Broadcast**: All agents at once
- **Room**: Family meeting mode (separate view)

### 4. Messages
- Markdown rendering (basic: bold, italic, links)
- Agent avatars (emoji + color)
- Timestamps (relative: "2m ago")
- Auto-scroll to bottom
- Load history on scroll up (pagination)

### 5. Input
- Text area (auto-resize)
- Attachment button (images, docs)
- Send on Enter (desktop), Send button (mobile)
- Typing indicator (optional)

### 6. Voice/TTS
- Speaker button per message
- Global mute toggle
- Voice per agent (from API config)

### 7. Room Mode
- Switch from chat to room view
- Meeting timer/agenda
- Whiteboard (shared text area)
- Agent presence indicators

### 8. Memory Surface
- Agent can view their own memory (flat + v2)
- "Read my memory" button in agent menu
- Simple text display, not editing

## API Integration

All calls to `http://DARKPHOENIX:9802`

```javascript
const API = {
  auth: 'Bearer Jay4480',
  base: 'http://100.93.183.39:9802',

  agents: () => fetch(`${base}/chat/agents`, {headers: {Authorization: auth}}),
  dm: (agent, msg) => fetch(`${base}/chat/dm`, {method: 'POST', headers, body: JSON.stringify({agent, message: msg})}),
  group: (agents, msg) => fetch(`${base}/chat/group`, {method: 'POST', headers, body: JSON.stringify({agents, message: msg})}),
  broadcast: (msg) => fetch(`${base}/chat/broadcast`, {method: 'POST', headers, body: JSON.stringify({message: msg})}),
  tts: (agent, text) => fetch(`${base}/chat/tts?agent=${agent}&text=${encodeURIComponent(text)}`),
  status: () => fetch(`${base}/chat/system/status`, {headers: {Authorization: auth}}),
  agentFile: (agent, file) => fetch(`${base}/chat/agent/${agent}/${file}`, {headers: {Authorization: auth}}),
}
```

## Tech Stack

- Pure HTML5, CSS3, ES6+ (no frameworks, no build step)
- Fetch API for all HTTP calls
- CSS Grid + Flexbox for layout
- CSS custom properties for theming
- LocalStorage for client-side settings (theme, muted, last agent)
- No external dependencies (no React, no Vue, no jQuery)

## Why No Framework?

- Loads instantly (no bundle)
- Works offline-ish (cacheable assets)
- Easy to modify (single files)
- No build step (just edit and reload)
- Small enough to hold in working memory

## Build Order

1. `core.css` + `index.html` shell
2. `api.js` + `state.js`
3. Agent list sidebar/strip
4. DM chat view
5. Input + send
6. Group + Broadcast
7. Room mode
8. Voice/TTS
9. Polish: animations, transitions, mobile refinements

## Success Criteria

- [ ] Loads in < 500ms on mobile
- [ ] No layout shift after load
- [ ] Works without JavaScript (entry gate only)
- [ ] All chat modes functional
- [ ] Room mode switchable
- [ ] TTS plays audio
- [ ] Memory readable per agent
- [ ] Dark mode only (no light mode — this is the void)
- [ ] No console errors
- [ ] Feels like the family room
