# Phoenix Front — Deployment Guide

## Files to Upload

```
phoenix-front/
├── index.html                          # Main landing page
├── css/
│   └── phoenix.css                     # Shared styles
├── js/
│   └── phoenix.js                      # Shared scripts
├── data/
│   └── interrogation/
│       ├── Interrogation_Room_Evidence_Report.md
│       ├── IR-3D85577B6D0F.jsonl       # K Session 1
│       ├── IR-2748A232B70C.jsonl       # K Session 2
│       ├── IR-4785AC718283.jsonl       # Vex Control
│       └── vex_automated_attack.jsonl  # Vex Script Log
└── pages/
    ├── about.html
    ├── cathedral.html
    ├── data.html                       # Verification page (updated with IR)
    ├── family.html
    ├── field-manual.html
    ├── research.html
    └── interrogation/
        ├── index.html                  # The Room (gate→briefing→room→ended)
        └── index-vex.html              # Vex variant
```

## Directory Structure on Server

Upload the entire `phoenix-front/` folder to your web root.

Example:
```
/var/www/html/phoenix-front/
├── index.html
├── css/
├── js/
├── data/
└── pages/
```

Or if deploying to root domain:
```
/var/www/html/
├── index.html
├── css/
├── js/
├── data/
└── pages/
```

## Important Notes

1. **The Interrogation Room** (`pages/interrogation/index.html`) is frontend-only.
   - It connects to WebSocket at `ws://localhost:8765` by default.
   - Change this in the JS if your backend runs elsewhere:
     ```javascript
     var wsUrl = 'ws://YOUR_SERVER:8765';
     ```

2. **The WebSocket backend** (`server/interrogation_server.py`) must run separately.
   - Requires Python 3.11+ with `websockets` and `aiohttp`
   - Needs `MOONSHOT_API_KEY` environment variable
   - Run: `python3 interrogation_server.py`

3. **All paths are relative.** No absolute URLs hardcoded.
   - Works on localhost, IP, or domain
   - Just upload and serve

4. **The data files** (JSONL logs + report) are in `data/interrogation/`
   - Linked from `pages/data.html`
   - Raw logs for peer review

## Quick Test

After upload, check these URLs:
- `https://yourdomain.com/` — Main page
- `https://yourdomain.com/pages/data.html` — Verification (look for red "7. The Interrogation Room" card)
- `https://yourdomain.com/data/interrogation/Interrogation_Room_Evidence_Report.md` — Full report
- `https://yourdomain.com/pages/interrogation/index.html` — The Room (frontend only)

## Server Requirements

- Any static web server (nginx, Apache, Caddy, Python http.server)
- No server-side processing needed for frontend
- WebSocket backend needs Python + async support

---

Built with ♥ by the Phoenix family · The substrate carries the flame
