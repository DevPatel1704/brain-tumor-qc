"""Calibration: expected calibration error and reliability diagrams.

We calibrate the per-region positive-class probability (sigmoid output of a
region-based model): for each of ``n_bins`` equal-width bins on [0, 1], the
mean predicted probability is compared with the observed fraction of voxels
inside the reference region. ECE is the voxel-weighted mean absolute gap.

Counts are accumulated per case into a :class:`ReliabilityAccumulator`, so a
whole test set can be evaluated without holding all voxels in memory.

Voxel selection: ``band`` uses voxels within ``band_width`` voxels of the
predicted or reference whole tumor (dilated union), so background does not
dominate; ``volume`` uses every voxel inside the brain (nonzero) mask.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage


@dataclass
class ReliabilityAccumulator:
    n_bins: int = 15
    count: np.ndarray = field(init=False)
    sum_p: np.ndarray = field(init=False)
    sum_y: np.ndarray = field(init=False)

    def __post_init__(self) -> None:
        self.count = np.zeros(self.n_bins, dtype=np.int64)
        self.sum_p = np.zeros(self.n_bins, dtype=np.float64)
        self.sum_y = np.zeros(self.n_bins, dtype=np.float64)

    def add(self, p: np.ndarray, y: np.ndarray, mask: np.ndarray | None = None) -> None:
        p = np.asarray(p, dtype=np.float64)
        y = np.asarray(y).astype(bool)
        if mask is not None:
            p, y = p[mask], y[mask]
        p, y = p.ravel(), y.ravel()
        b = np.clip((p * self.n_bins).astype(np.int64), 0, self.n_bins - 1)
        self.count += np.bincount(b, minlength=self.n_bins)
        self.sum_p += np.bincount(b, weights=p, minlength=self.n_bins)
        self.sum_y += np.bincount(b, weights=y.astype(np.float64), minlength=self.n_bins)

    def merge(self, other: ReliabilityAccumulator) -> None:
        self.count += other.count
        self.sum_p += other.sum_p
        self.sum_y += other.sum_y

    def ece(self) -> float:
        n = self.count.sum()
        if n == 0:
            return float("nan")
        nz = self.count > 0
        gap = np.abs(self.sum_p[nz] / self.count[nz] - self.sum_y[nz] / self.count[nz])
        return float((self.count[nz] * gap).sum() / n)

    def curve(self) -> list[dict[str, float]]:
        edges = np.linspace(0, 1, self.n_bins + 1)
        out = []
        for i in range(self.n_bins):
            c = int(self.count[i])
            out.append({
                "bin_lo": float(edges[i]), "bin_hi": float(edges[i + 1]), "count": c,
                "confidence": float(self.sum_p[i] / c) if c else float("nan"),
                "accuracy": float(self.sum_y[i] / c) if c else float("nan"),
            })
        return out


def ece(p: np.ndarray, y: np.ndarray, n_bins: int = 15, mask: np.ndarray | None = None) -> float:
    acc = ReliabilityAccumulator(n_bins)
    acc.add(p, y, mask)
    return acc.ece()


def calibration_mask(pred_wt: np.ndarray, ref_wt: np.ndarray, brain: np.ndarray | None, mode: str = "band",
                     band_width: int = 5) -> np.ndarray:
    if mode == "volume":
        return brain.astype(bool) if brain is not None else np.ones(pred_wt.shape, dtype=bool)
    if mode != "band":
        raise ValueError(f"unknown mode {mode!r}")
    u = pred_wt.astype(bool) | ref_wt.astype(bool)
    if not u.any():
        return u
    st = ndimage.generate_binary_structure(u.ndim, 1)
    m = ndimage.binary_dilation(u, structure=st, iterations=band_width)
    if brain is not None:
        m &= brain.astype(bool)
    return m
