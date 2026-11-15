"""Case-level uncertainty scores.

Primary score (``boundary_band``): mean voxel uncertainty inside a band of
``width`` voxels on both sides of the predicted whole-tumor boundary:

    band = dilate(WT, width) AND NOT erode(WT, width)

If the predicted whole tumor is empty, the band is empty and the score is NaN.
The trust gate treats NaN as "needs review" (fail-safe), so the flag still
depends only on the score and the review limit (requirement R4).

Alternatives used in the comparison: mean uncertainty inside the predicted
whole tumor (``wt_mean``) and mean member disagreement (mutual information)
inside the band (``band_disagreement``).
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage


def boundary_band(wt: np.ndarray, width: int = 3) -> np.ndarray:
    wt = wt.astype(bool)
    if not wt.any():
        return np.zeros_like(wt)
    st = ndimage.generate_binary_structure(wt.ndim, 1)
    outer = ndimage.binary_dilation(wt, structure=st, iterations=width)
    inner = ndimage.binary_erosion(wt, structure=st, iterations=width, border_value=0)
    return outer & ~inner


def masked_mean(u: np.ndarray, mask: np.ndarray) -> float:
    if not mask.any():
        return float("nan")
    return float(u[mask].mean())


def score_boundary_band(u: np.ndarray, wt_pred: np.ndarray, width: int = 3) -> float:
    return masked_mean(u, boundary_band(wt_pred, width))


def score_wt_mean(u: np.ndarray, wt_pred: np.ndarray) -> float:
    return masked_mean(u, wt_pred.astype(bool))


def all_scores(u: np.ndarray, wt_pred: np.ndarray, width: int = 3, mi: np.ndarray | None = None) -> dict[str, float]:
    band = boundary_band(wt_pred, width)
    out = {"boundary_band": masked_mean(u, band), "wt_mean": masked_mean(u, wt_pred.astype(bool))}
    if mi is not None:
        out["band_disagreement"] = masked_mean(mi, band)
    return out


SCORE_FUNCTIONS = ("boundary_band", "wt_mean", "band_disagreement")
