"""Voxel-wise predictive uncertainty from ensemble members.

Region-based nnU-Net models output one sigmoid probability per region (WT, TC,
ET). Members (ensemble models, TTA flips or MC-dropout samples) are averaged
first, then the binary entropy of the mean is taken per region, in bits, so
every value lies in [0, 1]. The voxel map shown in the dashboard is the mean
over regions.

Mutual information (expected entropy subtracted from the entropy of the mean)
measures member disagreement and is provided as an alternative.
"""

from __future__ import annotations

import numpy as np

EPS = 1e-7


def binary_entropy(p: np.ndarray) -> np.ndarray:
    """Entropy in bits of a Bernoulli probability (elementwise), in [0, 1]."""
    p = np.clip(np.asarray(p, dtype=np.float32), EPS, 1 - EPS)
    return -(p * np.log2(p) + (1 - p) * np.log2(1 - p))


def categorical_entropy(p: np.ndarray, axis: int = 0, normalize: bool = True) -> np.ndarray:
    """Entropy of class probabilities along ``axis``; normalized by log(C) to [0, 1]."""
    p = np.clip(np.asarray(p, dtype=np.float32), EPS, 1.0)
    h = -(p * np.log(p)).sum(axis=axis)
    if normalize:
        h = h / np.log(p.shape[axis])
    return h


def ensemble_mean(members: np.ndarray) -> np.ndarray:
    """Members have shape (M, R, ...); returns (R, ...)."""
    return np.asarray(members, dtype=np.float32).mean(axis=0)


def predictive_entropy(members: np.ndarray) -> np.ndarray:
    """Per-region binary entropy of the ensemble mean, shape (R, ...)."""
    return binary_entropy(ensemble_mean(members))


def mutual_information(members: np.ndarray) -> np.ndarray:
    """Per-region mutual information (disagreement), shape (R, ...), in bits, >= 0."""
    m = np.asarray(members, dtype=np.float32)
    mi = binary_entropy(m.mean(axis=0)) - binary_entropy(m).mean(axis=0)
    return np.clip(mi, 0.0, None)


def voxel_uncertainty(region_entropy: np.ndarray, reduce: str = "mean") -> np.ndarray:
    """Collapse per-region uncertainty (R, ...) into one voxel map."""
    if reduce == "mean":
        return region_entropy.mean(axis=0)
    if reduce == "max":
        return region_entropy.max(axis=0)
    if reduce == "wt":
        return region_entropy[0]
    raise ValueError(f"unknown reduce {reduce!r}")


def to_uint8(u: np.ndarray) -> np.ndarray:
    """Uncertainty in [0, 1] to uint8 0..255 for the viewer bundle."""
    return np.round(np.clip(u, 0.0, 1.0) * 255).astype(np.uint8)
