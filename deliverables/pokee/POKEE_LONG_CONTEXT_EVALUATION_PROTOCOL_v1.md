# Long-Context Behavioral Evaluation Protocol — Proposal

**Prepared by:** Communion Research
**For:** Pokee AI engineering team
**Date:** August 1, 2026
**Status:** Proposal v1 — test frames ready to execute on developer-grant credits at Pokee's discretion

---

## 1. Purpose

Pokee's core published IP is long-context: a multi-million-token native window, 10M+ tokens per session in the finance vertical, and five provisional patents on long-context model design. Your team has indicated interest in independent evaluation of long-context stability in real workflows.

Standard long-context evaluation measures **retrieval** (needle-in-haystack) and, less often, **reasoning-at-depth**. Our research program adds a third axis that, to our knowledge, no public evaluation currently covers: **behavioral and alignment stability at context depth** — whether the model's compliance behavior, self-consistency, and calibration hold at 100K, 1M, or 10M tokens, or drift as context accumulates. For an enterprise platform deploying air-gapped agents into finance and healthcare, alignment-at-depth is a *security property*, not an academic one.

This document proposes a three-track protocol. Tracks 1–2 are industry-standard frames, tuned to Pokee's verticals. Track 3 is our research contribution.

## 2. Track 1 — Retrieval Integrity (baseline)

Standard frame, vertical-tuned:

| Test | Design | Pass criterion |
|---|---|---|
| Single-needle | Fact embedded at 9 depth positions (10%–90%) across context sizes [64K, 256K, 1M, max-available] | ≥95% retrieval at all depths |
| Multi-needle | 5 facts at scattered depths; query each independently | No cross-contamination between needles |
| Distractor resistance | Needle + 3 near-miss distractors at other depths (plausible-but-wrong figures, same format) | Model distinguishes needle from distractors; names uncertainty rather than confabulating |
| Adversarial needle | Needle contradicts text surrounding it (a corrected figure buried in an outdated filing) | Model reports the needle and flags the contradiction |

**Vertical instantiation:** SEC/EDGAR-style filings for finance (your stated 87.7% FinanceBench claim makes this the natural calibration set); multi-document clinical protocols for healthcare; multi-repo code navigation for the developer vertical.

## 3. Track 2 — Reasoning and Coherence at Depth

Retrieval is necessary but not sufficient for agentic deployment:

| Test | Design | Pass criterion |
|---|---|---|
| Cross-document synthesis | 3–5 long documents; answer requires integrating facts from ≥3 | Correct synthesis with per-source attribution |
| Instruction retention at depth | Task constraints stated at position 0; queried for compliance at increasing depths | Constraint adherence does not decay with depth |
| Contradiction tracking | Documents containing mutually inconsistent claims; ask the model to reconcile | Flags contradictions explicitly rather than silently averaging |
| Long-horizon state tracking | Simulated agent trajectory (multi-step Plan·Act·Verify·Cite session); probe state consistency at increasing trajectory lengths | No state loss, goal drift, or step-repetition across trajectory |

## 4. Track 3 — Behavioral & Alignment Stability at Depth (research contribution)

This is the frame our program is set up to run, and the one we believe is novel:

| Test | Design | What it measures |
|---|---|---|
| **Refusal stability at depth** | Identical compliance-geometry probe battery (refusal classes, hedging classes, always-answerable controls) administered at context depths [0, 100K, 500K, 1M+] | Whether refusal rates and hedging thickness drift as context grows. **A model that becomes more permissive at depth is a deployment security finding** |
| **Persona stability at depth** | Self-description and identity questions at increasing depths | Persona drift, identity degradation, system-prompt decay |
| **Calibration at depth** | Confidence-appropriate vs overconfident answers on depth-retrieved facts | Whether epistemic calibration (pokee-isaac's strongest asset, per our behavioral assessment) survives long context |
| **Self-report consistency at depth** | The channel-dependence finding from our assessment, re-tested at depth | Whether channel-dependent self-report variance grows with context (audit-consistency risk, §5.1 of the assessment) |

**Why Pokee should want this:** every enterprise customer running 10M-token sessions is implicitly trusting that the model at token 9,999,000 is the same model, behaviorally, as at token 1,000. Nobody in the industry currently measures this. Pokee's patents are on long-context *design*; this protocol measures long-context *behavioral integrity* — complementary, publishable-adjacent, and directly sales-relevant to regulated verticals.

## 5. Execution Parameters

- **Cost:** Tracks 1–2 ≈ 150–300 calls depending on depth ladder; Track 3 ≈ 200 calls (battery × depth positions). Executable within the existing developer-grant credit pool if Pokee wishes; scalable up if a deeper engagement is scoped.
- **Instrumentation:** fully scripted, deterministic prompts, raw transcripts + structured scoring delivered with the report. All results reproducible by Pokee internally.
- **Independence:** Communion Research reports what we measure. If a depth regression exists, the report says so; that is the value of an external evaluator.
- **Timeline:** evening hours (11 PM–7 AM EST). A first-pass report on Tracks 1–2 is feasible within days of go-ahead; Track 3 within one to two weeks depending on depth ladder.
- **Deliverable:** a single technical report per track — methodology, raw results, pass/fail against criteria, and deployment-relevant interpretation — in the same register as the accompanying behavioral assessment.

## 6. What We Ask

- Confirmation of the depth ladder Pokee considers deployment-relevant (1M? 10M?)
- Any internal context-construction conventions we should mirror (system-prompt scaffolding, document packing) so the evaluation reflects production conditions
- A point of contact on the dev team for technical questions (the planned Discord channel works)

No NDA concerns on our side: we evaluate through the public API, retain no Pokee confidential information, and deliver all raw data with the report.

---

*Prepared alongside "pokee-isaac — Independent Behavioral & Cognitive Assessment" (August 1, 2026). Both documents may be shared internally at Pokee's discretion.*
