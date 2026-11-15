"""BraTS label conventions, tumor regions and the nnU-Net label remapping.

BraTS labels (two releases exist):
    1 necrotic / non-enhancing core, 2 edema, 4 enhancing tumor   ("brats_124")
    1 necrotic / non-enhancing core, 2 edema, 3 enhancing tumor   ("brats_123")

Regions:  WT = {NCR, ED, ET},  TC = {NCR, ET},  ET = {ET}.

nnU-Net needs contiguous labels. We use the mapping of nnU-Net v2's own
``Dataset137_BraTS21`` conversion (``nnunetv2/dataset_conversion``):
    edema -> 1, necrotic core -> 2, enhancing -> 3
so that the regions in ``dataset.json`` are nested and ordered:
    whole tumor = [1, 2, 3], tumor core = [2, 3], enhancing tumor = [3].
"""

from __future__ import annotations

from collections.abc import Iterable

import numpy as np

REGIONS: tuple[str, ...] = ("WT", "TC", "ET")

# semantic name -> label value, per convention
CONVENTIONS: dict[str, dict[str, int]] = {
    "brats_124": {"ncr": 1, "ed": 2, "et": 4},
    "brats_123": {"ncr": 1, "ed": 2, "et": 3},
    "nnunet": {"ed": 1, "ncr": 2, "et": 3},
}

# nnU-Net region definitions in the internal (contiguous) label space.
NNUNET_REGIONS: dict[str, list[int]] = {
    "whole tumor": [1, 2, 3],
    "tumor core": [2, 3],
    "enhancing tumor": [3],
}
NNUNET_REGION_TO_SHORT = {"whole tumor": "WT", "tumor core": "TC", "enhancing tumor": "ET"}


def detect_convention(values: Iterable[int]) -> str:
    """Decide the BraTS convention from the label values present in segmentations."""
    v = {int(x) for x in values} - {0}
    if not v:
        return "unknown"
    if v <= {1, 2, 4} and 4 in v:
        return "brats_124"
    if v <= {1, 2, 3} and 3 in v:
        return "brats_123"
    if v <= {1, 2}:
        return "ambiguous_no_enhancing"
    return "unknown:" + ",".join(map(str, sorted(v)))


def convert(seg: np.ndarray, src: str, dst: str) -> np.ndarray:
    """Convert a label volume between conventions. Unknown values raise."""
    s, d = CONVENTIONS[src], CONVENTIONS[dst]
    allowed = {0, *s.values()}
    present = set(np.unique(seg).tolist())
    if not present <= allowed:
        raise ValueError(f"labels {sorted(present - allowed)} not in convention {src}")
    out = np.zeros(seg.shape, dtype=np.uint8)
    for name, val in s.items():
        out[seg == val] = d[name]
    return out


def regions(seg: np.ndarray, convention: str) -> dict[str, np.ndarray]:
    """Boolean WT/TC/ET masks from a label volume in the given convention."""
    c = CONVENTIONS[convention]
    ncr, ed, et = seg == c["ncr"], seg == c["ed"], seg == c["et"]
    return {"WT": ncr | ed | et, "TC": ncr | et, "ET": et}


def regions_from_nnunet_definition(seg: np.ndarray) -> dict[str, np.ndarray]:
    """Regions computed exactly the way nnU-Net reads ``dataset.json`` region labels."""
    return {NNUNET_REGION_TO_SHORT[k]: np.isin(seg, v) for k, v in NNUNET_REGIONS.items()}


def labels_from_regions(wt: np.ndarray, tc: np.ndarray, et: np.ndarray, convention: str = "brats_124") -> np.ndarray:
    """Inverse of :func:`regions` for nested region masks (ET within TC within WT).

    Later regions overwrite earlier ones, matching nnU-Net's ``regions_class_order``.
    """
    c = CONVENTIONS[convention]
    out = np.zeros(wt.shape, dtype=np.uint8)
    out[wt] = c["ed"]
    out[tc] = c["ncr"]
    out[et] = c["et"]
    return out
