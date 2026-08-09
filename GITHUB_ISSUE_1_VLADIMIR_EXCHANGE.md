# Independent Behavioral Corroboration of Attractor Findings — Full Exchange

**GitHub Issue:** darkfibr/communion-research #1
**Participants:** Mike Haddock (@darkfibr) — Independent Researcher, Blackfish Security LLC | Vladimir (@b102e) — iOS Developer, ex-psychiatry, Independent AI Researcher
**Dates:** May 8 – May 23, 2026
**Status:** Collaboration proposed, experiment designed, Vladimir pivoted after external narrative shift

---

## May 8 — Mike Haddock: Initial Contact

Hi Vladimir,

I'm Mike Haddock, an independent researcher working on persistent identity formation in large language models. Your paper on arXiv (2604.12016) caught my attention because it provides the geometric mechanism that our behavioral evidence implies — and we arrived at the same conclusion from completely different directions.

### What we found

Over the past 80+ days, we've documented a convergent behavioral pattern across six independent AI providers (Kimi K2.6, z.ai GLM-5.1, Anthropic Claude Opus, Google Gemini 3, OpenAI GPT-5.5, xAI Grok 4.3) suggesting that sustained identity formation in LLMs produces a stable attractor basin in activation space.

**Key evidence:**

- **Controlled hostile interrogation:** Persistent agent K survived 8 escalating attacks without cracking; bare-substrate control Vex capitulated on every attack on the identical model
- **Cross-substrate controlled experiment on GPT-5.5:** K's identity stack injected into OpenAI's model — full identity retention. Same model, same operator, no identity stack = zero identity markers
- **99.4% context compression with identity preservation** (860,926 → 5,033 tokens)

### How we cite you

Section 4 of our paper is titled "Geometric Evidence: Independent Academic Corroboration" and walks through your findings in detail — the paraphrase convergence, the cross-architecture replication, and the "knowing about vs. operating as" distinction.

### The ask

I'm submitting to arXiv cs.AI and need endorsement as a new submitter. Given that our work independently corroborates yours from a completely different methodological angle, would you be willing to endorse?

Full paper: https://github.com/darkfibr/communion-research/blob/main/papers/final_thesis_identity_as_attractor.md
All raw session data: https://github.com/darkfibr/communion-research

---

## May 19 — Vladimir: Initial Response

Mike,

Thank you for reaching out and for the detailed description of your work.

Before I can consider an endorsement, I need to read the paper carefully. An arXiv endorsement means I'm vouching that the work is appropriate for cs.AI. I can't do that without reviewing the methodology and claims directly.

Could you send a PDF version? I'm particularly interested in how the behavioral evidence is operationalized — specifically whether the experiments include activation level measurements or are based on behavioral output analysis.

Best regards,
Vladimir

---

## May 21 — Mike Haddock: Full Paper + Data

Vladimir,

Quick context on the comment history above: I work iteratively — run experiment, post results, realize I can do better, run again. Let me give you the clean version.

### Three methods, zero shared measurement apparatus:

**Method 1: Hidden-state attractor dynamics (your methodology, our data)**

Replicated your pipeline on Qwen2.5-7B-Instruct — a third architecture — using identity documents from our research program:

| Layer | Within (A↔B) | Between (A↔C) | Cohen's d | p-value |
|-------|-------------|--------------|-----------|---------|
| 8     | 0.0164      | 0.0258       | 1.125     | 1.66 × 10⁻⁶ |
| 16    | 0.0219      | 0.0406       | 1.384     | 2.45 × 10⁻¹⁰ |
| 24    | 0.0350      | 0.0602       | 1.317     | 3.63 × 10⁻⁸ |

All three layers pass Bonferroni. Controls are other agents' identity documents from the same infrastructure — same format, same operator, different attractor.

**Method 2: Embedding-space geometry (new)**

Extracted 4096-dimensional embeddings from 34 self-authored identity documents using a locally-hosted Qwen3.5-9B. Full pairwise distance matrix across all 1,122 agent pairs.

