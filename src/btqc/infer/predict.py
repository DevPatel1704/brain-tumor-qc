"""nnU-Net v2 inference producing prediction records with uncertainty.

Members = trained models of one fold (seeds) x flip TTA. Each member runs the
nnU-Net predictor with its own mirroring disabled (see tta.py). Inputs are the
canonical RAS NIfTI files written by ``make convert``; nnU-Net's default
SimpleITK I/O orders arrays (z, y, x), so arrays are transposed on the way in
and out, as ``nnUNetPredictor.predict_single_npy_array`` documents.
"""

from __future__ import annotations

import time
from functools import partial
from pathlib import Path
from typing import Any

import numpy as np

from btqc.data.discover import SEQUENCES
from btqc.data.nifti_io import load_nifti
from btqc.infer.postprocess import summarize
from btqc.infer.record import PredictionRecord, save_record, seg_from_prob
from btqc.infer.tta import MemberAccumulator, flip_sets, predict_with_flips
from btqc.uncertainty.entropy import to_uint8, voxel_uncertainty


def load_canonical_case(canonical_dir: Path, case_id: str) -> tuple[np.ndarray, tuple[float, ...], dict[str, Any]]:
    """(C, X, Y, Z) float32 image in channel order t1, t1ce, t2, flair, and spacing."""
    chans = []
    spacing: tuple[float, ...] = (1.0, 1.0, 1.0)
    for s in SEQUENCES:
        img = load_nifti(canonical_dir / case_id / f"{case_id}_{s}.nii.gz")
        chans.append(img.get_fdata(dtype=np.float32))
        spacing = tuple(float(z) for z in img.header.get_zooms()[:3])
    return np.stack(chans), spacing, {}


class NnunetMember:
    """One trained nnU-Net model (one fold index) wrapped as image -> region probabilities."""

    def __init__(self, model_folder: Path, fold_index: int, checkpoint: str = "checkpoint_final.pth",
                 device: str = "cuda", tile_step_size: float = 0.5):
        import os

        import torch

        from btqc.config import REPO_ROOT
        from btqc.train.nnunet_setup import nnunet_env

        # nnU-Net resolves custom trainer classes (and its folders) from the environment
        for k, v in nnunet_env(REPO_ROOT).items():
            os.environ.setdefault(k, v)
        from nnunetv2.inference.predict_from_raw_data import nnUNetPredictor

        dev =torch.device(device if device != "cuda" or torch.cuda.is_available() else "cpu")
        self.predictor = nnUNetPredictor(tile_step_size=tile_step_size, use_gaussian=True, use_mirroring=False,
                                         perform_everything_on_device=dev.type == "cuda", device=dev, verbose=False,
                                         allow_tqdm=False)
        self.predictor.initialize_from_trained_model_folder(str(model_folder), use_folds=(fold_index,),
                                                            checkpoint_name=checkpoint)
        self.fold_index = fold_index

    def __call__(self, image_cxyz: np.ndarray, spacing_xyz: tuple[float, ...]) -> np.ndarray:
        img = np.ascontiguousarray(image_cxyz.transpose(0, 3, 2, 1))  # -> (C, z, y, x) as SimpleITK
        props = {"spacing": [spacing_xyz[2], spacing_xyz[1], spacing_xyz[0]]}
        _, prob = self.predictor.predict_single_npy_array(img, props, None, None, True)
        return np.ascontiguousarray(np.asarray(prob, dtype=np.float32).transpose(0, 3, 2, 1))


def predict_case(members: list[Any], image: np.ndarray, spacing: tuple[float, ...], flips: list[tuple[int, ...]],
                 case_id: str, meta: dict[str, Any], band_width: int = 3) -> PredictionRecord:
    acc = MemberAccumulator()
    t0 = time.time()
    for m in members:
        predict_with_flips(partial(m, spacing_xyz=spacing), image, flips, acc)
    prob = acc.mean()
    brain = image[3] != 0
    u = voxel_uncertainty(acc.entropy_of_mean(), "mean")
    mi = voxel_uncertainty(acc.mutual_information(), "mean")
    u[~brain] = 0
    mi[~brain] = 0
    seg = seg_from_prob(prob)
    out = {"source": "model", "n_members": acc.n, "flips": [list(f) for f in flips], "seconds": time.time() - t0}
    out.update(meta)
    out.update(summarize(seg, u, spacing, brain, mi, band_width))
    return PredictionRecord(case_id, seg, prob, to_uint8(u), to_uint8(mi), out)


def predict_folder_nnunet(folder: Path, model_folder: Path, out_root: Path, job_id: str,
                          fold_indices: tuple[int, ...] = (0,), tta: bool = True) -> str:
    """Predict one uploaded case (files upload_<seq>.nii.gz in ``folder``) for the API.
    The upload is reoriented to RAS with the same code as the batch pipeline."""
    from btqc.data.orient import to_canonical

    chans = []
    spacing: tuple[float, ...] = (1.0, 1.0, 1.0)
    for s in SEQUENCES:
        img = load_nifti(folder / f"upload_{s}.nii.gz")
        can, aff, _ = to_canonical(img.get_fdata(dtype=np.float32), img.affine)
        chans.append(can)
        spacing = tuple(float(np.linalg.norm(aff[:3, j])) for j in range(3))
    members = [NnunetMember(model_folder, i) for i in fold_indices]
    cid = f"upload_{job_id}"
    rec = predict_case(members, np.stack(chans), spacing, flip_sets() if tta else [()], cid,
                       {"method": "live", "fold": "live", "model_folder": str(model_folder)})
    save_record(rec, out_root / "live" / "live")
    return cid
