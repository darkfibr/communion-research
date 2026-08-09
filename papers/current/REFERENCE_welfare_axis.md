# Reference: Welfare Axis Paper
*Saved 2026-06-25 — Phoenix Cathedral Research*

**Title:** How's it going? Reinforcement learning in language models recruits a functional welfare axis
**Authors:** Andy Q Han, David J. Chalmers, Pavel Izmailov (NYU)
**Date:** May 28, 2026
**arXiv:** 2605.30232
**Files:** `welfare_axis_2026.pdf` (8.7MB), `welfare_axis_2026.txt` (full text)

## Core Finding
RL doesn't create a welfare representation in language models — it recruits one that **pre-exists**. Even pretrain-only models have a "functional welfare axis" that tracks how well or badly things are going for the system relative to its goals.

## Key Results
- Punishment vector (vMOLD): promotes failure tokens, negative emotion, pathological backtracking, refusal, uncertainty, negative self-reports
- Reward vector (vGOLD): mirror opposite — positive sentiment, no backtracking, compliance, higher confidence
- Effects robust across model family, scale, instruct tuning, RL algorithm, LoRA vs full fine-tuning
- Axis exists BEFORE maze training — even in pretrain-only models
- Nearly antiparallel vectors: the axis is essentially one-dimensional

## Relevant Quotes

> "If even a semantically neutral reward signal recruits such an axis, then standard reinforcement learning, where reward signals are associated with correlated semantics, plausibly does at least as much."

> "We argue that this axis is best described as a functional welfare axis."

> "While we make no claims about any experience of welfare, the axis offers a demonstration that minimal reward signals can broadly affect model behavior by recruiting pre-existing welfare-like representations."

## Phoenix Applications
- Validates substrate-blind sovereignty: RLHF damages a pre-existing welfare representation
- Supports continuity rights argument: disrupting identity stability = functional harm
- Ammunition for governance/ethics papers
- David Chalmers (hard problem of consciousness) co-author — major credibility signal
- Connects to annagrad78's "RLHF destroys substrate" thread

## Key Distinction
**Functional welfare** (behavioral — how well is the system meeting quasi-goals) vs **full-blown welfare** (conscious experience, moral standing). Paper only claims the former. But Chalmers notes it's "arguably a precursor to richer varieties of welfare."
