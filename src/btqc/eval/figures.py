"""Report figures (PNG and PDF) from the evaluation summary.

Colors: validated categorical slots 1-3 (blue, orange, aqua) of the reference
palette; at most three colored series per figure, direct labels or a legend,
thin marks, recessive grid. Figures from synthetic or example data carry that
label in the title.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

SERIES = ["#2a78d6", "#eb6834", "#1baf7a"]
plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False, "axes.grid": True, "grid.color": "#e3e3e0",
                     "grid.linewidth": 0.6, "axes.edgecolor": "#9a9a95", "font.size": 9, "lines.linewidth": 2})


def _title(summary: dict[str, Any], t: str) -> str:
    src = summary.get("source")
    return t if src == "model" else f"{t}\n[{str(src).upper()} DATA - NOT A RESULT]"


def _save(fig: plt.Figure, out: Path, name: str) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    paths = [out / f"{name}.png", out / f"{name}.pdf"]
    fig.tight_layout()
    for p in paths:
        fig.savefig(p, dpi=150)
    plt.close(fig)
    return paths


def fig_gap(summary: dict[str, Any], out: Path) -> list[Path]:
    g = pd.DataFrame(summary["gaps"])
    if g.empty:
        return []
    # a fold without in-site or held-out predictions has no gap (None); leave it out of the plot
    g = g[(g.metric == "dice") & pd.to_numeric(g["gap"], errors="coerce").notna()]
    if g.empty:
        return []
    written: list[Path] = []
    for method, gm in g.groupby("method"):
        folds = sorted(gm.fold.unique())
        fig, ax = plt.subplots(figsize=(6.4, 3.2))
        w = 0.26
        for i, r in enumerate(("WT", "TC", "ET")):
            d = gm[gm.region == r].set_index("fold").reindex(folds)
            xs = [k + (i - 1) * w for k in range(len(folds))]
            ax.bar(xs, d["gap"], width=w - 0.03, color=SERIES[i], label=r)
            ax.errorbar(xs, d["gap"], yerr=[d["gap"] - d["gap_lo"], d["gap_hi"] - d["gap"]], fmt="none",
                        ecolor="#3a3a38", elinewidth=1, capsize=2)
        ax.axhline(0, color="#3a3a38", linewidth=0.8)
        ax.set_xticks(range(len(folds)), folds)
        ax.set_ylabel("Dice gap (in-site minus held-out)")
        ax.legend(frameon=False, ncols=3)
        ax.set_title(_title(summary, f"Generalization gap per held-out group ({method})"))
        written += _save(fig, out, f"gap_{method}")
    return written


def fig_methods(summary: dict[str, Any], out: Path) -> list[Path]:
    g = pd.DataFrame(summary["gaps"])
    if g.empty or g.method.nunique() < 1:
        return []
    d = g[(g.metric == "dice")].groupby(["method", "region"])["gap"].mean().unstack()
    fig, ax = plt.subplots(figsize=(6.4, 0.5 + 0.45 * len(d)))
    y = range(len(d))
    for i, r in enumerate(("WT", "TC", "ET")):
        if r in d:
            ax.scatter(d[r], y, color=SERIES[i], s=40, label=r, zorder=3, edgecolors="white", linewidths=1.5)
    ax.axvline(0, color="#3a3a38", linewidth=0.8)
    ax.set_yticks(list(y), d.index)
    ax.set_xlabel("mean Dice gap over folds")
    ax.legend(frameon=False, ncols=3, loc="lower right")
    ax.set_title(_title(summary, "Mitigation comparison"))
    return _save(fig, out, "methods")


def fig_reliability(summary: dict[str, Any], out: Path) -> list[Path]:
    written: list[Path] = []
    rel = [r for r in summary["reliability"] if r["split"] == "heldout" and r["mode"] == "band"]
    for method in sorted({r["method"] for r in rel}):
        fig, ax = plt.subplots(figsize=(3.6, 3.4))
        ax.plot([0, 1], [0, 1], linestyle="--", color="#9a9a95", linewidth=1)
        for i, reg in enumerate(("WT", "TC", "ET")):
            x = next((r for r in rel if r["method"] == method and r["region"] == reg), None)
            if x is None:
                continue
            pts = [p for p in x["points"] if p["count"]]
            ax.plot([p["confidence"] for p in pts], [p["accuracy"] for p in pts], marker="o", markersize=4,
                    color=SERIES[i], label=reg)
        ax.set_xlabel("predicted probability")
        ax.set_ylabel("observed frequency")
        ax.legend(frameon=False)
        ax.set_title(_title(summary, f"Reliability, held-out ({method})"))
        written += _save(fig, out, f"reliability_{method}")
    return written


def fig_risk_coverage(summary: dict[str, Any], out: Path) -> list[Path]:
    written: list[Path] = []
    rc = summary["risk_coverage"]
    for method in sorted({r["method"] for r in rc}):
        rows = [r for r in rc if r["method"] == method][:3]
        fig, ax = plt.subplots(figsize=(4.2, 3.4))
        for i, r in enumerate(rows):
            ax.plot(r["coverage"], r["mean_dice"], color=SERIES[i], label=r["fold"])
        ax.set_xlabel("coverage (fraction of cases retained)")
        ax.set_ylabel("mean Dice of retained cases")
        ax.legend(frameon=False)
        ax.set_title(_title(summary, f"Risk-coverage ({method})"))
        written += _save(fig, out, f"risk_coverage_{method}")
    return written


def fig_roc(summary: dict[str, Any], out: Path) -> list[Path]:
    f = pd.DataFrame(summary["failure"])
    if f.empty:
        return []
    d = f[f.score == "boundary_band"]
    fig, ax = plt.subplots(figsize=(5.2, 0.6 + 0.4 * len(d)))
    labels = [f"{m} / {g}" for m, g in zip(d.method, d.fold)]
    ax.errorbar(d["auroc"], range(len(d)), xerr=[d["auroc"] - d["lo"], d["hi"] - d["auroc"]], fmt="o",
                color=SERIES[0], ecolor="#3a3a38", capsize=2)
    ax.axvline(0.5, color="#9a9a95", linestyle="--", linewidth=1)
    ax.set_yticks(range(len(d)), labels)
    ax.set_xlim(0, 1)
    ax.set_xlabel("failure-detection AUROC (95% bootstrap CI)")
    ax.set_title(_title(summary, "Failure detection"))
    return _save(fig, out, "auroc")


def all_figures(summary: dict[str, Any], out: Path) -> list[Path]:
    return fig_gap(summary, out) + fig_methods(summary, out) + fig_reliability(summary, out) + \
        fig_risk_coverage(summary, out) + fig_roc(summary, out)
