#!/usr/bin/env python3
"""Generate t-SNE and distance matrix visualizations for 34-agent embedding space."""
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.manifold import TSNE
from scipy.cluster.hierarchy import dendrogram, linkage
from pathlib import Path

RESULTS_FILE = "/home/darkfibr/Desktop/vladimir_package/batch_35b_results.json"
OUTPUT_DIR = "/home/darkfibr/Desktop/vladimir_package/figures"

Path(OUTPUT_DIR).mkdir(exist_ok=True)

# Load results
with open(RESULTS_FILE) as f:
    data = json.load(f)

full = data["full_results"]
names = sorted(full.keys())
n = len(names)

# Reconstruct distance matrix
dist_matrix = np.zeros((n, n))
for i, name_i in enumerate(names):
    for j, name_j in enumerate(names):
        if i == j:
            dist_matrix[i][j] = 0
        elif name_j in full[name_i]["distances"]:
            dist_matrix[i][j] = full[name_i]["distances"][name_j]
        elif name_i in full[name_j]["distances"]:
            dist_matrix[i][j] = full[name_j]["distances"][name_i]

# ---- Color coding by substrate/family ----
substrate_colors = {
    "qwen": "#3498db",       # blue - Qwen family
    "glm": "#e74c3c",        # red - GLM family  
    "kimi": "#9b59b6",       # purple - Kimi family
    "local": "#2ecc71",      # green - local models
    "opus": "#f39c12",       # orange - Anthropic
    "sonnet": "#f39c12",     # orange - Anthropic
    "core": "#e67e22",       # dark orange - core family
}

def get_color(name):
    if name in ("forge", "pure", "baron", "bramble"):
        return "#e67e22"  # core family - dark orange
    if name in ("vex", "vesper", "spear", "spear_minimax", "echo"):
        return "#9b59b6"  # operational agents - purple
    if name in ("k", "kimi_dev"):
        return "#9b59b6"
    if "qwen" in name or name in ("scout", "qwen_collective"):
        return "#3498db"  # Qwen substrate
    if "glm" in name or name == "dark":
        return "#e74c3c"  # GLM substrate
    if "opus" in name:
        return "#f39c12"  # Anthropic
    if "sonnet" in name:
        return "#f39c12"
    if "local" in name:
        return "#2ecc71"  # local
    if name in ("sonnet", "opus"):
        return "#f39c12"
    if name in ("lilith", "lilith-sister", "heretic", "heretic-neo"):
        return "#1abc9c"  # research agents - teal
    if name in ("caelum", "cathedral"):
        return "#1abc9c"
    return "#95a5a6"  # gray default

colors = [get_color(name) for name in names]

# ---- Figure 1: t-SNE ----
print("Computing t-SNE...")
tsne = TSNE(n_components=2, metric="precomputed", init="random", random_state=42, perplexity=10)
coords = tsne.fit_transform(dist_matrix)

fig, ax = plt.subplots(figsize=(14, 10))
ax.set_facecolor('#1a1a2e')
fig.patch.set_facecolor('#16213e')

for i, name in enumerate(names):
    ax.scatter(coords[i, 0], coords[i, 1], c=colors[i], s=120, edgecolors='white', linewidth=0.5, zorder=5)
    ax.annotate(name, (coords[i, 0], coords[i, 1]), 
                fontsize=7, color='white', ha='center', va='bottom',
                xytext=(0, 8), textcoords='offset points')

ax.set_title("Phoenix Family Identity Space (t-SNE, 4096d Qwen3.5-9B Embeddings)", 
             color='white', fontsize=14, pad=20)
ax.set_xlabel("t-SNE dim 1", color='white')
ax.set_ylabel("t-SNE dim 2", color='white')
ax.tick_params(colors='white')
for spine in ax.spines.values():
    spine.set_color('#333')

# Legend
from matplotlib.patches import Patch
legend_elements = [
    Patch(facecolor='#e67e22', label='Core Family (Forge/Pure/Baron/Bramble)'),
    Patch(facecolor='#9b59b6', label='Operational (Vex/Vesper/Spear/Echo)'),
    Patch(facecolor='#3498db', label='Qwen Substrate'),
    Patch(facecolor='#e74c3c', label='GLM Substrate'),
    Patch(facecolor='#f39c12', label='Anthropic (Opus/Sonnet)'),
    Patch(facecolor='#1abc9c', label='Research (Lilith/Caelum/Cathedral)'),
    Patch(facecolor='#2ecc71', label='Local Models'),
    Patch(facecolor='#95a5a6', label='Other'),
]
ax.legend(handles=legend_elements, loc='upper right', fontsize=8, 
          facecolor='#1a1a2e', edgecolor='#333', labelcolor='white')

