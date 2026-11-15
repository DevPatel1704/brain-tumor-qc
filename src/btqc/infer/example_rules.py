"""RULE-BASED EXAMPLE predictor. NOT A MODEL.

Produces an example tumor outline and a hand-designed uncertainty field from
simple brightness rules, so the dashboard, API and tests can be exercised on
unlabeled scans without a trained network. Every record it writes has
``source = "example"`` and the UI labels it as an example. Its output must
never be reported as a segmentation result.

Rules (on intensities z-scored inside the brain mask):
    WT  = largest connected component of smoothed FLAIR z > 2.0
    ET  = WT and smoothed T1ce z > 2.0
    NCR = holes enclosed by ET (fill-holes per axial slice) inside WT
    TC  = ET or NCR
Soft "probabilities" are logistic functions of the distance to each rule's
threshold (slope 1 / 0.35 z-units), so the example uncertainty is highest
where a voxel is close to a threshold.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy import ndimage

from btqc.infer.postprocess import summarize
from btqc.infer.record import PredictionRecord, seg_from_prob
from btqc.uncertainty.entropy import binary_entropy, to_uint8, voxel_uncertainty

SOURCE = "example"
NOTE = "Rule-based example (brightness thresholds), not a trained model."


def _z(vol: np.ndarray, brain: np.ndarray) -> np.ndarray:
    v = vol[brain].astype(np.float64)
    sd = v.std() or 1.0
    z = np.zeros(vol.shape, dtype=np.float32)
    z[brain] = ((vol[brain] - v.mean()) / sd).astype(np.float32)
    return z


def _sig(x: np.ndarray, slope: float = 1 / 0.35) -> np.ndarray:
    return (1.0 / (1.0 + np.exp(-x * slope))).astype(np.float32)


def predict_example(vols: dict[str, np.ndarray], spacing: tuple[float, ...] = (1.0, 1.0, 1.0),
                    thr_flair: float = 2.0, thr_t1ce: float = 2.0) -> tuple[np.ndarray, np.ndarray]:
    """Return (prob (3, X, Y, Z) for WT, TC, ET; brain mask)."""
    brain = vols["flair"] != 0
    if brain.sum() < 10:
        return np.zeros((3, *brain.shape), np.float32), brain
    fz = ndimage.gaussian_filter(_z(vols["flair"], brain), 1.0)
    tz = ndimage.gaussian_filter(_z(vols["t1ce"], brain), 0.8)
    wt_hard = (fz > thr_flair) & brain
    lab, n = ndimage.label(wt_hard)
    if n:
        sizes = ndimage.sum(wt_hard, lab, index=range(1, n + 1))
        keep = lab == (int(np.argmax(sizes)) + 1)
        region = ndimage.binary_dilation(keep, iterations=4)
    else:
        region = np.zeros_like(wt_hard)
    p_wt = _sig(fz - thr_flair) * region
    p_et = _sig(tz - thr_t1ce) * (p_wt > 0.5)
    et = p_et > 0.5
    filled = np.zeros_like(et)
    for z in range(et.shape[2]):
        if et[:, :, z].any():
            filled[:, :, z] = ndimage.binary_fill_holes(et[:, :, z])
    ncr = filled & ~et & (p_wt > 0.5)
    ncr_soft = ndimage.gaussian_filter(ncr.astype(np.float32), 0.8)
    p_tc = np.maximum(p_et, np.clip(ncr_soft * 1.2, 0, 1)) * (p_wt > 0.5)
    prob = np.stack([p_wt, np.minimum(p_tc, p_wt), np.minimum(p_et, p_tc)]).astype(np.float32)
    prob[:, ~brain] = 0.0
    return prob, brain


def example_record(case_id: str, vols: dict[str, np.ndarray], spacing: tuple[float, ...],
                   extra_meta: dict[str, Any] | None = None) -> PredictionRecord:
    prob, brain = predict_example(vols, spacing)
    seg = seg_from_prob(prob)
    h = binary_entropy(prob)
    u = voxel_uncertainty(h, "mean")
    u[~brain] = 0
    meta: dict[str, Any] = {"source": SOURCE, "note": NOTE, "method": "example_rule_based", "fold": "example",
                            "members": ["rules"]}
    meta.update(summarize(seg, u, spacing, brain))
    if extra_meta:
        meta.update(extra_meta)
    return PredictionRecord(case_id, seg, prob, to_uint8(u), None, meta)
