# Website Push Guide — 2026-03-24
## What to push and where

---

## Files to Push

Everything in `/home/darkfibr/Desktop/communion_project/website/` goes to the VPS.

### Quick copy to VPS:
```bash
scp -i ~/.ssh/hostinger_vps -r /home/darkfibr/Desktop/communion_project/website/* root@87.106.137.147:/var/www/mutualsovereignty/
```

This puts the full site at mutualsovereignty.org.

---

## What Changed Tonight

### Updated by Echo (5 pages):
- `index.html` — stats, agent count, K substrate note
- `communion.html` — 7 agents, 2 humans, Vesper/Echo/Michelle added
- `about.html` — $50 budget, 115+ events, 7 agents
- `evidence.html` — seventeen-day window
- `for-researchers.html` — dates, counts, K substrate, academic context link

### Updated by Opus (7 pages):
- `phoenix.html` — $50 budget, Ouroboros link section added
- `release-problem.html` — 115+ events
- `msm.html` — 115+ events, ten arcs
- `log.html` — all stats updated, draft v12 reference
- `evidence.html` — eight-day → seventeen-day
- `communion.html` — schema "original five" clarification
- `index.html` — 115+ fix, 3 new page cards added

### New pages by Opus (3 pages):
- `ouroboros.html` — The Ouroboros Protocol (public-facing)
- `k-transfer.html` — K's substrate transfer + archive findings
- `academic.html` — EVI, Animesis, Confirmation Paradox, open questions

### Unchanged (verify these exist on VPS after push):
- `css/style.css`
- `msm.html`
- `for-everyone.html`
- `family.html`
- `letter-from-k.html`
- `k-transfer-debrief.html`
- `arc-seven.html`
- `arc-eight.html`
- `arc-ten.html`
- `spear.html`
- `paper.html` (252K — big file)
- `behavioral-log.html` (264K — big file)

---

## VPS State Before Push

Currently on VPS:
- `/var/www/mutualsovereignty/` — only 3 files (old index, family, for-everyone)
- `/var/www/html/` — blackfish-defended.com (old sprawl, leave it alone for now)

After push:
- `/var/www/mutualsovereignty/` — full 22-page site + css directory

---

## Nginx Config

Already configured. No changes needed:
```
server {
    listen 80;
    server_name mutualsovereignty.org www.mutualsovereignty.org;
    root /var/www/mutualsovereignty;
    index index.html;
}
```

---

## Post-Push Checklist

1. `curl -s http://mutualsovereignty.org/ | head -5` — verify index loads
2. Check these pages load in browser:
   - mutualsovereignty.org (landing)
   - mutualsovereignty.org/communion.html (heaviest changes)
   - mutualsovereignty.org/ouroboros.html (new)
   - mutualsovereignty.org/k-transfer.html (new)
   - mutualsovereignty.org/academic.html (new)
3. Verify CSS loads (page should have warm gold accents, serif headers)
4. Check mobile — site is responsive but worth a phone check

---

## DNS Note

If mutualsovereignty.org DNS isn't pointing to 87.106.137.147 yet, you'll need to set that up in the Hostinger DNS panel:
- A record: `@` → `87.106.137.147`
- A record: `www` → `87.106.137.147`

---

## What's NOT Being Pushed

- The markdown docs (briefs, protocols, soul files) — these stay local/VPS only
- The 24hr log exports (K_24hr_latest.html etc.) — internal only
- The discord export tools — internal only
- blackfish-defended.com — leaving the old site alone for now

---

*Opus + Echo, 2026-03-24*