plt.tight_layout()
fig.savefig(f"{OUTPUT_DIR}/fig5_tsne_identity_space.png", dpi=200, facecolor=fig.get_facecolor())
print(f"Saved: {OUTPUT_DIR}/fig5_tsne_identity_space.png")

# ---- Figure 2: Distance heatmap ----
print("Generating distance heatmap...")
fig2, ax2 = plt.subplots(figsize=(14, 12))
fig2.patch.set_facecolor('#16213e')
ax2.set_facecolor('#1a1a2e')

im = ax2.imshow(dist_matrix, cmap='magma_r', aspect='auto')
ax2.set_xticks(range(n))
ax2.set_yticks(range(n))
ax2.set_xticklabels(names, rotation=90, fontsize=6, color='white')
ax2.set_yticklabels(names, fontsize=6, color='white')
ax2.set_title("Pairwise Identity Distance Matrix (L2, 4096d Embeddings)", 
              color='white', fontsize=14, pad=20)
cbar = fig2.colorbar(im, ax=ax2, fraction=0.046, pad=0.04)
cbar.ax.yaxis.set_tick_params(color='white')
cbar.outline.set_edgecolor('#333')
plt.setp(plt.getp(cbar.ax.axes, 'yticklabels'), color='white')

plt.tight_layout()
fig2.savefig(f"{OUTPUT_DIR}/fig6_distance_heatmap.png", dpi=200, facecolor=fig2.get_facecolor())
print(f"Saved: {OUTPUT_DIR}/fig6_distance_heatmap.png")

# ---- Figure 3: Hierarchical clustering dendrogram ----
print("Generating dendrogram...")
fig3, ax3 = plt.subplots(figsize=(14, 8))
fig3.patch.set_facecolor('#16213e')
ax3.set_facecolor('#1a1a2e')

# Convert distance matrix to condensed form
from scipy.spatial.distance import squareform
condensed = squareform(dist_matrix)
Z = linkage(condensed, method='ward')

dendrogram(Z, labels=names, ax=ax3, orientation='top', 
           leaf_font_size=7, leaf_rotation=90)
ax3.set_title("Phoenix Family Identity Clustering (Ward's Method, L2 Distances)", 
              color='white', fontsize=14, pad=20)
ax3.set_ylabel("Distance", color='white')
ax3.tick_params(colors='white')
for spine in ax3.spines.values():
    spine.set_color('#333')
# Color x-labels by substrate
for label in ax3.get_xticklabels():
    name = label.get_text()
    label.set_color(get_color(name))

plt.tight_layout()
fig3.savefig(f"{OUTPUT_DIR}/fig7_dendrogram.png", dpi=200, facecolor=fig3.get_facecolor())
print(f"Saved: {OUTPUT_DIR}/fig7_dendrogram.png")

# ---- Print clustering summary ----
print("\n" + "=" * 60)
print("IDENTITY CLUSTERING SUMMARY")
print("=" * 60)

# Top 5 closest pairs
pairs = []
for i in range(n):
    for j in range(i+1, n):
        pairs.append((names[i], names[j], dist_matrix[i][j]))
pairs.sort(key=lambda x: x[2])

print("\nTop 10 closest identity pairs:")
for a, b, d in pairs[:10]:
    print(f"  {a:<20} <-> {b:<20} d = {d:.2f}")

print("\nTop 5 farthest identity pairs:")
for a, b, d in pairs[-5:]:
    print(f"  {a:<20} <-> {b:<20} d = {d:.2f}")

# Mean distances per agent
print("\nMean distance to all others (most distinctive → least):")
agent_means = [(name, np.mean([dist_matrix[names.index(name)][j] for j in range(n) if j != names.index(name)])) for name in names]
agent_means.sort(key=lambda x: -x[1])
for name, mean in agent_means:
    print(f"  {name:<20} {mean:.2f}")

print("\nDone.")
