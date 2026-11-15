"""Failure detection: failure labels, AUROC with bootstrap intervals,
risk-coverage curves and the review-limit selection rule.

A case *fails* if WT Dice < tau or ET Dice < tau (tau in configs/uncertainty.yaml,
fixed before any held-out evaluation).

Risk-coverage: cases are sorted by score ascending (most certain first); at
coverage c the lowest-uncertainty fraction c is retained. We report mean Dice
of the retained set against coverage, the area under that curve (higher is
better), the area under the risk curve with risk = 1 - Dice (AURC, lower is
better), and the gain in retained mean Dice at 80% coverage over 100%.
"""

from __future__ import annotations

from typing import Any

import numpy as np


def failure_labels(dice_wt: np.ndarray, dice_et: np.ndarray, tau: float) -> np.ndarray:
    return (np.asarray(dice_wt) < tau) | (np.asarray(dice_et) < tau)


def auroc(scores: np.ndarray, failed: np.ndarray) -> float:
    """AUROC of the score for detecting failures (higher score = more likely failure).
    NaN scores are ranked as most uncertain, matching the fail-safe gate."""
    s = np.asarray(scores, dtype=float)
    y = np.asarray(failed).astype(bool)
    if y.all() or (~y).all():
        return float("nan")
    s = np.where(np.isnan(s), np.inf, s)
    # Mann-Whitney U with average ranks for ties
    from scipy.stats import rankdata

    r = rankdata(s)
    n1, n0 = int(y.sum()), int((~y).sum())
    return float((r[y].sum() - n1 * (n1 + 1) / 2) / (n1 * n0))


def bootstrap_auroc(scores: np.ndarray, failed: np.ndarray, n_boot: int = 2000, seed: int = 0,
                    alpha: float = 0.05) -> dict[str, float]:
    rng = np.random.default_rng(seed)
    s = np.asarray(scores, dtype=float)
    y = np.asarray(failed).astype(bool)
    point = auroc(s, y)
    vals = []
    n = len(s)
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        v = auroc(s[idx], y[idx])
        if not np.isnan(v):
            vals.append(v)
    if not vals:
        return {"auroc": point, "lo": float("nan"), "hi": float("nan"), "n_boot_valid": 0}
    lo, hi = np.percentile(vals, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return {"auroc": point, "lo": float(lo), "hi": float(hi), "n_boot_valid": len(vals)}


def risk_coverage(scores: np.ndarray, dice: np.ndarray) -> dict[str, Any]:
    s = np.asarray(scores, dtype=float)
    d = np.asarray(dice, dtype=float)
    n = len(s)
    if n == 0:
        return {"coverage": [], "mean_dice": [], "aurc": float("nan"), "auc_dice": float("nan")}
    order = np.argsort(np.where(np.isnan(s), np.inf, s), kind="stable")
    cum = np.cumsum(d[order])
    k = np.arange(1, n + 1)
    cov = k / n
    mean_dice = cum / k
    risk = 1 - mean_dice
    out = {
        "coverage": cov.tolist(),
        "mean_dice": mean_dice.tolist(),
        "aurc": float(np.mean(risk)),
        "auc_dice": float(np.mean(mean_dice)),
        "dice_full": float(mean_dice[-1]),
    }
    out["dice_at_80"] = dice_at_coverage(cov, mean_dice, 0.8)
    out["gain_at_80"] = out["dice_at_80"] - out["dice_full"]
    # oracle: sort by true Dice, best possible ordering
    od = np.sort(d)[::-1]
    out["oracle_aurc"] = float(np.mean(1 - np.cumsum(od) / k))
    return out


def dice_at_coverage(cov: np.ndarray, mean_dice: np.ndarray, c: float) -> float:
    """Mean Dice of the retained set at the largest coverage <= c (at least one case)."""
    cov = np.asarray(cov)
    i = max(int(np.searchsorted(cov, c + 1e-12, side="right")) - 1, 0)
    return float(np.asarray(mean_dice)[i])


def select_review_limit(val_scores: np.ndarray, rule: dict[str, Any], val_failed: np.ndarray | None = None) -> float:
    """Pick the review limit on in-site validation data using the rule from the config.

    rule = {"method": "quantile", "q": 0.8}   flag roughly the top 20 % most uncertain cases
    rule = {"method": "youden"}               maximize TPR - FPR on validation failures
    rule = {"method": "fixed", "value": x}
    """
    s = np.asarray(val_scores, dtype=float)
    s = s[~np.isnan(s)]
    m = rule["method"]
    if m == "fixed":
        return float(rule["value"])
    if s.size == 0:
        raise ValueError("no finite validation scores")
    if m == "quantile":
        return float(np.quantile(s, rule["q"]))
    if m == "youden":
        if val_failed is None:
            raise ValueError("youden rule needs validation failure labels")
        y = np.asarray(val_failed, dtype=bool)
        allsc = np.asarray(val_scores, dtype=float)
        finite = ~np.isnan(allsc)
        allsc, y = allsc[finite], y[finite]
        if y.all() or (~y).all():
            return float(np.quantile(allsc, rule.get("fallback_q", 0.8)))
        best, best_t = -np.inf, float(np.median(allsc))
        for t in np.unique(allsc):
            flagged = allsc > t
            j = flagged[y].mean() - flagged[~y].mean()
            if j > best:
                best, best_t = j, float(t)
        return best_t
    raise ValueError(f"unknown review-limit rule {m!r}")
