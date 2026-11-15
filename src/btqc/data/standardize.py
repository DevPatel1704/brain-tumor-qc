"""Mitigation 3: per-case intensity standardization variants (no fitting across
cases, so no information leaks between folds).

* ``pct``: clip each sequence to its 0.5-99.5 percentile range inside the brain
  mask, then z-score inside the brain; background stays exactly 0.
* ``mode``: subtract the histogram mode of the brain voxels and divide by the
  interquartile range (a white-stripe-like normalization, robust to tumor).

The standardized images are written as a separate nnU-Net dataset. nnU-Net's
own z-scoring is still applied on top; for ``pct`` it is then nearly an
identity, so the difference to the baseline is the clipping of outliers.
"""

from __future__ import annotations

import json
from pathlib import Path

import nibabel as nib
import numpy as np

from btqc.data.nifti_io import load_nifti
from btqc.train.nnunet_setup import CHANNEL_SEQ, dataset_json, dataset_name, write_label


def standardize(vol: np.ndarray, method: str = "pct") -> np.ndarray:
    brain = vol != 0
    out = np.zeros(vol.shape, dtype=np.float32)
    v = vol[brain].astype(np.float64)
    if v.size < 10:
        return out
    if method == "pct":
        lo, hi = np.percentile(v, [0.5, 99.5])
        v = np.clip(v, lo, hi)
        sd = v.std() or 1.0
        out[brain] = ((v - v.mean()) / sd).astype(np.float32)
    elif method == "mode":
        h, e = np.histogram(v, bins=200)
        mode = 0.5 * (e[np.argmax(h)] + e[np.argmax(h) + 1])
        q1, q3 = np.percentile(v, [25, 75])
        out[brain] = ((v - mode) / ((q3 - q1) or 1.0)).astype(np.float32)
    else:
        raise ValueError(method)
    # keep background distinguishable from standardized tissue that happens to be 0
    out[brain & (out == 0)] = 1e-6
    return out


def build_standardized_dataset(canonical_dir: Path, raw_root: Path, dataset_id: int, name: str, train: list[str],
                               test: list[str], method: str = "pct") -> Path:
    out = raw_root / dataset_name(dataset_id, name)
    for split, cases in (("imagesTr", train), ("imagesTs", test)):
        for cid in cases:
            for i, s in enumerate(CHANNEL_SEQ):
                img = load_nifti(canonical_dir / cid / f"{cid}_{s}.nii.gz")
                std = standardize(img.get_fdata(dtype=np.float32), method)
                o = nib.Nifti1Image(std, img.affine)
                o.header.set_sform(img.affine, code=1)
                o.header.set_qform(img.affine, code=1)
                (out / split).mkdir(parents=True, exist_ok=True)
                nib.save(o, str(out / split / f"{cid}_{i:04d}.nii.gz"))
    for cid in train:
        write_label(canonical_dir / cid / f"{cid}_seg.nii.gz", out / "labelsTr" / f"{cid}.nii.gz")
    (out / "dataset.json").write_text(json.dumps(dataset_json(len(train), name, f"per-case {method} standardized"),
                                                 indent=2, sort_keys=False), encoding="utf-8")
    return out
