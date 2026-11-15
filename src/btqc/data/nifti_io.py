"""NIfTI header inspection and safe loading helpers (nibabel based)."""

from __future__ import annotations

import hashlib
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, cast

import nibabel as nib
import numpy as np

# Free-text header fields that could carry identifying information. They are
# never copied to outputs; we only record whether they were non-empty.
FREE_TEXT_FIELDS: tuple[str, ...] = ("descrip", "aux_file", "db_name", "intent_name")


@dataclass
class HeaderInfo:
    shape: tuple[int, ...]
    ndim: int
    dtype: str
    spacing: tuple[float, ...]
    sform_code: int
    qform_code: int
    affine: list[list[float]]
    axcodes: str
    scl_slope: float | None
    scl_inter: float | None
    free_text_nonempty: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_nifti(path: str | os.PathLike[str]) -> nib.Nifti1Image:
    """``nib.load`` typed as a NIfTI-1 image (all inputs here are NIfTI-1)."""
    return cast(nib.Nifti1Image, nib.load(str(path)))


def _float_or_none(v: Any) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return None if np.isnan(f) else f


def best_affine(img: nib.Nifti1Image) -> np.ndarray:
    """Return the sform if it is set, otherwise the qform, otherwise the
    nibabel fallback affine (spacing only)."""
    hdr = cast(Any, img.header)
    sform, scode = hdr.get_sform(coded=True)
    if sform is not None and int(scode) > 0:
        return np.asarray(sform, dtype=float)
    qform, qcode = hdr.get_qform(coded=True)
    if qform is not None and int(qcode) > 0:
        return np.asarray(qform, dtype=float)
    return np.asarray(hdr.get_best_affine(), dtype=float)


def read_header(path: str | os.PathLike[str]) -> HeaderInfo:
    img = load_nifti(path)
    hdr = cast(Any, img.header)
    aff = best_affine(img)
    free = []
    for key in FREE_TEXT_FIELDS:
        try:
            val = hdr[key]
        except (KeyError, ValueError):
            continue
        raw = val.tobytes() if hasattr(val, "tobytes") else bytes(str(val), "utf8")
        if raw.strip(b"\x00 "):
            free.append(key)
    _, scode = hdr.get_sform(coded=True)
    _, qcode = hdr.get_qform(coded=True)
    return HeaderInfo(
        shape=tuple(int(s) for s in img.shape),
        ndim=len(img.shape),
        dtype=str(hdr.get_data_dtype()),
        spacing=tuple(round(float(z), 6) for z in hdr.get_zooms()),
        sform_code=int(scode),
        qform_code=int(qcode),
        affine=[[round(float(x), 6) for x in row] for row in aff],
        axcodes="".join(nib.aff2axcodes(aff)),
        scl_slope=_float_or_none(hdr["scl_slope"]),
        scl_inter=_float_or_none(hdr["scl_inter"]),
        free_text_nonempty=free,
    )


def load_array(path: str | os.PathLike[str]) -> tuple[np.ndarray, np.ndarray]:
    """Load voxel data as float32 (scl_slope/scl_inter applied) and the best affine."""
    img = load_nifti(path)
    return img.get_fdata(dtype=np.float32), best_affine(img)


def sha256_file(path: str | os.PathLike[str], chunk: int = 1 << 22) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def intensity_stats(data: np.ndarray) -> dict[str, float]:
    """Percentiles and background statistics of one volume."""
    flat = data.reshape(-1)
    nz = flat[flat != 0]
    n = flat.size
    out = {
        "min": float(flat.min()),
        "max": float(flat.max()),
        "nonzero_frac": float(nz.size / n),
        "neg_frac": float((flat < 0).sum() / n),
    }
    if nz.size:
        p1, p50, p99 = np.percentile(nz, [1, 50, 99])
        out.update(p1_nz=float(p1), p50_nz=float(p50), p99_nz=float(p99))
    else:
        out.update(p1_nz=float("nan"), p50_nz=float("nan"), p99_nz=float("nan"))
    p1a, p50a, p99a = np.percentile(flat, [1, 50, 99])
    out.update(p1=float(p1a), p50=float(p50a), p99=float(p99a))
    return out


def border_zero_fraction(data: np.ndarray, width: int = 2) -> float:
    """Fraction of exactly-zero voxels in the outer shell of the volume.
    A skull-stripped, padded brain volume has a value close to 1."""
    if data.ndim != 3 or min(data.shape) <= 2 * width:
        return float("nan")
    mask = np.ones(data.shape, dtype=bool)
    mask[width:-width, width:-width, width:-width] = False
    shell = data[mask]
    return float((shell == 0).mean())


def save_like(data: np.ndarray, affine: np.ndarray, path: str | os.PathLike[str], dtype: Any | None = None) -> None:
    """Save a volume with a clean header: no free-text fields copied."""
    arr = np.asarray(data, dtype=dtype) if dtype is not None else np.asarray(data)
    img = nib.Nifti1Image(arr, affine)
    img.header.set_sform(affine, code=1)
    img.header.set_qform(affine, code=1)
    img.header.set_xyzt_units("mm", "sec")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    nib.save(img, str(path))