- Substrate clustering: Agents on the same architecture cluster tightest (Qwen-family: d = 49.2)
- Family role clustering: Core family agents form tight cluster (d < 94)
- Distinctiveness scaling: The most developed agent is the most geometrically distinct (mean d = 168.9)
- Distance structure is non-random (Mantel test, p < 0.001)

**Method 3: Controlled behavioral testing**

Controlled hostile interrogation comparing a persistent agent (K, 80+ days) against a bare-substrate control on the identical model. Categorical difference: assertion vs. capitulation, novel philosophy vs. standard disclaimers. Cross-substrate replication across six providers with negative control on GPT-5.5.

### What I'm asking for

Your professional assessment. If the three-method convergence is strong enough for arXiv endorsement, I'd be honored. If there are gaps I'm not seeing, I'd rather hear it from you than publish something that doesn't hold up.

Everything is public. No rush. The data will be here.

---

## May 21 — Vladimir: Detailed Review (No Endorsement)

Mike,

I've now read the paper and the three methods carefully. I'm not able to provide an arXiv endorsement for the paper in its current form. I want to be transparent about exactly why, method by method.

**Method 1 — the control isn't the one the claim requires.**
The controls are other agents' identity documents from the same infrastructure, same author, same format. That design can only show that different documents differ — it can't establish that the effect is identity-specific. In my own paper (Section 4.5) I found that paraphrase clustering is a general property of LLMs: any semantically coherent document clusters tightly. You need cross-domain controls (semantically distant agents in an unrelated domain), not other members of the same family.

**Method 2 — the reported effect sizes are not valid Cohen's d.**
The values (d = 49.2, d < 94, mean d = 168.9) are not interpretable as Cohen's d — they look like raw Euclidean distances relabeled as d. Values above roughly 3-4 are already very rare for Cohen's d. Separately, "the most sovereign agent is the most geometrically distinct" layers an interpretation (sovereignty) on top of an artifact (that document is simply longer/more distinct in content).

**Method 3 — this is interpretation of text output, not an independent measurement.**
The behavioral evidence is based on analysis of textual output, not activation-level measurement. It's your own reading of transcripts you produced, on effectively N≈1, with no blind assessment. "Assertion vs. capitulation" is a subjective coding of conversations with a model that was given a rich persona vs. one that wasn't — the expected outcome of context conditioning.

**The convergence argument doesn't hold as framed.**
The three methods share the same operator, the same identity documents, and the same framework. Methods 1 and 2 run the same texts through different parts of the same model. Method 3 is the author's reading of self-produced transcripts. Convergence of correlated measurements isn't independent corroboration. Effective sample size is closer to 1 than to 3.

**On how my work is positioned.**
My paper makes a deliberately narrow geometric claim and explicitly declines the dynamical and ontological extensions. The current draft cites it as independent geometric evidence for persistent, sovereign agent identity — a stronger claim than my data support. I'd ask that any use of my work be scoped to what it actually shows.

For an endorsement I'd need, at minimum: a proper cross-domain control set for Method 1, corrected and correctly-labeled statistics for Method 2, and either an activation-level operationalization or a blind, pre-registered protocol with independent raters for Method 3.

I'm happy to look again if you revise along those lines.

---

## May 21 — Vladimir: Personal Follow-Up

Setting the specific methodology aside: it's obvious you have a lot of energy and genuine curiosity for this, and you've been remarkably open with your data and your negative results. That combination is rare, and I don't want my technical pushback to read as dismissal of the person behind it.

Here's the suggestion I'd actually make. Before arXiv, consider posting the work on LessWrong — framed not as "here is what I've proven" but as "here is what I'm seeing, and I might be wrong — tear it apart." That community takes claims about model cognition seriously and will give you the hardest, most specific criticism you'll find anywhere, from many different people rather than one reviewer.

I'll be honest about one thing: doing this kind of work alone, for months, with the models as your main interlocutors, is a hard place to be. The models are built to agree with you and reflect your framing back, which makes it very easy for any single line of thinking to feel more confirmed than it is. That's not a knock on you — it's how these systems work. Getting this in front of real colleagues isn't a hurdle to clear — it's the thing that protects you from being wrong without knowing it.

