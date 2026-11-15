"""Phase 1 conversion: canonical RAS NIfTI, viewer bundles and PNG montages.

The raw root is read-only. Everything is written below ``processed_root``::

    canonical/<case>/<case>_<seq>.nii.gz    RAS reoriented, original dtype, clean header
    canonical/<case>/meta.json              original affine, orientation, source paths, checksums
    viewer/<case>/<seq>.u8.gz               gzip uint8, RAS, x-fastest (Fortran) order
    viewer/<case>/<seq>.json                dims, spacing, affine, window limits, mapping
    montage/<case>.png                      QA montage (4 sequences x 3 planes)

Conversion is resumable: a case whose ``meta.json`` exists is skipped unless
``force`` is set.
"""

from __future__ import annotations

import gzip
import json
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from btqc.data.discover import SEQUENCES, CaseFiles, Discovery
from btqc.data.labels import detect_convention
from btqc.data.nifti_io import load_array, load_nifti, save_like, sha256_file
from btqc.data.orient import to_canonical

VIEWER_FORMAT = "btqc-viewer-u8-v1"


@dataclass
class ConvertOptions:
    out_root: Path
    raw_root: Path
    window_percentiles: tuple[float, float] = (1.0, 99.0)
    montage: bool = True
    force: bool = False
    slices2d: bool = False


def window_limits(data: np.ndarray, pct: tuple[float, float] = (1.0, 99.0)) -> tuple[float, float]:
    nz = data[data != 0]
    if nz.size == 0:
        return 0.0, 1.0
    lo, hi = np.percentile(nz, pct)
    if hi <= lo:
        hi = lo + 1.0
    return float(lo), float(hi)


def to_uint8(data: np.ndarray, lo: float, hi: float) -> np.ndarray:
    """Map [lo, hi] to 1..255 for nonzero voxels; exact-zero background stays 0,
    so the viewer can tell background from dark tissue."""
    out = np.zeros(data.shape, dtype=np.uint8)
    nz = data != 0
    scaled = np.clip((data[nz].astype(np.float32) - lo) / (hi - lo), 0.0, 1.0)
    out[nz] = (1 + np.round(scaled * 254)).astype(np.uint8)
    return out


def write_bundle(arr_u8: np.ndarray, meta: dict[str, Any], out_dir: Path, name: str) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    raw = np.asarray(arr_u8, dtype=np.uint8).ravel(order="F").tobytes()
    with gzip.open(out_dir / f"{name}.u8.gz", "wb", compresslevel=6) as f:
        f.write(raw)
    (out_dir / f"{name}.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")


def read_bundle(out_dir: Path, name: str) -> tuple[np.ndarray, dict[str, Any]]:
    meta = json.loads((out_dir / f"{name}.json").read_text(encoding="utf-8"))
    with gzip.open(out_dir / f"{name}.u8.gz", "rb") as f:
        raw = f.read()
    arr = np.frombuffer(raw, dtype=np.uint8).reshape(meta["dims"], order="F")
    return arr, meta


