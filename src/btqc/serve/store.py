"""Read-only access to processed cases, prediction records and evaluation summaries."""

from __future__ import annotations

import gzip
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np

from btqc.data.convert import bundle_meta
from btqc.infer.record import PredictionRecord, load_record

SAFE_ID = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")
EXAMPLE_NOTE = ("EXAMPLE: this outline and heat map come from simple brightness rules, not from a trained model. "
                "No model result is shown.")


class NotFound(KeyError):
    pass


def safe_id(s: str) -> str:
    if not SAFE_ID.match(s):
        raise NotFound(s)
    return s


class Store:
    def __init__(self, processed_root: Path, predictions_root: Path, results_dir: Path, sitegroups: Path | None,
                 methods: list[str]):
        self.processed = processed_root
        self.viewer = processed_root / "viewer"
        self.canonical = processed_root / "canonical"
        self.preds = predictions_root
        self.results = results_dir
        self.methods = methods
        self.groups: dict[str, str] = {}
        if sitegroups and sitegroups.exists():
            self.groups = json.loads(sitegroups.read_text(encoding="utf-8")).get("case_group", {})
        self.cache_dir = processed_root / "pred_bundles"

    # ---------------------------------------------------------------- cases
    def case_ids(self) -> list[str]:
        if not self.viewer.exists():
            return []
        return sorted(p.name for p in self.viewer.iterdir() if (p / "flair.json").exists() and SAFE_ID.match(p.name))

    def sequences(self, cid: str) -> list[str]:
        d = self.viewer / safe_id(cid)
        return [s for s in ("t1", "t1ce", "t2", "flair") if (d / f"{s}.json").exists()]

    def has_reference(self, cid: str) -> bool:
        return (self.viewer / safe_id(cid) / "seg.json").exists()

    def bundle(self, cid: str, kind: str) -> tuple[Path, dict[str, Any]]:
        d = self.viewer / safe_id(cid)
        meta_p, data_p = d / f"{kind}.json", d / f"{kind}.u8.gz"
        if kind not in ("t1", "t1ce", "t2", "flair", "seg") or not meta_p.exists():
            raise NotFound(f"{cid}/{kind}")
        return data_p, json.loads(meta_p.read_text(encoding="utf-8"))

    # ---------------------------------------------------------------- predictions
    def find_prediction(self, cid: str) -> tuple[str, str, Path] | None:
        safe_id(cid)
        for m in self.methods:
            mdir = self.preds / m
            if not mdir.exists():
                continue
            for fdir in sorted(p for p in mdir.iterdir() if p.is_dir()):
                if (fdir / f"{cid}.npz").exists():
                    return m, fdir.name, fdir
        return None

    def prediction(self, cid: str) -> tuple[str, str, PredictionRecord] | None:
        hit = self.find_prediction(cid)
        if hit is None:
            return None
        m, f, d = hit
        return m, f, _load_cached(str(d), cid, (d / f"{cid}.npz").stat().st_mtime)

    def prediction_meta(self, cid: str) -> dict[str, Any] | None:
        hit = self.find_prediction(cid)
        if hit is None:
            return None
        m, f, d = hit
        meta = json.loads((d / f"{cid}.json").read_text(encoding="utf-8"))
        meta.setdefault("method", m)
        meta.setdefault("fold", f)
        return meta

    def prediction_bundle(self, cid: str, kind: str) -> tuple[bytes, dict[str, Any]]:
        """Gzip uint8 labels or uncertainty in canonical RAS, cached on disk."""
        if kind not in ("labels", "uncertainty"):
            raise NotFound(kind)
        got = self.prediction(cid)
        if got is None:
            raise NotFound(cid)
        m, f, rec = got
        out = self.cache_dir / cid
        gz_p, meta_p = out / f"{m}_{f}_{kind}.u8.gz", out / f"{m}_{f}_{kind}.json"
        src = self.preds / m / f / f"{cid}.npz"
        if not gz_p.exists() or gz_p.stat().st_mtime < src.stat().st_mtime:
            arr = rec.seg if kind == "labels" else rec.unc
            _, smeta = self.bundle(cid, "flair")
            meta = bundle_meta(cid, kind, np.asarray(smeta["affine"]), smeta["original_orientation"], arr.shape, None,
                               {"source": rec.source, "method": m, "fold": f,
                                "labels": "brats_124" if kind == "labels" else None,
                                "scale": "uncertainty 0..1 -> 0..255" if kind == "uncertainty" else None})
            out.mkdir(parents=True, exist_ok=True)
            with gzip.open(gz_p, "wb", compresslevel=6) as fh:
                fh.write(np.asarray(arr, np.uint8).ravel(order="F").tobytes())
            meta_p.write_text(json.dumps(meta), encoding="utf-8")
        return gz_p.read_bytes(), json.loads(meta_p.read_text(encoding="utf-8"))

    # ---------------------------------------------------------------- evaluation
    def eval_summary(self) -> dict[str, Any]:
        p = self.results / "eval_summary.json"
        if not p.exists():
            out: dict[str, Any] = {"status": "not run", "message": "No site-held-out evaluation has been run on real "
                                   "data. Train models with labeled FeTS 2022 data and run `make eval`."}
            synth = self.results / "eval_summary_synthetic.json"
            if synth.exists():
                out["synthetic_demo"] = json.loads(synth.read_text(encoding="utf-8"))
            return out
        return json.loads(p.read_text(encoding="utf-8"))

    def json_result(self, name: str) -> dict[str, Any] | None:
        p = self.results / name
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


@lru_cache(maxsize=8)
def _load_cached(d: str, cid: str, mtime: float) -> PredictionRecord:
    return load_record(Path(d), cid)
