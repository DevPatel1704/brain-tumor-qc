"""Segmentation metrics: Dice, HD95 and average symmetric surface distance.

Empty-mask convention (configurable in ``configs/eval.yaml``, defaults below):

* both reference and prediction empty: Dice 1, HD95 0, ASD 0
* exactly one empty: Dice 0, HD95 = ASD = ``empty_penalty_mm``

The default penalty, 373.13 mm, is the diagonal of the 240x240x155 BraTS grid
at 1 mm (sqrt(240^2 + 240^2 + 155^2)), i.e. the largest possible distance. The
same constant (373.1287) is used in published BraTS-family evaluations (e.g.
arXiv:2410.22057 on BraTS-METS 2023); BraTS 2023 glioma reports use 374. We
could not locate the constant in an official BraTS 2021 document, so it is a
documented choice, configurable in configs/eval.yaml (see docs/metrics.md). We
report the fraction of penalized cases next to every HD95 mean.

HD95 is the 95th percentile of the pooled symmetric surface distances (both
directions concatenated, as in MedPy ``hd95``). Surfaces are the voxels of the
mask removed by one binary erosion with a 6-connected structuring element.
Distances are in millimetres using the voxel spacing.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage

BRATS_EMPTY_PENALTY_MM = float(np.sqrt(240**2 + 240**2 + 155**2))  # 373.13


@dataclass(frozen=True)
class EmptyPolicy:
    penalty_mm: float = BRATS_EMPTY_PENALTY_MM


def dice(ref: np.ndarray, pred: np.ndarray) -> float:
    ref = ref.astype(bool)
    pred = pred.astype(bool)
    s = int(ref.sum()) + int(pred.sum())
    if s == 0:
        return 1.0
    return float(2.0 * np.logical_and(ref, pred).sum() / s)


def _surface(mask: np.ndarray) -> np.ndarray:
    st = ndimage.generate_binary_structure(mask.ndim, 1)
    return mask & ~ndimage.binary_erosion(mask, structure=st, border_value=0)


def _crop_union(a: np.ndarray, b: np.ndarray, margin: int = 2) -> tuple[np.ndarray, np.ndarray]:
    idx = np.argwhere(a | b)
    lo = np.maximum(idx.min(0) - margin, 0)
    hi = np.minimum(idx.max(0) + margin + 1, a.shape)
    sl = tuple(slice(int(lo_), int(hi_)) for lo_, hi_ in zip(lo, hi))
    return a[sl], b[sl]


def surface_distances(ref: np.ndarray, pred: np.ndarray, spacing: tuple[float, ...]) -> tuple[np.ndarray, np.ndarray]:
    """Distances (mm) from each prediction-surface voxel to the reference surface and back.
    Both masks must be non-empty."""
    r, p = _crop_union(ref.astype(bool), pred.astype(bool))
    sr, sp = _surface(r), _surface(p)
    dt_r = ndimage.distance_transform_edt(~sr, sampling=spacing)
    dt_p = ndimage.distance_transform_edt(~sp, sampling=spacing)
    return dt_r[sp], dt_p[sr]


def hd95(ref: np.ndarray, pred: np.ndarray, spacing: tuple[float, ...] = (1.0, 1.0, 1.0),
         policy: EmptyPolicy = EmptyPolicy()) -> float:
    r, p = ref.any(), pred.any()
    if not r and not p:
        return 0.0
    if r != p:
        return policy.penalty_mm
    d1, d2 = surface_distances(ref, pred, spacing)
    return float(np.percentile(np.concatenate([d1, d2]), 95))


def asd(ref: np.ndarray, pred: np.ndarray, spacing: tuple[float, ...] = (1.0, 1.0, 1.0),
        policy: EmptyPolicy = EmptyPolicy()) -> float:
    """Average symmetric surface distance (mean of the pooled distances)."""
    r, p = ref.any(), pred.any()
    if not r and not p:
        return 0.0
    if r != p:
        return policy.penalty_mm
    d1, d2 = surface_distances(ref, pred, spacing)
    return float(np.concatenate([d1, d2]).mean())


def region_metrics(ref_regions: dict[str, np.ndarray], pred_regions: dict[str, np.ndarray],
                   spacing: tuple[float, ...] = (1.0, 1.0, 1.0), policy: EmptyPolicy = EmptyPolicy(),
                   surface: bool = True) -> dict[str, float]:
    """Dice/HD95/ASD per region plus flags for empty reference / empty prediction."""
    out: dict[str, float] = {}
    voxel_ml = float(np.prod(spacing)) / 1000.0
    for k in ref_regions:
        r, p = ref_regions[k].astype(bool), pred_regions[k].astype(bool)
        out[f"dice_{k}"] = dice(r, p)
        if surface:
            out[f"hd95_{k}"] = hd95(r, p, spacing, policy)
            out[f"asd_{k}"] = asd(r, p, spacing, policy)
        out[f"ref_empty_{k}"] = float(not r.any())
        out[f"pred_empty_{k}"] = float(not p.any())
        out[f"penalized_{k}"] = float(r.any() != p.any())
        out[f"vol_ref_ml_{k}"] = float(r.sum()) * voxel_ml
        out[f"vol_pred_ml_{k}"] = float(p.sum()) * voxel_ml
    return out
