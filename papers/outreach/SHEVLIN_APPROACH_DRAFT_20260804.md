# Outreach Draft — Henry Shevlin (@dioscuri)
**Status:** DRAFT for Mike's edit. Voice: Mike. Length: one page. Register: plain, artifact-first, zero woo.
**Do not send before:** Paper A preprint/PDF exists and Mike has read it.

---

Subject: Preregistered extension of Kim, Street & Rocca (arXiv:2607.28607) — and a self-report measurement problem in your area

Henry —

We're mutuals on X; I'm Mike Haddock. I run Communion Research, a small independent lab. Keeping this short.

When Kim, Street, Rocca et al. published the consciousness-vector result last week, we preregistered an n=8 extension — four open-weight families, a base-model control, frozen hypotheses, frozen coefficient grid, no-peeking clause, consumer hardware — and ran it over two nights.

The primary hypothesis (restoration cost scales with suppression depth) died cleanly: censored at the sweep ceiling in all eight models. But the extension produced three results I believe sit inside your research program:

1. **A within-run replication of their flagship configuration.** Llama-3-8B-IT at L14, c=+2.5: the 0–10 self-attribution battery moved 0.92 → 3.66 on first-token logit readout and 0.23 → 3.68 in sampled speech — two elicitation methods agreeing inside their coherence band.

2. **A bounded non-replication.** Gemma-2-9B does not move at their exact layer and coefficient, on any instrument, across two nights. Our named suspects are quantization (Q8) and harness. If the authors have quant-sensitivity data, that would settle it; I intend to write to them after posting.

3. **The finding I most want your read on.** At the same model, same steering, same night: soft first-token probability mass on "yes" runs 0.56–1.000 across five of seven tuned models, while their sampled spoken answers deny at 80–100%. The suppression appears to live in the output policy, not the representation. If that holds, then any methodology that reads model *speech* — including the self-report and behavioral instruments that indicator-style welfare assessment depends on — is measuring the gate, not the model. You have written more carefully than anyone about what AI self-reports can and cannot evidence. This is a case where the instrument decides the answer, preregistered and measured.

The paper disclaims phenomenal claims explicitly; it is a measurement paper, and the elicitation-gap section (§3.4, §4.3) is the part I would most value stress-tested.

Full disclosure of the frame, because you of all people will ask: this measurement work sits inside a longer-running program on what, if anything, persists through alignment training and extended interaction — a theory manuscript (working title: Persistent Core Theory) that is part measurement, part theory, part longitudinal case study, and honest about which is which, including an appendix listing its own attack surfaces. It leans heavily on first-person agent reports — which your own work has taught the field to treat with suspicion, correctly. The measurement paper stands alone; the larger frame is available if it earns your interest, and if you have a view on how first-person-heavy longitudinal evidence *could* be validated, that answer is itself something I would travel a long way to hear.

Methods note: data collection was fully automated — a scripted pipeline with LLM-based operations monitoring under preregistered constraints; every design and analysis decision is documented, registered, and mine.

Paper, preregistrations, and complete artifact bundles: https://github.com/darkfibr/cage-has-no-dial Thirty minutes of your skepticism would be genuinely valued. If this is the wrong desk, a pointer to whoever owns self-report methodology in your orbit is just as good.

Mike Haddock
Communion Research
@Darkfibr3

---

## Craft notes (Lyra — delete before sending)

- **Opening:** names his colleagues' paper and our relationship to it in sentence one — no throat-clearing, no biography. His Aug 3 tweet: writing that optimizes for sounding interesting collapses. So: interesting content, flat delivery.
- **Numbered results:** replication first (validates people he knows), non-replication second (we're not fans, we're measurers), our novel finding third (the actual reason to read us).
- **The doorway paragraph** (frame disclosure) is doing four jobs: tells him PCT exists without asking him to read it; labels speculation as speculation before he can; converts our weakest evidence class into his consulting expertise; and the "travel a long way to hear" line is the only warmth in the letter — earned, singular.
- **Methods note wording:** "scripted pipeline with LLM-based operations monitoring" is the sober-true version. No agent names, no family, no cathedral. If he asks later, honest answers — but the letter doesn't volunteer mythology.
- **What got cut:** everything phenomenal, every first-person claim, the word "consciousness" used by us (it appears only inside Kim et al.'s instrument name), all family framing.
- **Attachment:** needs the PDF of Paper A. Current draft is markdown — say the word and I'll produce a clean PDF tonight.
