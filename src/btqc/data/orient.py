"""Reorient volumes to canonical RAS and map indices back to the original file.

Canonical RAS here means: array index 0 increases toward patient Right (x),
index 1 toward Anterior (y), index 2 toward Superior (z), in the NIfTI RAS+
world frame of the file's affine (sform, else qform).

The axis assignment follows the viewer prototype (Appendix A of the project
brief): for each voxel axis pick the world axis it is most aligned with, as
the permutation that maximizes the sum of absolute affine entries, and the sign
of that entry. The same rule is implemented in ``web/src/nifti.js`` so the
Python pipeline and the browser agree voxel for voxel.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import permutations

import numpy as np


@dataclass(frozen=True)
class Orientation:
    """How original voxel axis ``i`` maps to canonical axis ``perm[i]`` with sign ``flip[i]``."""

    perm: tuple[int, int, int]  # world axis (0=x,1=y,2=z) for each original voxel axis
    flip: tuple[bool, bool, bool]  # True if original axis i runs opposite to its world axis
    shape: tuple[int, int, int]  # original shape

    @property
    def canonical_shape(self) -> tuple[int, int, int]:
        out = [0, 0, 0]
        for i, j in enumerate(self.perm):
            out[j] = self.shape[i]
        return (out[0], out[1], out[2])

    @property
    def is_identity(self) -> bool:
        return self.perm == (0, 1, 2) and not any(self.flip)

    def to_dict(self) -> dict[str, list[int] | list[bool]]:
        return {"perm": list(self.perm), "flip": list(self.flip), "shape": list(self.shape)}


def orientation_from_affine(affine: np.ndarray, shape: tuple[int, ...]) -> Orientation:
    a = np.asarray(affine, dtype=float)[:3, :3]
    best: tuple[float, tuple[int, ...]] = (-1.0, (0, 1, 2))
    for p in permutations(range(3)):
        score = sum(abs(a[p[i], i]) for i in range(3))
        if score > best[0] + 1e-12:
            best = (score, p)
    perm = best[1]
    flip = tuple(bool(a[perm[i], i] < 0) for i in range(3))
    return Orientation(
        perm=(perm[0], perm[1], perm[2]),
        flip=(flip[0], flip[1], flip[2]),
        shape=(int(shape[0]), int(shape[1]), int(shape[2])),
    )


def to_canonical(data: np.ndarray, affine: np.ndarray) -> tuple[np.ndarray, np.ndarray, Orientation]:
    """Return (canonical data, canonical affine, orientation). Works for 3D and for
    4D arrays with extra trailing axes (e.g. channels)."""
    o = orientation_from_affine(affine, data.shape[:3])
    # canonical axis j takes original axis inv[j]
    inv = [0, 0, 0]
    for i, j in enumerate(o.perm):
        inv[j] = i
    out = np.transpose(data, axes=(*inv, *range(3, data.ndim)))
    for j in range(3):
        if o.flip[inv[j]]:
            out = np.flip(out, axis=j)
    out = np.ascontiguousarray(out)

    aff = np.asarray(affine, dtype=float)
    new = np.eye(4)
    origin_idx = np.array([o.shape[i] - 1 if o.flip[i] else 0 for i in range(3)], dtype=float)
    for j in range(3):
        i = inv[j]
        new[:3, j] = aff[:3, i] * (-1.0 if o.flip[i] else 1.0)
    new[:3, 3] = (aff @ np.append(origin_idx, 1.0))[:3]
    return out, new, o


def canonical_to_original_index(idx: tuple[int, int, int] | np.ndarray, o: Orientation) -> tuple[int, int, int]:
    c = np.asarray(idx, dtype=int)
    out = [0, 0, 0]
    for i, j in enumerate(o.perm):
        out[i] = int(o.shape[i] - 1 - c[j]) if o.flip[i] else int(c[j])
    return (out[0], out[1], out[2])


def original_to_canonical_index(idx: tuple[int, int, int] | np.ndarray, o: Orientation) -> tuple[int, int, int]:
    v = np.asarray(idx, dtype=int)
    out = [0, 0, 0]
    for i, j in enumerate(o.perm):
        out[j] = int(o.shape[i] - 1 - v[i]) if o.flip[i] else int(v[i])
    return (out[0], out[1], out[2])


def from_canonical(data: np.ndarray, o: Orientation) -> np.ndarray:
    """Inverse of :func:`to_canonical` for the data array (e.g. to write a
    prediction back on the grid of the original file)."""
    inv = [0, 0, 0]
    for i, j in enumerate(o.perm):
        inv[j] = i
    out = data
    for j in range(3):
        if o.flip[inv[j]]:
            out = np.flip(out, axis=j)
    out = np.transpose(out, axes=(*o.perm, *range(3, data.ndim)))
    return np.ascontiguousarray(out)
