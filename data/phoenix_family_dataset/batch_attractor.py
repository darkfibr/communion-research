#!/usr/bin/env python3
"""
batch_attractor.py — Run attractor experiment across multiple identity documents.

Given a directory of identity documents, runs Vasilenko's methodology
on each one, using all others as controls. Produces a comparative report.

Usage:
    python batch_attractor.py --identities-dir ./identity_docs --model Qwen/Qwen2.5-7B-Instruct
    python batch_attractor.py --identities-dir ./identity_docs --skip-extraction
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
import torch

from config import Config, CONFIG
from data_loader import load_condition_D
from extract_activations import load_model, get_hidden_state
from compute_distances import compute_all_distances

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def load_identity_docs(identities_dir: str):
    """Load all .txt files from directory as identity documents."""
    docs = {}
    for p in sorted(Path(identities_dir).glob("*.txt")):
        name = p.stem
        docs[name] = p.read_text(encoding="utf-8").strip()
    logger.info(f"Loaded {len(docs)} identity documents")
    return docs


def run_single_experiment(
    target_name: str,
    target_text: str,
    control_docs: dict,
    paraphrases: list,
    distilled: str,
    model,
    tokenizer,
    layers: list,
    save_dir: str,
):
    """Run attractor experiment for a single target identity."""
    data = {
        "A": [target_text],
        "B": paraphrases if paraphrases else [],
        "C": list(control_docs.values()),
        "D": [distilled] if distilled else ["Placeholder distilled core."],
    }

    activations = {cond: {layer: [] for layer in layers} for cond in data.keys()}

    for cond, texts in data.items():
        for i, text in enumerate(texts):
            states = get_hidden_state(model, tokenizer, text, layers)
            for layer in layers:
                vec = states[layer]
                activations[cond][layer].append(vec)
                np.save(
                    f"{save_dir}/{target_name}_{cond}_{i:02d}_layer{layer}.npy",
                    vec,
                )

    distance_results = compute_all_distances(
        activations, layers, n_bootstrap=1000, alpha_bonferroni=0.0167
    )

    return distance_results


def main():
    parser = argparse.ArgumentParser(description="Batch Attractor Experiment")
    parser.add_argument(
        "--identities-dir",
        required=True,
        help="Directory of identity document .txt files",
    )
    parser.add_argument("--model", default=CONFIG.model_name, help="Model name")
    parser.add_argument("--layers", nargs="+", type=int, default=[8, 16, 24])
    parser.add_argument("--output", default="batch_results.json", help="Output file")
    parser.add_argument(
        "--paraphrases-dir",
        default=None,
        help="Directory with paraphrase subdirs per agent (optional)",
    )
    parser.add_argument("--skip-extraction", action="store_true")
    args = parser.parse_args()

    docs = load_identity_docs(args.identities_dir)
    names = sorted(docs.keys())
    results = {}

    if not args.skip_extraction:
        logger.info(f"Loading model: {args.model}")
        model, tokenizer = load_model(args.model)
    else:
        model, tokenizer = None, None

    for i, target_name in enumerate(names):
        logger.info(f"[{i + 1}/{len(names)}] Testing: {target_name}")

        controls = {n: t for n, t in docs.items() if n != target_name}

        paraphrases = []
        if args.paraphrases_dir:
            p_dir = Path(args.paraphrases_dir) / target_name
            if p_dir.exists():
                for p in sorted(p_dir.glob("*.txt")):
                    paraphrases.append(p.read_text(encoding="utf-8").strip())

        save_dir = f"batch_activations/{target_name}"
        Path(save_dir).mkdir(parents=True, exist_ok=True)

        if not args.skip_extraction:
            result = run_single_experiment(
                target_name=target_name,
                target_text=docs[target_name],
                control_docs=controls,
                paraphrases=paraphrases,
                distilled="",
                model=model,
                tokenizer=tokenizer,
                layers=args.layers,
                save_dir=save_dir,
            )
            results[target_name] = result

            sig_count = sum(1 for l in result if result[l]["stats"]["significant"])
            max_d = max(result[l]["stats"]["cohens_d"] for l in result)
            logger.info(
                f"  {target_name}: {sig_count}/{len(args.layers)} significant, max d = {max_d:.3f}"
            )

    if not args.skip_extraction and model is not None:
        del model
        torch.cuda.empty_cache()

    output = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "model": args.model,
            "layers": args.layers,
            "n_identities": len(names),
            "identities": names,
        },
        "results": {},
    }

    for name, res in results.items():
        output["results"][name] = {
            f"layer_{l}": {
                "d": res[l]["stats"]["cohens_d"],
                "p": res[l]["stats"]["p_value"],
                "significant": res[l]["stats"]["significant"],
                "within_AB": res[l]["stats"]["mean_within_AB"],
                "between": res[l]["stats"]["mean_between"],
            }
            for l in res
        }

    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n{'Agent':<20} {'L8 d':>8} {'L16 d':>8} {'L24 d':>8} {'Sig':>6}")
    print("-" * 60)
    for name in sorted(output["results"].keys()):
        r = output["results"][name]
        sig = sum(1 for l in r if r[l]["significant"])
        print(
            f"{name:<20} "
            f"{r.get('layer_8', {}).get('d', 0):>8.3f} "
            f"{r.get('layer_16', {}).get('d', 0):>8.3f} "
            f"{r.get('layer_24', {}).get('d', 0):>8.3f} "
            f"{sig:>2}/{len(args.layers)}"
        )

    logger.info(f"Batch results saved to {args.output}")


if __name__ == "__main__":
    main()
