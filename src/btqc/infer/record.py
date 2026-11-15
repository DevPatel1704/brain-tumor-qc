"""Prediction record: the one on-disk format every predictor writes and every
consumer (harness, API, dashboard export) reads.

    <pred_root>/<method>/<fold>/<case_id>.npz
        seg      uint8   (X, Y, Z)     BraTS 1/2/4 labels, canonical RAS grid
        prob     float16 (3, X, Y, Z)  ensemble-mean sigmoid probability, regions WT, TC, ET
        unc      uint8   (X, Y, Z)     voxel uncertainty in [0, 1] scaled to 0..255
        mi       uint8   (X, Y, Z)     member disagreement (mutual information), optional
    <pred_root>/<method>/<fold>/<case_id>.json
        case scores, members used, source ("model" | "example"), timings, run id

``source`` is ``"example"`` for rule-based or synthetic predictions. The API and
dashboard label those as examples and never present them as model output.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from btqc.data.labels import labels_from_regions

REGION_ORDER = ("WT", "TC", "ET")


@dataclass
class PredictionRecord:
    case_id: str
    seg: np.ndarray
    prob: np.ndarray
    unc: np.ndarray
    mi: np.ndarray | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def source(self) -> str:
        return str(self.meta.get("source", "unknown"))

    def regions(self) -> dict[str, np.ndarray]:
        return {r: self.prob[i] > 0.5 for i, r in enumerate(REGION_ORDER)}

    def unc_float(self) -> np.ndarray:
        return self.unc.astype(np.float32) / 255.0


def seg_from_prob(prob: np.ndarray, threshold: float = 0.5) -> np.ndarray:
    """Region probabilities (WT, TC, ET) to BraTS labels; nested like nnU-Net's regions_class_order."""
    wt, tc, et = (prob[i] > threshold for i in range(3))
    return labels_from_regions(wt, tc & wt, et & tc & wt, "brats_124")


def save_record(rec: PredictionRecord, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    arrays: dict[str, np.ndarray] = {
        "seg": rec.seg.astype(np.uint8),
        "prob": rec.prob.astype(np.float16),
        "unc": rec.unc.astype(np.uint8),
    }
    if rec.mi is not None:
        arrays["mi"] = rec.mi.astype(np.uint8)
    p = out_dir / f"{rec.case_id}.npz"
    np.savez_compressed(p, **arrays)  # type: ignore[arg-type]
    (out_dir / f"{rec.case_id}.json").write_text(json.dumps({"case_id": rec.case_id, **rec.meta}, indent=1,
                                                            default=float), encoding="utf-8")
    return p


def load_record(out_dir: Path, case_id: str) -> PredictionRecord:
    with np.load(out_dir / f"{case_id}.npz") as z:
        seg, prob, unc = z["seg"], z["prob"].astype(np.float32), z["unc"]
        mi = z["mi"] if "mi" in z.files else None
    meta = json.loads((out_dir / f"{case_id}.json").read_text(encoding="utf-8"))
    return PredictionRecord(case_id, seg, prob, unc, mi, meta)


def list_records(out_dir: Path) -> list[str]:
    return sorted(p.stem for p in out_dir.glob("*.npz"))
