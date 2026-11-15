"""Synthetic fixtures for tests and CI. Everything here is SYNTHETIC EXAMPLE DATA.

Each case is a small volume (default 32x32x24) with an ellipsoid "brain", an
ellipsoid tumor (edema shell, enhancing ring, necrotic core) and four fake
sequences with BraTS-like relative contrasts. A fake institution table is
written in the FeTS partitioning format. Institutions get different intensity
gains and gamma so that site shift exists in the fixtures.

    python -m btqc.data.fixtures --out tests/_fixtures --n-cases 12
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import nibabel as nib
import numpy as np
from scipy import ndimage

from btqc.data.discover import SEQUENCES

# Affine of the real FeTS/BraTS files: diag(-1, -1, 1) with an offset (LPS voxel axes).
LPS_AFFINE = np.array([[-1.0, 0, 0, 0], [0, -1.0, 0, 239.0], [0, 0, 1.0, 0], [0, 0, 0, 1]])

# mean intensity per tissue: background, brain, edema, necrotic core, enhancing
_CONTRAST = {
    "t1": (0, 420, 330, 220, 380),
    "t1ce": (0, 430, 400, 160, 950),
    "t2": (0, 320, 720, 820, 520),
    "flair": (0, 300, 830, 420, 620),
}


@dataclass
class SyntheticCase:
    case_id: str
    institution: int
    images: dict[str, np.ndarray]
    seg: np.ndarray  # BraTS 1/2/4 convention
    affine: np.ndarray


def _ellipsoid(shape: tuple[int, int, int], center: np.ndarray, radii: np.ndarray) -> np.ndarray:
    g = np.indices(shape, dtype=np.float32)
    d = sum(((g[i] - center[i]) / radii[i]) ** 2 for i in range(3))
    return d <= 1.0


def make_case(
    case_id: str,
    institution: int = 1,
    shape: tuple[int, int, int] = (32, 32, 24),
    seed: int = 0,
    with_enhancing: bool = True,
    affine: np.ndarray | None = None,
) -> SyntheticCase:
    rng = np.random.default_rng(seed)
    s = np.array(shape, dtype=np.float32)
    brain = _ellipsoid(shape, s / 2 - 0.5, s * np.array([0.42, 0.45, 0.42]))
    c = s / 2 + rng.uniform(-0.12, 0.12, 3) * s
    r_ed = s * rng.uniform(0.16, 0.22, 3)
    r_core = r_ed * rng.uniform(0.45, 0.6)
    edema = _ellipsoid(shape, c, r_ed) & brain
    core = _ellipsoid(shape, c, r_core) & brain
    inner = _ellipsoid(shape, c, r_core * 0.6) & brain
    seg = np.zeros(shape, dtype=np.uint8)
    seg[edema] = 2
    if with_enhancing:
        seg[core] = 4
        seg[inner] = 1
    else:
        seg[core] = 1
    tissue = np.zeros(shape, dtype=np.int64)
    tissue[brain] = 1
    tissue[seg == 2] = 2
    tissue[seg == 1] = 3
    tissue[seg == 4] = 4
    gain = 1.0 + 0.15 * (institution % 5 - 2)
    gamma = 1.0 + 0.08 * ((institution * 7) % 3 - 1)
    images = {}
    for seq in SEQUENCES:
        lut = np.array(_CONTRAST[seq], dtype=np.float32)
        img = lut[tissue]
        img = ndimage.gaussian_filter(img, 0.7)
        img = img + rng.normal(0, 18, shape).astype(np.float32)
        img = np.clip(img, 0, None)
        img = (img / 1000.0) ** gamma * 1000.0 * gain
        img[~brain] = 0  # skull-stripped: exactly zero background
        images[seq] = np.round(img).astype(np.int16)
    return SyntheticCase(case_id, institution, images, seg, LPS_AFFINE.copy() if affine is None else affine)


def write_case(case: SyntheticCase, root: Path, layout: str = "flat", gz: bool = True, with_seg: bool = True) -> Path:
    """Write a case in the FeTS training layout (``flat``) or the wrapped
    validation layout (``wrapped``: each file inside a directory of the same name)."""
    ext = ".nii.gz" if gz else ".nii"
    case_dir = root / case.case_id
    items = dict(case.images)
    if with_seg:
        items["seg"] = case.seg
    for seq, arr in items.items():
        name = f"{case.case_id}_{seq}{ext}"
        target = case_dir / name / name if layout == "wrapped" else case_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        img = nib.Nifti1Image(arr, case.affine)
        img.header.set_sform(case.affine, code=1)
        img.header.set_qform(case.affine, code=1)
        nib.save(img, str(target))
    return case_dir


def make_dataset(
    root: Path,
    n_cases: int = 12,
    institutions: tuple[int, ...] = (1, 1, 1, 18, 18, 18, 5, 5, 20, 21, 12, 13),
    shape: tuple[int, int, int] = (32, 32, 24),
    layout: str = "flat",
    with_seg: bool = True,
    seed: int = 0,
) -> list[SyntheticCase]:
    """Write ``n_cases`` synthetic cases plus ``partitioning_synthetic.csv`` under ``root``."""
    root.mkdir(parents=True, exist_ok=True)
    cases = []
    for k in range(n_cases):
        inst = institutions[k % len(institutions)]
        c = make_case(f"FeTS2022_{k:05d}", inst, shape, seed=seed + k, with_enhancing=(k % 6 != 5))
        write_case(c, root, layout=layout, with_seg=with_seg)
        cases.append(c)
    lines = ["Partition_ID,Subject_ID"] + [f"{c.institution},{c.case_id}" for c in cases]
    (root / "partitioning_synthetic.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (root / "README_SYNTHETIC.txt").write_text(
        "SYNTHETIC EXAMPLE DATA generated by btqc.data.fixtures. Not patient data, not model output.\n",
        encoding="utf-8",
    )
    return cases


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--n-cases", type=int, default=12)
    ap.add_argument("--shape", type=int, nargs=3, default=(32, 32, 24))
    ap.add_argument("--layout", choices=["flat", "wrapped"], default="flat")
    ap.add_argument("--no-seg", action="store_true")
    a = ap.parse_args(argv)
    make_dataset(a.out, a.n_cases, shape=tuple(a.shape), layout=a.layout, with_seg=not a.no_seg)
    print(f"wrote {a.n_cases} synthetic cases to {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
