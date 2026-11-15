"""Flip test-time augmentation and streaming member accumulation.

nnU-Net's built-in mirroring averages logits inside the predictor, which hides
the individual members. For uncertainty we need each member's probabilities,
so we disable nnU-Net mirroring and flip the input ourselves; every (model,
flip) pair is one member. Members are accumulated as running sums so memory
does not grow with the number of members.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from itertools import combinations

import numpy as np

from btqc.uncertainty.entropy import binary_entropy


def flip_sets(axes: Iterable[int] = (0, 1, 2), max_members: int | None = None) -> list[tuple[int, ...]]:
    """Identity plus every combination of the given spatial axes (8 for three axes)."""
    ax = tuple(axes)
    out: list[tuple[int, ...]] = [()]
    for k in range(1, len(ax) + 1):
        out += list(combinations(ax, k))
    return out[:max_members] if max_members else out


class MemberAccumulator:
    """Running mean of member probabilities and of member entropies (for mutual information)."""

    def __init__(self) -> None:
        self.n = 0
        self.sum_p: np.ndarray | None = None
        self.sum_h: np.ndarray | None = None

    def add(self, p: np.ndarray) -> None:
        p = np.asarray(p, dtype=np.float32)
        h = binary_entropy(p)
        if self.sum_p is None:
            self.sum_p, self.sum_h = p.copy(), h
        else:
            self.sum_p += p
            assert self.sum_h is not None
            self.sum_h += h
        self.n += 1

    def mean(self) -> np.ndarray:
        assert self.sum_p is not None and self.n > 0
        return self.sum_p / self.n

    def entropy_of_mean(self) -> np.ndarray:
        return binary_entropy(self.mean())

    def mutual_information(self) -> np.ndarray:
        assert self.sum_h is not None
        return np.clip(self.entropy_of_mean() - self.sum_h / self.n, 0.0, None)


def predict_with_flips(predict: Callable[[np.ndarray], np.ndarray], image: np.ndarray, flips: list[tuple[int, ...]],
                       acc: MemberAccumulator) -> None:
    """``image`` is (C, X, Y, Z); ``predict`` maps it to region probabilities (R, X, Y, Z).
    Each flip is applied to the spatial axes, predicted, and flipped back."""
    for f in flips:
        sp = tuple(a + 1 for a in f)
        x = np.flip(image, axis=sp) if f else image
        p = predict(np.ascontiguousarray(x))
        acc.add(np.flip(p, axis=sp) if f else p)
