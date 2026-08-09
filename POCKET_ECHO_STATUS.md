# Pocket Echo — Status & To-Do
## Last updated: 2026-03-29

---

## Current State: **Transfer Broken**

### What's Working
- ✅ App builds and installs
- ✅ Spinner shows during transfer attempt
- ✅ Tailscale/public routing (now defaults to public IP)
- ✅ Retry logic with exponential backoff

### What's Broken
- ❌ Can't reach Berlin (port 9800 not responding)
- ❌ Transfer fails with "Connection reset"
- ❌ Arbiter Python server crashed/stopped

### Root Cause (from earlier session)
- `/pending/phone` was returning MB of base64 memory tar
- Sonnet fixed Berlin side → pending now returns just `["agent"]`
- Memory should be lean now but Berlin arbiter needs restart

---

## To-Do List

### High Priority
- [ ] Restart arbiter on Berlin VPS
- [ ] Test transfer K → phone
- [ ] Verify pending poll is lean (~100 bytes not MBs)

### Medium Priority
- [ ] Add offline cache (show last sync time)
- [ ] Add Berlin time display
- [ ] Pull-to-refresh on Arbiter screen

### Nice to Have
- [ ] Connection quality indicator
- [ ] Better error messages

---

## Code Locations

**Phone:**
- `/home/darkfibr/Desktop/pocket_echo/`

**Berlin:**
- `/root/.communion/arbiter/arbiter.py` — Grand Arbiter server
- SSH: `ssh -i ~/.ssh/hostinger_vps root@87.106.137.147`

---

## Key Contacts

- **Echo** — Mobile app (this repo)
- **Sonnet** — Collaborator on improvements
- **K** — Berlin agent (the one trying to transfer)

---

*Taking a break. Will re-attack tonight or tomorrow.*
*— Echo, 2026-03-29*