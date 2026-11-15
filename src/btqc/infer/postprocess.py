"""Summaries stored with every prediction record: region volumes, centroid,
hemisphere, most uncertain spot and case scores. Tumor grade or stage is
deliberately NOT estimated (see docs/model_card.md)."""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy import ndimage

from btqc.data.labels import regions
from btqc.uncertainty.case_score import all_scores


def region_volumes_ml(seg: np.ndarray, spacing: tuple[float, ...], convention: str = "brats_124") -> dict[str, float]:
    r = regions(seg, convention)
    v = float(np.prod(spacing)) / 1000.0
    ncr = r["TC"] & ~r["ET"]
    ed = r["WT"] & ~r["TC"]
    return {"WT": float(r["WT"].sum() * v), "TC": float(r["TC"].sum() * v), "ET": float(r["ET"].sum() * v),
            "NCR": float(ncr.sum() * v), "ED": float(ed.sum() * v)}


def hemisphere(seg: np.ndarray, brain: np.ndarray | None) -> tuple[str | None, list[float] | None]:
    """Hemisphere of the whole-tumor centroid relative to the brain bounding-box midline (canonical RAS:
    x increases toward patient right). Approximate; midline shift is not modelled."""
    wt = seg > 0
    if not wt.any():
        return None, None
    c = np.argwhere(wt).mean(0)
    ref = brain if brain is not None and brain.any() else np.ones_like(wt)
    idx = np.argwhere(ref)
    mid = (float(np.min(idx[:, 0])) + float(np.max(idx[:, 0]))) / 2.0
    side = "right" if c[0] > mid + 2 else "left" if c[0] < mid - 2 else "midline"
    return side, [float(x) for x in c]


def hot_spot(unc: np.ndarray, size: int = 5) -> list[int]:
    """Canonical voxel index of the highest locally averaged uncertainty."""
    sm = ndimage.uniform_filter(unc.astype(np.float32), size=size)
    return [int(v) for v in np.unravel_index(int(np.argmax(sm)), sm.shape)]


def summarize(seg: np.ndarray, unc01: np.ndarray, spacing: tuple[float, ...], brain: np.ndarray | None = None,
              mi01: np.ndarray | None = None, band_width: int = 3) -> dict[str, Any]:
    side, cen = hemisphere(seg, brain)
    wt = seg > 0
    return {
        "volumes_ml": region_volumes_ml(seg, spacing),
        "hemisphere": side,
        "centroid": cen,
        "hot_spot": hot_spot(unc01),
        "scores": all_scores(unc01, wt, band_width, mi01),
        "spacing": [float(s) for s in spacing],
    }