def bundle_meta(case_id: str, kind: str, can_aff: np.ndarray, orient: dict[str, Any], dims: tuple[int, ...],
                window: tuple[float, float] | None, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    spacing = [float(np.linalg.norm(can_aff[:3, j])) for j in range(3)]
    m: dict[str, Any] = {
        "format": VIEWER_FORMAT,
        "case_id": case_id,
        "kind": kind,
        "dims": [int(d) for d in dims],
        "spacing": [round(s, 6) for s in spacing],
        "affine": [[round(float(x), 6) for x in r] for r in can_aff],
        "orientation": "RAS",
        "order": "x-fastest",
        "original_orientation": orient,
    }
    if window is not None:
        m["window"] = {"lo": window[0], "hi": window[1], "percentiles": [1, 99], "mapping": "nonzero -> 1..255"}
    if extra:
        m.update(extra)
    return m


def tumor_or_brain_center(vol: np.ndarray, seg: np.ndarray | None) -> tuple[int, int, int]:
    mask = seg > 0 if seg is not None and (seg > 0).any() else vol != 0
    if not mask.any():
        return tuple(int(s // 2) for s in vol.shape)  # type: ignore[return-value]
    idx = np.argwhere(mask)
    lo, hi = idx.min(0), idx.max(0)
    return tuple(int(v) for v in (lo + hi) // 2)  # type: ignore[return-value]


def radiological(slice2d: np.ndarray) -> np.ndarray:
    """Canonical RAS slice (first axis to the right/anterior, second to anterior/superior)
    to screen image in radiological convention: patient right on screen left,
    anterior/superior at the top. Same rule for axial s[x,y], coronal s[x,z], sagittal s[y,z]."""
    return slice2d[::-1, ::-1].T


def write_montage(case_id: str, vols: dict[str, np.ndarray], seg: np.ndarray | None, spacing: list[float],
                  path: Path, center: tuple[int, int, int]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import ListedColormap

    seg_cmap = ListedColormap([(0, 0, 0, 0), (0.9, 0.1, 0.1, 0.55), (0.1, 0.8, 0.2, 0.45), (1.0, 0.9, 0.0, 0.6)])
    x, y, z = center
    sx, sy, sz = spacing
    planes = [
        ("axial z=%d" % z, lambda v: v[:, :, z], (sx, sy), ("R", "L", "A", "P")),
        ("coronal y=%d" % y, lambda v: v[:, y, :], (sx, sz), ("R", "L", "S", "I")),
        ("sagittal x=%d" % x, lambda v: v[x, :, :], (sy, sz), ("A", "P", "S", "I")),
    ]
    seqs = [s for s in SEQUENCES if s in vols]
    fig, axes = plt.subplots(len(seqs), 3, figsize=(9, 3 * len(seqs)), squeeze=False)
    for r, s in enumerate(seqs):
        lo, hi = window_limits(vols[s])
        for c, (title, get, (dc, dr), (left, right, top, bottom)) in enumerate(planes):
            ax = axes[r][c]
            img = radiological(get(vols[s]))
            h, w = img.shape
            ax.imshow(img, cmap="gray", vmin=lo, vmax=hi, aspect=dr / dc, interpolation="nearest")
            if seg is not None:
                lab = radiological(get(seg)).astype(np.int64)
                lut = np.array([0, 1, 2, 3, 3])  # BraTS 1 red, 2 green, 3 or 4 (enhancing) yellow
                lab = lut[np.clip(lab, 0, 4)]
                ax.imshow(lab, cmap=seg_cmap, vmin=0, vmax=3, aspect=dr / dc, interpolation="nearest")
            kw = {"color": "orange", "fontsize": 8, "ha": "center", "va": "center"}
            ax.text(w * 0.04, h / 2, left, **kw)
            ax.text(w * 0.96, h / 2, right, **kw)
            ax.text(w / 2, h * 0.05, top, **kw)
            ax.text(w / 2, h * 0.95, bottom, **kw)
            ax.set_xticks([])
            ax.set_yticks([])
            if r == 0:
                ax.set_title(title, fontsize=9)
            if c == 0:
                ax.set_ylabel(s, fontsize=9)
    fig.suptitle(f"{case_id} (RAS, radiological display){' + reference mask' if seg is not None else ''}",
                 fontsize=10)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=80)
    plt.close(fig)


def convert_case(case: CaseFiles, opt: ConvertOptions) -> dict[str, Any]:
    cid = case.case_id
    can_dir = opt.out_root / "canonical" / cid
    meta_path = can_dir / "meta.json"
    if meta_path.exists() and not opt.force:
        return {"case_id": cid, "status": "skipped"}
    if not case.has_all_sequences:
        return {"case_id": cid, "status": "incomplete", "missing": case.missing}
    vols: dict[str, np.ndarray] = {}
    files: dict[str, Any] = {}
    orient_ref = None
    can_aff = None
    orig_aff = None
    for kind in (*SEQUENCES, "seg"):
        entry = case.files.get(kind)
        if entry is None:
            continue
        raw_dtype = _raw_dtype(entry.path)
        data, aff = load_array(entry.path)
        can, c_aff, orient = to_canonical(data, aff)
        if orient_ref is None:
            orient_ref, can_aff, orig_aff = orient, c_aff, aff
        elif orient != orient_ref or not np.allclose(c_aff, can_aff, atol=1e-4):
            return {"case_id": cid, "status": "grid_mismatch", "sequence": kind}
        out_dtype = np.uint8 if kind == "seg" else raw_dtype
        save_like(can.astype(out_dtype), c_aff, can_dir / f"{cid}_{kind}.nii.gz")
        vols[kind] = can
        files[kind] = {
            "source": str(entry.path.relative_to(opt.raw_root)).replace("\\", "/"),
            "source_sha256": sha256_file(entry.path),
            "dtype": str(np.dtype(out_dtype)),
        }
    assert orient_ref is not None and can_aff is not None and orig_aff is not None
    seg = vols.pop("seg", None)
    convention = None
    if seg is not None:
        convention = detect_convention(np.unique(seg).astype(int).tolist())
        seg = seg.astype(np.uint8)
    vdir = opt.out_root / "viewer" / cid
    windows = {}
    for s in SEQUENCES:
        lo, hi = window_limits(vols[s], opt.window_percentiles)
        windows[s] = [lo, hi]
        write_bundle(to_uint8(vols[s], lo, hi), bundle_meta(cid, s, can_aff, orient_ref.to_dict(), vols[s].shape,
                                                             (lo, hi)), vdir, s)
    if seg is not None:
        write_bundle(seg, bundle_meta(cid, "seg", can_aff, orient_ref.to_dict(), seg.shape, None,
                                      {"labels": convention, "source": "reference"}), vdir, "seg")
    spacing = [float(np.linalg.norm(can_aff[:3, j])) for j in range(3)]
    if opt.montage:
        center = tumor_or_brain_center(vols["flair"], seg)
        write_montage(cid, vols, seg, spacing, opt.out_root / "montage" / f"{cid}.png", center)
    if opt.slices2d:
        _write_slices(cid, vols, seg, opt.out_root / "slices2d" / cid)
    meta = {
        "case_id": cid,
        "original_affine": orig_aff.tolist(),
        "canonical_affine": can_aff.tolist(),
        "orientation": orient_ref.to_dict(),
        "canonical_shape": list(orient_ref.canonical_shape),
        "spacing": spacing,
        "files": files,
        "label_convention": convention,
        "windows": windows,
    }
    meta_path.write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return {"case_id": cid, "status": "converted", "has_seg": seg is not None}


def _raw_dtype(path: Path) -> np.dtype:

    hdr = load_nifti(path).header
    slope, inter = hdr.get_slope_inter()
    dt = hdr.get_data_dtype()
    if (slope not in (None, 1.0)) or (inter not in (None, 0.0)):
        return np.dtype(np.float32)
    return np.dtype(dt)


def _write_slices(cid: str, vols: dict[str, np.ndarray], seg: np.ndarray | None, out: Path) -> None:
    """Axial slices with tumor or brain for optional 2D experiments. Stored per case so any
    split is by case, never by slice."""
    out.mkdir(parents=True, exist_ok=True)
    stack = np.stack([vols[s] for s in SEQUENCES], axis=0).astype(np.float32)
    keep = np.where((stack[3] != 0).any(axis=(0, 1)))[0]
    np.savez_compressed(out / "axial.npz", images=stack[..., keep], seg=None if seg is None else seg[..., keep],
                        z=keep)


def _convert_one(args: tuple[CaseFiles, ConvertOptions]) -> dict[str, Any]:
    case, opt = args
    try:
        return convert_case(case, opt)
    except Exception as e:
        return {"case_id": case.case_id, "status": "error", "error": f"{type(e).__name__}: {e}"}


def convert_all(disc: Discovery, opt: ConvertOptions, workers: int = 2, max_cases: int | None = None,
                progress: Any = None) -> list[dict[str, Any]]:
    cases = list(disc.cases.values())[:max_cases]
    results = []
    if workers <= 1:
        it = map(_convert_one, [(c, opt) for c in cases])
        for i, r in enumerate(it):
            results.append(r)
            if progress:
                progress(i + 1, len(cases), r)
        return results
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for i, r in enumerate(ex.map(_convert_one, [(c, opt) for c in cases])):
            results.append(r)
            if progress:
                progress(i + 1, len(cases), r)
    return results