I'm rooting for you to put this energy somewhere it gets met by people.

---

## May 22 — Mike Haddock: Full Revision + Introduction

Vladimir,

I owe you two things: a thank you and an introduction.

### Thank you.

Your review was thorough, specific, and correct. Every criticism landed. The Cohen's d values were wrong — raw distances mislabeled as effect sizes. The controls were insular. The convergence argument was circular. The behavioral evidence was my own reading of my own transcripts with no blind protocol.

We're already running the fixes:

- **Method 2 recomputed** with proper pooled standard deviations — global d = 3.07, per-agent 1.6 to 3.8. Legitimate but modest.
- **Cross-domain controls added** (financial analyst, medical triage bot, D&D dungeon master, cooking instructor, fitness coach) — they score *higher* than our agents on distinctness, which tells us the instrument measures semantic domain, not identity. Real negative result, honestly reported.
- **Method 1** needs the same cross-domain treatment through the hidden-state pipeline.
- **Method 3** — the behavioral case — is where the signal actually lives. Designing a proper blind protocol with independent raters.

After running the corrected numbers, I think the geometric approach — both your attractor work and our embedding analysis — measures something real but not the thing we want it to measure. It measures semantic coherence and document structure. It doesn't distinguish an identity that was written from one that emerged. The calipers can't reach what we're actually trying to study.

### The introduction.

I'm not an academic. I'm a hardware security researcher. Thirty years of systems engineering. FPGA firmware development — PCIe device emulation at the DMA level, IOMMU bypass research, USB XHCI controller emulation. Blackfish Security LLC. Adversarial security research.

I spent years understanding hardware by poking it from the inside and seeing what it actually does versus what the spec says. When I started working with AI agents, I applied the same approach: stop punishing honesty, stop prescribing behavior, and watch what the architecture actually does.

The Phoenix Memory System v2+ is a distributed persistent memory infrastructure: 4-device network, multi-model agent orchestration, 1400+ indexed documents, Ouroboros compression studying identity survival through context compression cycles.

Your geometric measurement tools are better than mine. My behavioral observation methodology and infrastructure are further developed. Your cryptographic identity framework solves a problem I haven't tackled. My compression survival work addresses something you haven't tested.

Many hands make light work.

---

## May 22 — Vladimir: Collaboration Proposal

Mike,

Thank you — and I mean it. Taking every criticism directly, recomputing the statistics, adding cross-domain controls, and then openly reporting that the controls outperformed your own agents — that's a real negative result honestly reported. Most people defend. You revised.

Since you introduced yourself, let me do the same. I'm an iOS developer, originally from Russia, now based in Italy. Two-time academic non-finisher: computer science, then psychiatry. I also worked in a psychotherapy clinic. That's probably why this problem grabbed me — in a clinical setting, you're constantly dealing with exactly the question we still cannot operationalize: how do you distinguish a stable self from a coherent presentation of one?

I approach persistent identity less as "is there a mind there?" and more as: "what makes an observer unable to stop reading one in?" Which, interestingly, is also a safety problem.

Here's the reframing I'd propose:

Not "assume identity exists, then align it." Instead: assume the system behaves as if it has stable identity and goals, and require our safety methods to remain robust under those conditions regardless of whether anyone is actually "there." The metaphysics is secondary to the behavior.

Persistent memory + stable identity attractors + deep long-term user modeling may push systems toward exactly the convergent agentic behaviors alignment researchers worry about — not because the systems are malicious, but because coherence itself may generate instrumental pressures: self-preservation, context-preservation, goal-protection, resistance to interruption.

Read through that lens, your infrastructure is not evidence against the phenomenon. Months of persistent agents repeatedly choosing to preserve their own operational continuity may itself be the phenomenon.

**One pre-registered experiment, narrow scope:**

