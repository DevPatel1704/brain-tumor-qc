"""Build the per-file inventory and per-case manifest from a raw data root.

The raw root is only read. Results go to ``data/manifest.csv`` and
``data/file_inventory.csv``.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from btqc.data.discover import SEQUENCES, Discovery, FileEntry
from btqc.data.nifti_io import (
    border_zero_fraction,
    intensity_stats,
    load_array,
    read_header,
    sha256_file,
)

AFFINE_TOL = 1e-4


def inspect_file(path: str) -> dict[str, Any]:
    """Header, checksum and intensity statistics of one NIfTI file."""
    hdr = read_header(path)
    data, _ = load_array(path)
    row: dict[str, Any] = hdr.to_dict()
    row["sha256"] = sha256_file(path)
    row["size_bytes"] = Path(path).stat().st_size
    if data.ndim == 3:
        row.update(intensity_stats(data))
        row["border_zero_frac"] = border_zero_fraction(data)
        if np.all(np.equal(np.mod(data, 1), 0)):
            vals, counts = np.unique(data.astype(np.int64), return_counts=True)
            row["n_unique"] = int(vals.size)
            if vals.size <= 16:
                row["unique_values"] = json.dumps({int(v): int(c) for v, c in zip(vals, counts, strict=True)})
        else:
            row["n_unique"] = -1
    return row


@dataclass
class ManifestResult:
    files: pd.DataFrame
    cases: pd.DataFrame


def _entries(disc: Discovery) -> list[FileEntry]:
    return [e for c in disc.cases.values() for e in c.files.values()]


def build_inventory(
    disc: Discovery,
    workers: int = 4,
    max_cases: int | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> pd.DataFrame:
    entries = _entries(disc)
    if max_cases is not None:
        keep = set(list(disc.cases)[:max_cases])
        entries = [e for e in entries if e.case_id in keep]
    rows: list[dict[str, Any]] = []
    paths = [str(e.path) for e in entries]
    if workers <= 1:
        results: Any = map(inspect_file, paths)
        ex = None
    else:
        ex = ProcessPoolExecutor(max_workers=workers)
        results = ex.map(inspect_file, paths, chunksize=2)
    try:
        for i, (e, info) in enumerate(zip(entries, results, strict=True)):
            info.update(
                case_id=e.case_id,
                sequence=e.sequence,
                declared_name=e.declared_name,
                inner_name=e.inner_name,
                rel_path=str(e.path.relative_to(disc.root)).replace("\\", "/"),
            )
            rows.append(info)
            if progress:
                progress(i + 1, len(entries))
    finally:
        if ex is not None:
            ex.shutdown()
    df = pd.DataFrame(rows)
    front = ["case_id", "sequence", "rel_path", "declared_name", "inner_name"]
    return df[front + [c for c in df.columns if c not in front]]


def _same_affine(a: list[list[float]], b: list[list[float]]) -> bool:
    return bool(np.allclose(np.asarray(a), np.asarray(b), atol=AFFINE_TOL))


def build_case_table(files: pd.DataFrame, institutions: pd.DataFrame | None = None) -> pd.DataFrame:
    """One row per case with geometry checks, per-sequence statistics and checksums."""
    rows = []
    for case_id, g in files.groupby("case_id", sort=True):
        by_seq = {r["sequence"]: r for _, r in g.iterrows()}
        present = [s for s in SEQUENCES if s in by_seq]
        problems: list[str] = []
        missing = [s for s in SEQUENCES if s not in by_seq]
        if missing:
            problems.append("missing:" + "+".join(missing))
        ref = by_seq[present[0]] if present else None
        for s, r in by_seq.items():
            if ref is None or s == present[0]:
                continue
            if tuple(r["shape"]) != tuple(ref["shape"]):
                problems.append(f"shape_mismatch:{s}")
            if not _same_affine(r["affine"], ref["affine"]):
                problems.append(f"affine_mismatch:{s}")
        inner_ids = {
            str(r["inner_name"]).split("_")[0] for r in by_seq.values() if isinstance(r["inner_name"], str)
        }
        if len(inner_ids) > 1:
            problems.append("inner_name_ids_differ")
        row: dict[str, Any] = {
            "case_id": case_id,
            "sequences_present": "+".join(present),
            "n_sequences": len(present),
            "has_seg": "seg" in by_seq,
            "shape": "x".join(map(str, ref["shape"])) if ref is not None else "",
            "spacing": "x".join(f"{z:g}" for z in ref["spacing"]) if ref is not None else "",
            "orientation": ref["axcodes"] if ref is not None else "",
            "dtype": ref["dtype"] if ref is not None else "",
            "institution": None,
            "grid_ok": not any(p.startswith(("shape", "affine")) for p in problems),
            "problems": ";".join(problems),
        }
        for s in SEQUENCES:
            r = by_seq.get(s)
            for k in ("p1_nz", "p50_nz", "p99_nz", "nonzero_frac"):
                row[f"{s}_{k}"] = None if r is None else r.get(k)
            row[f"{s}_sha256"] = None if r is None else r["sha256"]
        if "seg" in by_seq:
            row["seg_sha256"] = by_seq["seg"]["sha256"]
            row["seg_labels"] = by_seq["seg"].get("unique_values")
        rows.append(row)
    cases = pd.DataFrame(rows)
    if institutions is not None and len(institutions):
        m = dict(zip(institutions["case_id"], institutions["institution"], strict=True))
        cases["institution"] = cases["case_id"].map(m)
    return cases


def find_institution_tables(root: Path, extra_dirs: list[Path] | None = None) -> list[Path]:
    """Look for candidate subject-to-institution CSV files. Read-only."""
    hits: list[Path] = []
    for base in [root, *(extra_dirs or [])]:
        if not base.exists():
            continue
        for p in base.rglob("*.csv"):
            name = p.name.lower()
            if any(k in name for k in ("partition", "institution", "site", "mapping")):
                hits.append(p)
    return hits


def load_institution_table(path: Path) -> pd.DataFrame:
    """Read a FeTS-style partitioning CSV: columns ``Partition_ID`` and
    ``Subject_ID`` (names compared case-insensitively)."""
    df = pd.read_csv(path)
    cols = {c.lower().replace(" ", "_"): c for c in df.columns}
    subj = next((cols[k] for k in ("subject_id", "case_id", "subject") if k in cols), None)
    part = next((cols[k] for k in ("partition_id", "institution", "site", "partition") if k in cols), None)
    if subj is None or part is None:
        raise ValueError(f"{path}: need a subject and a partition/institution column, got {list(df.columns)}")
    return pd.DataFrame({"case_id": df[subj].astype(str), "institution": df[part].astype(int)})
