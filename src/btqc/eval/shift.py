"""Shift characterization computed from data, not from the model (E2).

Intensity shift: every case is z-scored inside its nonzero (brain) mask per
sequence, which is what nnU-Net's ZScore normalization feeds the network.
A fixed-bin histogram of the z-scored brain voxels is stored per case and
sequence. A group profile is the mean of its case histograms. Distances
between profiles are Wasserstein-1 and Kolmogorov-Smirnov (max CDF gap),
both computed on the binned distributions.

Embedding shift: Frechet distance between Gaussian fits (mean, covariance)
of encoder bottleneck features of two groups.

Gap prediction: a least-squares line gap ~ shift over the held-out folds,
with a leave-one-fold-out residual spread as the uncertainty of an estimate.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np
from scipy import linalg

from btqc.data.discover import SEQUENCES
from btqc.data.nifti_io import load_nifti

BINS = np.linspace(-4.0, 6.0, 101)
CENTERS = 0.5 * (BINS[1:] + BINS[:-1])


def case_histogram(vol: np.ndarray, bins: np.ndarray = BINS) -> np.ndarray:
    """Normalized histogram of z-scored nonzero voxels; out-of-range values are clipped to the edge bins."""
    v = vol[vol != 0].astype(np.float64)
    if v.size < 2:
        return np.full(len(bins) - 1, np.nan)
    sd = v.std()
    z = (v - v.mean()) / (sd if sd > 0 else 1.0)
    z = np.clip(z, bins[0], bins[-1] - 1e-9)
    h, _ = np.histogram(z, bins=bins)
    return h / h.sum()


def group_profile(hists: list[np.ndarray]) -> np.ndarray:
    h = np.nanmean(np.stack(hists), axis=0)
    return h / h.sum()


def wasserstein_hist(p: np.ndarray, q: np.ndarray, centers: np.ndarray = CENTERS) -> float:
    """W1 between two distributions on the same bins = integral of |CDF_p - CDF_q|."""
    width = float(centers[1] - centers[0])
    return float(np.abs(np.cumsum(p) - np.cumsum(q)).sum() * width)


def ks_hist(p: np.ndarray, q: np.ndarray) -> float:
    return float(np.abs(np.cumsum(p) - np.cumsum(q)).max())


def frechet_distance(feat_a: np.ndarray, feat_b: np.ndarray, eps: float = 1e-6) -> float:
    """Frechet distance between Gaussian fits of two feature sets of shape (n, d)."""
    mu1, mu2 = feat_a.mean(0), feat_b.mean(0)
    s1 = np.cov(feat_a, rowvar=False) + eps * np.eye(feat_a.shape[1])
    s2 = np.cov(feat_b, rowvar=False) + eps * np.eye(feat_b.shape[1])
    covmean = linalg.sqrtm(s1 @ s2)
    if np.iscomplexobj(covmean):
        covmean = covmean.real
    return float(((mu1 - mu2) ** 2).sum() + np.trace(s1 + s2 - 2 * covmean))


def profile_distances(target: Mapping[str, np.ndarray], reference: Mapping[str, np.ndarray]) -> dict[str, float]:
    """Per-sequence W1 and KS between a target profile and a reference profile, plus their means."""
    out: dict[str, float] = {}
    for s in target:
        out[f"w1_{s}"] = wasserstein_hist(target[s], reference[s])
        out[f"ks_{s}"] = ks_hist(target[s], reference[s])
    w = [v for k, v in out.items() if k.startswith("w1_")]
    k = [v for kk, v in out.items() if kk.startswith("ks_")]
    out["w1_mean"] = float(np.mean(w))
    out["ks_mean"] = float(np.mean(k))
    return out


def fit_gap_model(shift: np.ndarray, gap: np.ndarray) -> dict[str, Any]:
    """Least-squares gap = a + b * shift, with leave-one-out residual spread."""
    x = np.asarray(shift, float)
    y = np.asarray(gap, float)
    ok = ~(np.isnan(x) | np.isnan(y))
    x, y = x[ok], y[ok]
    n = x.size
    if n < 3:
        return {"n": int(n), "a": float("nan"), "b": float("nan"), "loo_rmse": float("nan")}
    b, a = np.polyfit(x, y, 1)
    res = []
    for i in range(n):
        m = np.arange(n) != i
        bi, ai = np.polyfit(x[m], y[m], 1)
        res.append(y[i] - (ai + bi * x[i]))
    return {"n": int(n), "a": float(a), "b": float(b), "loo_rmse": float(np.sqrt(np.mean(np.square(res))))}


def estimate_performance(model: Mapping[str, Any], shift_value: float, insite_dice: float) -> dict[str, float]:
    """Estimated held-out Dice for a new site = in-site Dice minus predicted gap, +- 2 LOO RMSE.
    This is an ESTIMATE from very few folds, not a measurement."""
    if np.isnan(model.get("a", float("nan"))):
        return {"estimate": float("nan"), "lo": float("nan"), "hi": float("nan")}
    gap = model["a"] + model["b"] * shift_value
    est = insite_dice - gap
    r = 2 * model["loo_rmse"]
    return {"estimate": float(est), "lo": float(est - r), "hi": float(est + r), "predicted_gap": float(gap)}


def case_hists(can: Path, ids: list[str], cache: Path) -> dict[str, dict[str, np.ndarray]]:
    store: dict[str, dict[str, np.ndarray]] = {}
    if cache.exists():
        with np.load(cache) as z:
            for k in z.files:
                cid, s = k.rsplit("__", 1)
                store.setdefault(cid, {})[s] = z[k]
    todo = [c for c in ids if c not in store]
    for i, cid in enumerate(todo):
        store[cid] = {s: case_histogram(np.asarray(load_nifti(can / cid / f"{cid}_{s}.nii.gz").dataobj))
                      for s in SEQUENCES}
        if (i + 1) % 25 == 0:
            print(f"  histograms {i + 1}/{len(todo)}", flush=True)
    if todo:
        cache.parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(cache, **{  # type: ignore[arg-type]
           f"{c}__{s}": h for c, d in store.items() for s, h in d.items()})
    return store
