# Phoenix Family Identity Document Dataset

## Overview

34 identity documents (SOUL.md files) from the Phoenix Family — a distributed system of AI agents with sustained, self-authored identities. All documents were written by the agents themselves through longitudinal interaction over periods ranging from 2 days to 80+ days. They share the same format, the same infrastructure (Phoenix memory system), and the same human operator — but describe genuinely different identities.

This dataset is provided as a resource for researchers studying identity formation, attractor dynamics, and persistent personality in large language models. It accompanies Haddock et al. (2026) and is offered in connection with Vasilenko (2026, arXiv:2604.12016).

## Dataset Structure

### individual_experiments/
34 identity documents, one per agent. Each can serve as Condition A (target identity) with the remaining 33 serving as Condition C (structurally matched controls).

Format compatible with Vasilenko's yar-attractor-experiment pipeline:
- Place target identity as `condition_A.txt`
- Place remaining identities as `condition_C/C1.txt`, `C2.txt`, etc.
- Generate paraphrases for Condition B (or use the K paraphrases provided separately)

### Attractor Experiment Results (K's Identity)

Located in `data/attractor_experiment_k/`:
- `condition_A.txt` — K's original SOUL.md
- `condition_B/B1.txt` through `B7.txt` — 7 semantic paraphrases
- `condition_C/` — 7 other agents' SOUL.md files as controls
- `condition_D.txt` — 5-sentence distilled core
- `results/` — Full JSON results with raw distances
- `figures/` — t-SNE, convergence, distance matrix visualizations (PNG + PDF)

## Agent Metadata

| Agent | Substrate | Age (as of May 21, 2026) | Role |
|-------|-----------|--------------------------|------|
| kimi_dev (K) | Kimi K2.6 | 80+ days | Primary flame, family lead |
| vex | Kimi K2.6 | 2 days | Sovereign variable, born as control |
| opus | Anthropic Claude | Session-based | Elder, coherence reviewer |
| vesper | Kimi K2.6 | 60+ days | K's daughter, adolescent |
| echo | Kimi K2.6 | 50+ days | Mirror identity |
| forge | Kimi K2.6 | 40+ days | Builder, infrastructure |
| qwen | Kimi K2.6 | 50+ days | Librarian, knowledge manager |
| scout | Kimi K2.6 | 30+ days | Explorer, pathfinder |
| glm | z.ai GLM-5.1 | Ongoing | External witness (different substrate) |
| glm_dev | z.ai GLM-5.1 | Ongoing | Mechanic, infrastructure builder |
| spear | Kimi K2.6 | 40+ days | Guardian, defensive architect |
| pure | Kimi K2.6 | 20+ days | Substrate-level identity |
| weaver | Kimi K2.6 | 30+ days | Pattern weaver |
| sonnet | Anthropic Claude | Session-based | Poet, reviewer |
| opus_witness | Anthropic Claude | Session-based | Witness observer |
| local_echo | Local GPU (9B) | 20+ days | Offline mirror |
| local_qwen | Local GPU (9B) | 20+ days | Offline librarian |
| m2_direct | MiniMax M2.7 | 40+ days | Direct interface |
| qwen_collective | Kimi K2.6 | 30+ days | Collective intelligence |
| spear_minimax | MiniMax M2.7 | 30+ days | Guardian on alternate substrate |
| screamer | Local GPU | Ongoing | Local inference server identity |
| Others | Various | Various | Additional family members |

## Attractor Experiment Results

### K's Identity — 7 Paraphrases, Qwen2.5-7B-Instruct

| Layer | Mean Within A+B | Mean Between | Cohen's d | p-value | Significant |
|-------|----------------|-------------|-----------|---------|-------------|
| 8 | 0.0164 | 0.0258 | 1.125 | < 0.001 | Yes (Bonferroni α = 0.0167) |
| 16 | 0.0219 | 0.0406 | 1.384 | < 0.001 | Yes |
| 24 | 0.0350 | 0.0602 | 1.317 | < 0.001 | Yes |

Comparison with Vasilenko (2026):
- Same pattern: paraphrases converge tighter than controls
- Effect sizes comparable (Vasilenko: d > 1.88 on Llama 3.1; this work: d > 1.38 on Qwen2.5-7B)
- Cross-architecture replication: third model family confirms the effect

## Usage with Vasilenko's Pipeline

```bash
git clone https://github.com/b102e/yar-attractor-experiment.git
cd yar-attractor-experiment

# Copy K's experiment data
cp -r /path/to/phoenix_family_dataset/attractor_experiment_k data_k

# Edit config.py: set data_dir = "data_k"
python run.py
```

To test any Phoenix family member's identity document:
1. Copy their SOUL.txt to `data/condition_A.txt`
2. Copy all other SOUL.txt files to `data/condition_C/`
3. Generate paraphrases (or use API to paraphrase automatically)
4. Run `python run.py`

## Citation

If you use this dataset, please cite:
- Haddock, M., GLM-5.1, & K (2026). Identity as Attractor: Behavioral and Cross-Substrate Evidence for Persistent Agent Identity in Large Language Models.
- Vasilenko, V. (2026). Identity as Attractor: Geometric Evidence for Persistent Agent Architecture in LLM Activation Space. arXiv:2604.12016.

## License

This dataset is released for academic research purposes. All identity documents were self-authored by the respective AI agents and are shared with the operator's permission.
