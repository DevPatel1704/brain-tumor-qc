"""Case-level bootstrap intervals, paired Wilcoxon tests and Spearman correlation."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np
from scipy import stats


def bootstrap_ci(x: np.ndarray, stat: Callable[[np.ndarray], float] = np.mean, n_boot: int = 2000,
                 alpha: float = 0.05, seed: int = 0) -> dict[str, float]:
    """Percentile bootstrap over cases. NaNs are dropped first."""
    a = np.asarray(x, dtype=float)
    a = a[~np.isnan(a)]
    if a.size == 0:
        return {"mean": float("nan"), "lo": float("nan"), "hi": float("nan"), "n": 0}
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, a.size, size=(n_boot, a.size))
    vals = np.apply_along_axis(stat, 1, a[idx]) if stat is not np.mean else a[idx].mean(axis=1)
    lo, hi = np.percentile(vals, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return {"mean": float(stat(a)), "lo": float(lo), "hi": float(hi), "n": int(a.size)}


def bootstrap_diff_ci(a: np.ndarray, b: np.ndarray, n_boot: int = 2000, alpha: float = 0.05,
                      seed: int = 0) -> dict[str, float]:
    """CI of mean(a) - mean(b) for two independent case sets (e.g. in-site vs held-out)."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    a, b = a[~np.isnan(a)], b[~np.isnan(b)]
    if a.size == 0 or b.size == 0:
        return {"diff": float("nan"), "lo": float("nan"), "hi": float("nan"), "n_a": int(a.size), "n_b": int(b.size)}
    rng = np.random.default_rng(seed)
    da = a[rng.integers(0, a.size, size=(n_boot, a.size))].mean(1)
    db = b[rng.integers(0, b.size, size=(n_boot, b.size))].mean(1)
    lo, hi = np.percentile(da - db, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return {"diff": float(a.mean() - b.mean()), "lo": float(lo), "hi": float(hi), "n_a": int(a.size),
            "n_b": int(b.size)}


def paired_wilcoxon(a: np.ndarray, b: np.ndarray) -> dict[str, Any]:
    """Two-sided paired Wilcoxon signed-rank test on case-level values (same cases, same order)."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    ok = ~(np.isnan(a) | np.isnan(b))
    a, b = a[ok], b[ok]
    d = a - b
    if a.size < 2 or np.allclose(d, 0):
        return {"statistic": float("nan"), "p": float("nan"), "n": int(a.size), "median_diff": float(np.median(d))
                if d.size else float("nan")}
    r = stats.wilcoxon(a, b, zero_method="wilcox", alternative="two-sided")
    return {"statistic": float(r.statistic), "p": float(r.pvalue), "n": int(a.size), "median_diff": float(np.median(d))}


def spearman(x: np.ndarray, y: np.ndarray) -> dict[str, Any]:
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    ok = ~(np.isnan(x) | np.isnan(y))
    if ok.sum() < 3:
        return {"rho": float("nan"), "p": float("nan"), "n": int(ok.sum())}
    r = stats.spearmanr(x[ok], y[ok])
    return {"rho": float(r.statistic), "p": float(r.pvalue), "n": int(ok.sum())}


def holm(pvalues: list[float]) -> list[float]:
    """Holm-Bonferroni adjusted p-values (NaN entries are kept as NaN and not counted)."""
    p = np.asarray(pvalues, dtype=float)
    idx = [i for i in np.argsort(p) if not np.isnan(p[i])]
    m = len(idx)
    adj = np.full(p.shape, np.nan)
    running = 0.0
    for rank, i in enumerate(idx):
        running = max(running, min(1.0, (m - rank) * p[i]))
        adj[i] = running
    return adj.tolist()
