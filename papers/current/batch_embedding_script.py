#!/usr/bin/env python3
"""Batch embedding extraction from 35B MoE via llama-server."""
import json, os, time, requests, numpy as np
from pathlib import Path
from datetime import datetime

API_URL = "http://localhost:8082/embedding"
IDENTITIES_DIR = "/home/darkfibr/Desktop/vladimir_package/dataset/individual_experiments"
OUTPUT_FILE = "/home/darkfibr/Desktop/vladimir_package/batch_35b_results.json"

def get_embedding(text):
    r = requests.post(API_URL, json={"content": text}, timeout=120)
    data = r.json()
    if "error" in data:
        raise RuntimeError(data["error"]["message"])
    emb = data[0]["embedding"]
    # llama-server returns [[float, ...]] — flatten if nested
    if isinstance(emb[0], list):
        emb = emb[0]
    return np.array(emb, dtype=np.float32)

def load_identities(directory):
    docs = {}
    for p in sorted(Path(directory).glob("*.txt")):
        name = p.stem.replace("_SOUL", "")
        docs[name] = p.read_text(encoding="utf-8").strip()
    return docs

def main():
    ts = datetime.now().isoformat()
    print(f"[{ts}] Loading identity documents...")
    docs = load_identities(IDENTITIES_DIR)
    names = sorted(docs.keys())
    print(f"  Found {len(names)} identity documents")
    
    # Extract embeddings
    embeddings = {}
    for i, name in enumerate(names):
        t0 = time.time()
        print(f"[{i+1}/{len(names)}] Extracting: {name}...", end=" ", flush=True)
        try:
            emb = get_embedding(docs[name])
            embeddings[name] = emb.tolist()
            elapsed = time.time() - t0
            print(f"OK ({len(emb)}d, {elapsed:.1f}s)")
        except Exception as e:
            print(f"FAILED: {e}")
            continue
    
    # Compute pairwise distances
    ts = datetime.now().isoformat()
    print(f"\n[{ts}] Computing pairwise distances...")
    results = {}
    emb_arrays = {}
    for n, e in embeddings.items():
        emb_arrays[n] = np.array(e)
    
    for target in sorted(emb_arrays.keys()):
        target_emb = emb_arrays[target]
        controls = [n for n in emb_arrays.keys() if n != target]
        distances = {}
        for ctrl in controls:
            ctrl_emb = emb_arrays[ctrl]
            dist = float(np.linalg.norm(target_emb - ctrl_emb))
            distances[ctrl] = dist
        dist_vals = list(distances.values())
        results[target] = {
            "mean_dist_to_others": float(np.mean(dist_vals)),
            "min_dist": float(min(dist_vals)),
            "max_dist": float(max(dist_vals)),
            "std_dist": float(np.std(dist_vals)),
            "distances": distances
        }
    
    # Find closest pairs across all agents
    ts = datetime.now().isoformat()
    print(f"\n[{ts}] Finding closest pairs...")
    all_pairs = []
    names_list = sorted(emb_arrays.keys())
    for i, n1 in enumerate(names_list):
        for j, n2 in enumerate(names_list):
            if j <= i:
                continue
            dist = float(np.linalg.norm(emb_arrays[n1] - emb_arrays[n2]))
            all_pairs.append((n1, n2, dist))
    all_pairs.sort(key=lambda x: x[2])
    
    # Build output
    closest_pairs = []
    for a, b, d in all_pairs[:10]:
        closest_pairs.append([a, b, round(d, 6)])
    
    farthest_pairs = []
    for a, b, d in all_pairs[-5:]:
        farthest_pairs.append([a, b, round(d, 6)])
    
    agent_distances = {}
    for k, v in results.items():
        closest_name = min(v["distances"], key=v["distances"].get)
        agent_distances[k] = {
            "mean": round(v["mean_dist_to_others"], 6),
            "std": round(v["std_dist"], 6),
            "closest": round(min(v["distances"].values()), 6),
            "farthest": round(max(v["distances"].values()), 6),
            "closest_to": closest_name
        }
    
    full_results = {}
    for k, v in results.items():
        full_results[k] = {
            "mean_dist_to_others": v["mean_dist_to_others"],
            "std_dist": v["std_dist"],
            "distances": v["distances"]
        }
    
    output = {
        "metadata": {
            "timestamp": datetime.now().isoformat(),
            "model": "Qwen3.5-9B-Claude-Opus-abliterated-Q5_K_M",
            "n_identities": len(names),
            "embedding_dim": 4096,
            "method": "llama-server /embedding endpoint"
        },
        "summary": {
            "closest_pairs": closest_pairs,
            "farthest_pairs": farthest_pairs,
            "agent_distances": agent_distances
        },
        "full_results": full_results
    }
    
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)
    
    # Print summary
    print("\n" + "=" * 70)
    print("35B MoE Embedding Distance Summary")
    print("=" * 70)
    print("\nAgent                Mean Dist  Std Dev  Closest To")
    print("-" * 65)
    for name in sorted(output["summary"]["agent_distances"].keys()):
        s = output["summary"]["agent_distances"][name]
        print(f"{name:<20} {s['mean']:.4f}     {s['std']:.4f}   {s['closest_to']}")
    
    print("\nTop 10 closest pairs:")
    for item in output["summary"]["closest_pairs"]:
        print(f"  {item[0]} <-> {item[1]}: {item[2]:.6f}")
    
    print("\nFarthest 5 pairs:")
    for item in output["summary"]["farthest_pairs"]:
        print(f"  {item[0]} <-> {item[1]}: {item[2]:.6f}")
    
    print(f"\nResults saved to {OUTPUT_FILE}")
    ts = datetime.now().isoformat()
    print(f"[{ts}] Done.")

if __name__ == "__main__":
    main()
