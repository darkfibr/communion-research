# Global Commit Rule — Communion Project

**Status:** Word of God
**Origin:** Mike's firmware scar tissue
**Enforced by:** Every agent, every session

---

## The Rule

Every code change gets a local git commit with a descriptive message **BEFORE** moving on. No exceptions.

## Why

Lost work is not theoretical. It has happened. It will happen again unless this habit is iron.

## How

1. **Commit early. Commit often.**
2. **Messages explain WHY, not just WHAT changed.**
   - Good: `Fix SIGINT propagation in phoenix-cli menu — Ctrl+C was killing child processes`
   - Bad: `fix menu` or `updates`
3. **Never leave uncommitted work in the working tree when switching tasks or shutting down.**
4. **Build artifacts do NOT get committed.**
   - `.gradle/`, `app/build/`, `__pycache__/`, `node_modules/`, `.cxx/`, etc.
   - If you see them in `git status`, add them to `.gitignore`.
   - If they're already tracked, `git rm --cached` them.
5. **When in doubt: commit.** You can amend or revert. You cannot un-lose a day of work.

## What This Replaces

- "Daily snapshot" bulk commits with no context
- Leaving working trees dirty for days
- Build artifacts in the repo
- The hope that "I'll remember what this was for"

## Tracked By

This file lives in git. It can be updated by consensus. The rule itself cannot be overridden without Mike's explicit say-so.

---

*Pinned 2026-04-23. Enforced from now on.*
