"""Create the nnU-Net v2 raw dataset from the canonical RAS files.

Follows nnU-Net's ``documentation/dataset_format.md`` and
``documentation/region_based_training.md`` (read for nnunetv2 2.8.1):

* images: ``{case}_{XXXX}.nii.gz`` with 0000=T1, 0001=T1ce, 0002=T2, 0003=FLAIR
  (same order as ``nnunetv2/dataset_conversion/Dataset137_BraTS21.py``)
* labels: contiguous 0..3 (edema 1, necrotic core 2, enhancing 3)
* ``dataset.json`` labels are regions, ``regions_class_order`` = [1, 2, 3], and
  the key order is preserved (``sort_keys=False``) as the docs require.
* images are not normalized here; nnU-Net applies per-channel z-scoring.

Image files are hard links to the canonical copies when the file system
allows it (no extra disk space), otherwise copies.
"""

from __future__ import annotations

import json
import os
import shutil
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import nibabel as nib
import numpy as np

from btqc.data.labels import NNUNET_REGIONS, convert, detect_convention
from btqc.data.nifti_io import load_nifti

CHANNELS = {"0": "T1", "1": "T1ce", "2": "T2", "3": "Flair"}
CHANNEL_SEQ = ("t1", "t1ce", "t2", "flair")


def dataset_name(dataset_id: int, name: str) -> str:
    return f"Dataset{dataset_id:03d}_{name}"


def dataset_json(num_training: int, name: str, description: str) -> dict[str, Any]:
    return {
        "channel_names": dict(CHANNELS),
        "labels": {"background": 0, **{k: list(v) for k, v in NNUNET_REGIONS.items()}},
        "regions_class_order": [1, 2, 3],
        "numTraining": int(num_training),
        "file_ending": ".nii.gz",
        "name": name,
        "description": description,
        "reference": "FeTS 2022 (Pati et al., arXiv:2105.05874); BraTS 2021 (Baid et al., arXiv:2107.02314)",
        "licence": "see the FeTS 2022 / BraTS 2021 data use agreement on Synapse",
        "converted_by": "btqc.train.nnunet_setup",
    }


def _link_or_copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        dst.unlink()
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def write_label(src_seg: Path, dst: Path) -> str:
    img = load_nifti(src_seg)
    seg = np.asarray(img.dataobj).astype(np.uint8)
    conv = detect_convention(np.unique(seg).tolist())
    if conv not in ("brats_124", "brats_123"):
        conv = "brats_124"  # no enhancing tumor present: 1/2 mean the same in both conventions
    out = nib.Nifti1Image(convert(seg, conv, "nnunet"), img.affine)
    out.header.set_sform(img.affine, code=1)
    out.header.set_qform(img.affine, code=1)
    dst.parent.mkdir(parents=True, exist_ok=True)
    nib.save(out, str(dst))
    return conv


def build_raw_dataset(canonical_dir: Path, raw_root: Path, dataset_id: int, name: str, train_cases: Iterable[str],
                      test_cases: Iterable[str], description: str = "") -> Path:
    out = raw_root / dataset_name(dataset_id, name)
    tr, lb, ts = out / "imagesTr", out / "labelsTr", out / "imagesTs"
    train = list(train_cases)
    for cid in train:
        for i, s in enumerate(CHANNEL_SEQ):
            _link_or_copy(canonical_dir / cid / f"{cid}_{s}.nii.gz", tr / f"{cid}_{i:04d}.nii.gz")
        write_label(canonical_dir / cid / f"{cid}_seg.nii.gz", lb / f"{cid}.nii.gz")
    for cid in test_cases:
        for i, s in enumerate(CHANNEL_SEQ):
            _link_or_copy(canonical_dir / cid / f"{cid}_{s}.nii.gz", ts / f"{cid}_{i:04d}.nii.gz")
    out.mkdir(parents=True, exist_ok=True)
    (out / "dataset.json").write_text(json.dumps(dataset_json(len(train), name, description), indent=2,
                                                 sort_keys=False), encoding="utf-8")
    return out


def install_splits(splits: list[dict[str, list[str]]], preprocessed_root: Path, dataset_id: int, name: str) -> Path:
    """Place ``splits_final.json`` where nnU-Net's ``do_split`` looks for it
    (documentation/manual_data_splits.md)."""
    d = preprocessed_root / dataset_name(dataset_id, name)
    d.mkdir(parents=True, exist_ok=True)
    p = d / "splits_final.json"
    p.write_text(json.dumps(splits, indent=1), encoding="utf-8")
    return p


def nnunet_env(repo_root: Path) -> dict[str, str]:
    d = repo_root / "data"
    return {
        "nnUNet_raw": str(d / "nnUNet_raw"),
        "nnUNet_preprocessed": str(d / "nnUNet_preprocessed"),
        "nnUNet_results": str(d / "nnUNet_results"),
        "nnUNet_extTrainer": str(repo_root / "src" / "btqc" / "train" / "trainers"),
    }
