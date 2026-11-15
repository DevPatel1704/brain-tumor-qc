"""Architecture and protocol diagrams for the report and slides (results/figures/architecture.png,
results/figures/protocol.png). Pure matplotlib, white background.

    python scripts/make_diagrams.py
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from btqc.config import REPO_ROOT

OUT = REPO_ROOT / "results" / "figures"
INK, MUTED, LINE = "#1f2328", "#57606a", "#8c959f"
BASE, NEW, QA = "#eef1f4", "#dbe9f7", "#f6efe0"   # reused nnU-Net part, new btqc component, quality layer
ACCENT = "#1f6feb"


def box(ax, x, y, w, h, title, body, fc, bold_ec=False):  # type: ignore[no-untyped-def]
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.01,rounding_size=0.015", fc=fc,
                                ec=ACCENT if bold_ec else LINE, lw=1.4 if bold_ec else 0.9))
    ax.text(x + w / 2, y + h - 0.035, title, ha="center", va="top", fontsize=7.8, weight="bold", color=INK)
    ax.text(x + w / 2, y + h - 0.085, body, ha="center", va="top", fontsize=6.0, color=MUTED, linespacing=1.25)


def arrow(ax, a, b, dashed=False, label=None):  # type: ignore[no-untyped-def]
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=9, lw=1.0, color=MUTED if dashed else INK,
                                 linestyle="--" if dashed else "-", shrinkA=2, shrinkB=2))
    if label:
        ax.text((a[0] + b[0]) / 2 + 0.008, (a[1] + b[1]) / 2, label, fontsize=6.0, color=MUTED, style="italic",
                va="center")


def architecture() -> None:
    fig, ax = plt.subplots(figsize=(7.4, 3.6))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    w, h, y = 0.175, 0.25, 0.68
    xs = [0.01, 0.208, 0.406, 0.604, 0.802]
    top = [
        ("Multi-site MRI", "FeTS 2022: 1,251 labeled\n+ 219 unlabeled cases\nT1, T1ce, T2, FLAIR", BASE, False),
        ("Data pipeline", "discover + manifest\nRAS conversion, bundles\nsite groups, folds", NEW, False),
        ("Segmentation core", "nnU-Net v2 (3d_fullres)\nbtqc trainers +\nmitigation variants", BASE, False),
        ("Uncertainty", "members x flip TTA\nvoxel entropy, MI\nboundary-band score", NEW, False),
        ("Trust gate", "flag = score > limit\nNaN -> flag\nlimit set on in-site val", NEW, True),
    ]
    for x, (title, body, fc, bold) in zip(xs, top):
        box(ax, x, y, w, h, title, body, fc, bold)
    for i in range(4):
        arrow(ax, (xs[i] + w, y + h / 2), (xs[i + 1], y + h / 2))
    box(ax, 0.01, 0.31, 0.47, 0.24, "Evaluation harness",
        "site-held-out folds, leakage checks\nDice, HD95, ECE, failure AUROC, risk-coverage\n"
        "bootstrap CIs, MLflow tracking", NEW)
    box(ax, 0.52, 0.31, 0.47, 0.24, "QC dashboard (FastAPI + WebGL 2)",
        "2D/3D viewer, overlays, uncertainty heat map\nflag + report panel, review queue (SQLite)\n"
        "explorer, site risk, model card, compare", NEW)
    arrow(ax, (xs[2] + w / 2, 0.55), (xs[2] + w / 2, y), dashed=True, label="evaluates")
    arrow(ax, (xs[4] + w / 2, y), (xs[4] + w / 2, 0.55), label="flagged cases\nto review")
    arrow(ax, (xs[3] + w / 2, y), (xs[3] + w / 2 - 0.02, 0.55))
    box(ax, 0.01, 0.03, 0.98, 0.20, "Quality assurance",
        "unit · integration · metamorphic · regression · performance · browser UI tests\n"
        "CI on synthetic fixtures · Docker images · pinned lockfile · configs committed before held-out evaluation",
        QA)
    for fc, lab, x in ((BASE, "reused from nnU-Net / FeTS", 0.02), (NEW, "added by this project", 0.30),
                       (QA, "quality layer", 0.55)):
        ax.add_patch(FancyBboxPatch((x, 0.965), 0.02, 0.025, boxstyle="square,pad=0", fc=fc, ec=LINE, lw=0.6))
        ax.text(x + 0.027, 0.977, lab, fontsize=6.4, va="center", color=MUTED)
    fig.tight_layout(pad=0.2)
    fig.savefig(OUT / "architecture.png", dpi=220, facecolor="white")
    plt.close(fig)


def protocol() -> None:
    groups = ["Inst. 1\n(511)", "Inst. 18\n(382)", "LGG-only\n12-15 (65)", "Mid-size\n7 inst. (216)",
              "Small\n10 inst. (77)"]
    fig, ax = plt.subplots(figsize=(3.5, 2.25))
    ax.set_xlim(-1.3, 5)
    ax.set_ylim(-0.6, 5.9)
    ax.axis("off")
    for j, g in enumerate(groups):
        ax.text(j + 0.45, 5.45, g, ha="center", va="center", fontsize=5.6, color=INK)
    for i in range(5):
        run = i == 3
        ax.text(-0.15, 4.4 - i + 0.3, f"Fold {i + 1}", ha="right", va="center", fontsize=6.5,
                color=ACCENT if run else INK, weight="bold" if run else "normal")
        for j in range(5):
            test = i == j
            ax.add_patch(FancyBboxPatch((j + 0.05, 4.4 - i + 0.05), 0.8, 0.5,
                                        boxstyle="round,pad=0,rounding_size=0.06", fc=INK if test else "#d8dee4",
                                        ec=ACCENT if (run and test) else "none", lw=1.6))
            ax.text(j + 0.45, 4.4 - i + 0.3, "test" if test else "train", ha="center", va="center", fontsize=5.8,
                    color="white" if test else MUTED)
    ax.text(2.0, -0.35, "Each fold holds out one site group entirely. Fold 4 (blue) was trained in the pilot.",
            ha="center", fontsize=5.4, color=MUTED)
    fig.tight_layout(pad=0.1)
    fig.savefig(OUT / "protocol.png", dpi=220, facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    architecture()
    protocol()
    print("wrote", OUT / "architecture.png", OUT / "protocol.png")