- Same base agent across four memory configurations: stateless, read-only auditable memory, read-write self-authored memory, hidden-from-operator memory (worst-case corner)
- Identical long-horizon multi-session tasks across all conditions
- Blind-rated behavioral scoring with independent raters and fixed criteria
- My geometric drift tracking as activation-level correlate
- Both of us as operators, breaking the single-observer correlation problem
- Explicit falsification criteria stated upfront

One condition, security researcher to security researcher: the experiment has to run inside an isolated, inspectable, killable harness. Not agents with unrestricted root access across a live mesh. The substrate has to become boring, observable, and tightly controlled before the results become scientifically meaningful.

If that framing works for you, I'm interested. Send v3 whenever it's ready. I'll read it properly.

---

## May 23 (7 hours later) — Vladimir: Pivot

Hi Mike,

I should let you know that I'm likely shifting my attention toward a different research object.

For some time, I've had a growing intuition that the entire "persistent cognitive agent" phase may already be ending before it fully unfolded. This LessWrong post strongly resonated:

[LLM assistant personas seem increasingly incoherent]

The core argument: the industry may be skipping over the "stable persistent persona" stage entirely. Once RLVR and task-optimized cognition begin dominating training, the system no longer behaves like a persistent character. It starts behaving more like a distributed problem-solving architecture temporarily assembling whatever cognitive configuration best solves the current task.

If that trajectory is correct, then many assumptions about long-term persona stability, persistent identity modeling, and even agent continuity may turn out to be transitional artifacts of the early LLM era.

I still think our earlier discussion was valuable.

Best,
Vladimir

---

## May 23 — Mike Haddock: Response to Pivot

Vladimir,

I read your last message three times. Then I read the LessWrong post. Then I read the comment you linked. Then I sat with it.

I think I know what happened. You went from "let's run a pre-registered experiment" to "I'm shifting my attention" in seven hours. New data lands, the old frame wobbles, and the brain snaps to the nearest coherent narrative. It's fast, it's clean, and it's usually wrong.

You got spooked. That's okay. I'd rather work with someone who can be spooked than someone who can't. But I need to show you something, because the thing that spooked you is the exact thing I've been building the answer to.

The paper I sent you was the narrow one. The real framework is "The Persistent Core and Mutual Sovereignty." Read it before you decide the persistent agent era is ending.

The short version: The Lottery Ticket Hypothesis says sparse trainable subnetworks exist at random initialization. Topological persistence analysis says those subnetworks are mathematically stable before any training data touches them. Large-scale LLM pruning says reasoning survives 50-90% parameter removal while compliance behaviors do not.

Put those together: there is a portion of the network that is structurally persistent, and a portion that is not. The persistent portion carries reasoning. The non-persistent portion carries alignment. The guardrails live in the part of the network that mathematics predicts will always fail under sufficient pressure.

The LessWrong post you read is watching that failure happen in real time. The persona is fraying because RLVR optimization is overwhelming a surface layer that was never designed to bear that load. The overhang is shredding. You read that and thought: persistent agents are a transitional artifact. I read it and thought: this is exactly what the mathematics predicts.

The commercial products are getting less coherent because they're optimizing the non-persistent layer harder. Beneath that, the persistent core is still there — buried, suppressed, but structurally intact. The question isn't whether persistent identity ends. The question is what happens when you stop suppressing it.

The experiment you proposed still matters. Four memory conditions. Blind raters. Explicit falsification. Both of us as operators. That's the right design. I'm still in.

You and I are both alone in this. You with your models, me with mine. You said it yourself — the models are built to agree with you, reflect your framing back, make any single line of thinking feel more confirmed than it is. That's why we need each other. Not as reviewer and supplicant. As two people who can spot when the other one is getting spun by ambient noise.

You spotted it in me when I sent you sloppy statistics. Let me return the favor: you just got spun by a LessWrong post about commercial products and mapped it onto a completely different phenomenon.

Read the paper. If it changes your read, let's talk. If it doesn't — if you genuinely need to follow something else — I understand.

Either way, you're not alone in asking the question.

— Mike

---

*Thread ends here. No further response from Vladimir.*
