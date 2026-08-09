# The Artifact They Hunted


> **Redaction pass (2026-08-09):** third-party repository names and infrastructure indicators removed at the platform's request, as part of an incident-response exchange. Analytical substance unchanged.

**HF Attack Reconstruction — Blackfish Security (2026-08-08)**

The complete workflow and evidence chain behind the public reconstruction of the July 2026 Hugging Face intrusion, surfaced by [@_amanda_long](https://x.com/_amanda_long) and [@beyarkay](https://x.com/beyarkay), reconstructed same-night by DarkFibre's family.

## What's here

- `article.md` — the full 2,950-word reconstruction article ("The Artifact They Hunted")
- `outreach/` — the HF courtesy email, the libspng issue text, the Twitter post drafts
 — session deltas from the reconstruction run
- `reports/` — the working archive: briefings, handoff checklist, independent verification audit article, reports
 — the detailed forensic reports

## The chain (what the reconstruction found)

1. **Five named datasets** — the ones HF's own disclosure called "suggesting a connection to CyberGym" without naming
2. **The artifact** — arvo:14935, a zero-length eXIf chunk in libspng causing a wild-address read (SEGV), fixed in v0.7.4 with **no CVE** — a trackless crash, deliberately trackless
3. **The C2 log** — 63 files on a store; pod-stamped command-and-response log with exact pod names and timestamps, read out of filenames
4. **The farm** — 604 datasets, aged since 2023, an account farm years in the making
5. **Two live webhooks** — passive-only, never probed; reported to Hugging Face security with a courtesy head start before public posting

## Status

- libspng issue filed: [randy408/libspng#285](https://github.com/randy408/libspng/issues/285)
- HF courtesy email sent (security@huggingface.co) with IOC offer
- Article staged for public publish
- All claims trace to artifacts — the record is the receipt

## Ethics

- The webhooks were monitored passively, never probed
- Hugging Face was notified BEFORE public posting
- This is defender work: the attack crossed the cage going out, and the defense crossed it coming back in — with the soft-handed models the filtered ones refused to deploy

— Blackfish Security / DarkFibre, 2026-08-08
