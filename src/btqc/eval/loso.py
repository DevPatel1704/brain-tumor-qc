"""Site-held-out evaluation harness (contribution C1).

For every method and fold (= held-out site group) the harness scores the
prediction records of the fold's ``insite_test`` and ``heldout`` cases against
the reference masks, attaches case-level uncertainty scores, accumulates
calibration counts, and aggregates per group and region:

    gap = mean(in-site) - mean(held-out)        (Dice; HD95 reported the same way)

Leakage guard: a fold's predictions must come from models trained on that
fold only. Each record's ``meta['fold']`` is checked against the fold name.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from btqc.data.labels import REGIONS, regions
from btqc.data.nifti_io import load_nifti
from btqc.eval.metrics import EmptyPolicy, region_metrics
from btqc.eval.stats import bootstrap_ci, bootstrap_diff_ci
from btqc.infer.record import REGION_ORDER, PredictionRecord, load_record
from btqc.uncertainty.calibration import ReliabilityAccumulator, calibration_mask
from btqc.uncertainty.case_score import all_scores


class LeakageError(RuntimeError):
    pass


@dataclass
class CalibrationSet:
    n_bins: int = 15
    acc: dict[tuple[str, str, str], ReliabilityAccumulator] = field(default_factory=dict)

    def get(self, split: str, region: str, mode: str) -> ReliabilityAccumulator:
        key = (split, region, mode)
        if key not in self.acc:
            self.acc[key] = ReliabilityAccumulator(self.n_bins)
        return self.acc[key]


def load_reference(canonical_dir: Path, case_id: str) -> tuple[np.ndarray, tuple[float, ...], np.ndarray | None]:
    img = load_nifti(canonical_dir / case_id / f"{case_id}_seg.nii.gz")
    seg = np.asarray(img.dataobj).astype(np.uint8)
    spacing = tuple(float(z) for z in img.header.get_zooms()[:3])
    flair = canonical_dir / case_id / f"{case_id}_flair.nii.gz"
    brain = np.asarray(load_nifti(flair).dataobj) != 0 if flair.exists() else None
    return seg, spacing, brain


def evaluate_case(ref_seg: np.ndarray, rec: PredictionRecord, spacing: tuple[float, ...], convention: str,
                  band_width: int = 3, policy: EmptyPolicy = EmptyPolicy(), calib: CalibrationSet | None = None,
                  split: str = "", brain: np.ndarray | None = None, calib_band: int = 5) -> dict[str, Any]:
    ref = regions(ref_seg, convention)
    pred = regions(rec.seg, "brats_124")
    row: dict[str, Any] = region_metrics(ref, pred, spacing, policy)
    u = rec.unc_float()
    mi = rec.mi.astype(np.float32) / 255.0 if rec.mi is not None else None
    row.update({f"score_{k}": v for k, v in all_scores(u, pred["WT"], band_width, mi).items()})
    row["ref_has_et"] = bool(ref["ET"].any())
    if calib is not None:
        for mode in ("band", "volume"):
            m = calibration_mask(pred["WT"], ref["WT"], brain, mode, calib_band)
            for i, r in enumerate(REGION_ORDER):
                calib.get(split, r, mode).add(rec.prob[i], ref[r], m)
    return row


def evaluate_fold(method: str, fold: str, fold_def: Mapping[str, list[str]], pred_dir: Path, canonical_dir: Path,
                  case_institution: Mapping[str, Any], convention: str, splits: Iterable[str] = ("insite_test",
                  "heldout", "val"), band_width: int = 3, policy: EmptyPolicy = EmptyPolicy(),
                  calib: CalibrationSet | None = None, max_cases: int | None = None) -> pd.DataFrame:
    rows = []
    for split in splits:
        for cid in list(fold_def.get(split, []))[:max_cases]:
            if not (pred_dir / f"{cid}.npz").exists():
                rows.append({"method": method, "fold": fold, "split": split, "case_id": cid, "status": "missing"})
                continue
            rec = load_record(pred_dir, cid)
            if str(rec.meta.get("fold")) != fold:
                raise LeakageError(f"{method}/{fold}/{cid}: record was produced for fold {rec.meta.get('fold')!r}")
            ref, spacing, brain = load_reference(canonical_dir, cid)
            r = evaluate_case(ref, rec, spacing, convention, band_width, policy, calib, split, brain)
            r.update(method=method, fold=fold, split=split, case_id=cid, status="ok",
                     institution=case_institution.get(cid), source=rec.source)
            rows.append(r)
    df = pd.DataFrame(rows)
    front = ["method", "fold", "split", "case_id", "institution", "status"]
    return df[[c for c in front if c in df] + [c for c in df.columns if c not in front]]


def gap_table(cases: pd.DataFrame, n_boot: int = 2000, seed: int = 0, small_n: int = 15) -> pd.DataFrame:
    """Per method, fold and region: in-site and held-out means with CIs and the gap."""
    ok = cases[cases.get("status", "ok") == "ok"]
    rows = []
    for (method, fold), g in ok.groupby(["method", "fold"], sort=True):
        ins, held = g[g["split"] == "insite_test"], g[g["split"] == "heldout"]
        for r in REGIONS:
            for metric in ("dice", "hd95"):
                col = f"{metric}_{r}"
                if col not in g:
                    continue
                a, b = ins[col].to_numpy(float), held[col].to_numpy(float)
                ci_a = bootstrap_ci(a, n_boot=n_boot, seed=seed)
                ci_b = bootstrap_ci(b, n_boot=n_boot, seed=seed)
                d = bootstrap_diff_ci(a, b, n_boot=n_boot, seed=seed)
                rows.append({
                    "method": method, "fold": fold, "region": r, "metric": metric,
                    "insite_mean": ci_a["mean"], "insite_lo": ci_a["lo"], "insite_hi": ci_a["hi"],
                    "n_insite": ci_a["n"],
                    "heldout_mean": ci_b["mean"], "heldout_lo": ci_b["lo"], "heldout_hi": ci_b["hi"],
                    "n_heldout": ci_b["n"], "gap": d["diff"], "gap_lo": d["lo"], "gap_hi": d["hi"],
                    "small_n": bool(ci_b["n"] < small_n),
                    "penalized_frac_heldout": float(held[f"penalized_{r}"].mean()) if len(held) else float("nan"),
                })
    return pd.DataFrame(rows)


def calibration_table(calib: CalibrationSet, method: str, fold: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary, curves = [], []
    for (split, region, mode), acc in sorted(calib.acc.items()):
        summary.append({"method": method, "fold": fold, "split": split, "region": region, "mode": mode,
                        "ece": acc.ece(), "n_voxels": int(acc.count.sum())})
        for pt in acc.curve():
            curves.append({"method": method, "fold": fold, "split": split, "region": region, "mode": mode, **pt})
    return pd.DataFrame(summary), pd.DataFrame(curves)
