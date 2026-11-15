"""SYNTHETIC stub predictor for tests and the pipeline demo. NOT A MODEL.

Produces region probabilities from the reference mask itself: the reference
regions are smoothed, eroded or dilated by a random amount and perturbed by
noise whose strength depends on a per-site "difficulty". It exists so that the
harness, the uncertainty scores, failure detection and the dashboard can be
exercised end to end on fixtures. Records carry ``source = "synthetic"``.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scipy import ndimage

from btqc.data.labels import regions
from btqc.infer.postprocess import summarize
from btqc.infer.record import PredictionRecord, seg_from_prob
from btqc.infer.tta import MemberAccumulator
from btqc.uncertainty.entropy import to_uint8, voxel_uncertainty


def stub_members(ref_seg: np.ndarray, difficulty: float, n_members: int = 3, seed: int = 0,
                 convention: str = "brats_124") -> MemberAccumulator:
    rng = np.random.default_rng(seed)
    reg = regions(ref_seg, convention)
    acc = MemberAccumulator()
    shift = int(rng.integers(-2, 3)) if difficulty > 0.5 else 0
    for _ in range(n_members):
        ps = []
        for r in ("WT", "TC", "ET"):
            m = reg[r]
            k = int(rng.integers(0, 1 + int(3 * difficulty)))
            if k and m.any():
                op = ndimage.binary_erosion if rng.random() < 0.5 else ndimage.binary_dilation
                m = op(m, iterations=k)
            if shift:
                m = np.roll(m, shift, axis=0)
            p = ndimage.gaussian_filter(m.astype(np.float32), 1.0 + 2.0 * difficulty)
            p = np.clip(p + rng.normal(0, 0.05 + 0.25 * difficulty, p.shape).astype(np.float32), 0, 1)
            ps.append(p)
        prob = np.stack(ps)
        prob[1] = np.minimum(prob[1], prob[0])
        prob[2] = np.minimum(prob[2], prob[1])
        acc.add(prob)
    return acc


def stub_record(case_id: str, ref_seg: np.ndarray, brain: np.ndarray | None, spacing: tuple[float, ...],
                difficulty: float, fold: str, method: str = "synthetic_stub", seed: int = 0,
                convention: str = "brats_124") -> PredictionRecord:
    acc = stub_members(ref_seg, difficulty, seed=seed, convention=convention)
    prob = acc.mean()
    u = voxel_uncertainty(acc.entropy_of_mean(), "mean")
    mi = voxel_uncertainty(acc.mutual_information(), "mean")
    if brain is not None:
        prob[:, ~brain] = 0
        u[~brain] = 0
        mi[~brain] = 0
    seg = seg_from_prob(prob)
    meta: dict[str, Any] = {"source": "synthetic", "method": method, "fold": fold, "difficulty": difficulty,
                            "note": "SYNTHETIC stub predictor derived from the reference mask; not a model."}
    meta.update(summarize(seg, u, spacing, brain, mi))
    return PredictionRecord(case_id, seg, prob, to_uint8(u), to_uint8(mi), meta)
