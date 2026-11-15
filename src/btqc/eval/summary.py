"""Turn per-case harness rows and calibration counts into the evaluation summary
(results/eval_summary.json) consumed by the dashboard and the report tables.

Failure detection uses tau and the review-limit rule from
configs/uncertainty.yaml. The review limit is selected on each fold's in-site
``val`` cases and then applied unchanged to the fold's ``heldout`` cases.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from btqc.eval.loso import CalibrationSet, calibration_table, gap_table
from btqc.uncertainty.failure_detection import (
    bootstrap_auroc,
    failure_labels,
    risk_coverage,
    select_review_limit,
)

SCORES = ("score_boundary_band", "score_wt_mean", "score_band_disagreement")


def add_case_columns(cases: pd.DataFrame, tau: float) -> pd.DataFrame:
    df = cases.copy()
    if "dice_WT" in df:
        df["dice_mean"] = df[["dice_WT", "dice_TC", "dice_ET"]].mean(axis=1)
        df["failed"] = failure_labels(df["dice_WT"].to_numpy(), df["dice_ET"].to_numpy(), tau)
    return df


def failure_rows(df: pd.DataFrame, ucfg: dict[str, Any]) -> list[dict[str, Any]]:
    rule = ucfg["gate"]["review_limit_rule"]
    boot = ucfg["bootstrap"]
    out = []
    for (method, fold), g in df[df.status == "ok"].groupby(["method", "fold"]):
        held, val = g[g.split == "heldout"], g[g.split == "val"]
        if held.empty:
            continue
        for sc in SCORES:
            if sc not in held or held[sc].isna().all():
                continue
            r = bootstrap_auroc(held[sc].to_numpy(float), held["failed"].to_numpy(bool), boot["n_resamples"],
                                boot["seed"], boot["alpha"])
            row: dict[str, Any] = {"method": method, "fold": fold, "score": sc.replace("score_", ""),
                                   "n": len(held), "n_failed": int(held["failed"].sum()), **r}
            if sc == "score_boundary_band":
                vs = val[sc].to_numpy(float) if not val.empty else held[sc].to_numpy(float)
                limit = select_review_limit(vs, rule, val["failed"].to_numpy(bool) if not val.empty else None)
                flagged = ~(held[sc].to_numpy(float) <= limit)
                fails = held["failed"].to_numpy(bool)
                row.update(review_limit=limit, limit_source="val" if not val.empty else "heldout (no val cases)",
                           flagged_frac=float(flagged.mean()),
                           fail_rate_flagged=float(fails[flagged].mean()) if flagged.any() else float("nan"),
                           fail_rate_unflagged=float(fails[~flagged].mean()) if (~flagged).any() else float("nan"),
                           dice_mean_unflagged=float(held["dice_mean"].to_numpy()[~flagged].mean())
                           if (~flagged).any() else float("nan"),
                           dice_mean_all=float(held["dice_mean"].mean()))
            out.append(row)
    return out


def rc_rows(df: pd.DataFrame, score: str = "score_boundary_band") -> list[dict[str, Any]]:
    out = []
    for (method, fold), g in df[(df.status == "ok") & (df.split == "heldout")].groupby(["method", "fold"]):
        rc = risk_coverage(g[score].to_numpy(float), g["dice_mean"].to_numpy(float))
        out.append({"method": method, "fold": fold, "score": score, **rc})
    return out


def build_summary(cases: pd.DataFrame, calib: dict[tuple[str, str], CalibrationSet], ucfg: dict[str, Any],
                  ecfg: dict[str, Any], source: str, note: str, run: str = "") -> dict[str, Any]:
    df = add_case_columns(cases, ucfg["failure"]["tau"])
    st = ecfg["statistics"]
    gaps = gap_table(df, st["bootstrap_resamples"], st["seed"], st["small_group_warning_n"])
    rel_summary, rel_points = [], []
    for (method, fold), cs in calib.items():
        s, c = calibration_table(cs, method, fold)
        rel_summary.append(s)
        rel_points.append(c)
    reliability = []
    if rel_points:
        pts = pd.concat(rel_points)
        for (m, sp, reg, mode), g in pts.groupby(["method", "split", "region", "mode"]):
            # pool counts over folds for the diagram
            agg = g.groupby(["bin_lo", "bin_hi"]).apply(
                lambda x: pd.Series({"count": x["count"].sum(),
                                     "confidence": np.average(x["confidence"].fillna(0), weights=x["count"])
                                     if x["count"].sum() else np.nan,
                                     "accuracy": np.average(x["accuracy"].fillna(0), weights=x["count"])
                                     if x["count"].sum() else np.nan}), include_groups=False).reset_index()
            reliability.append({"method": m, "split": sp, "region": reg, "mode": mode,
                                "points": agg.to_dict(orient="records")})
    return {
        "status": "ok", "source": source, "note": note, "run": run,
        "tau": ucfg["failure"]["tau"],
        "methods": sorted(df["method"].unique().tolist()),
        "folds": sorted(df["fold"].unique().tolist()),
        "gaps": _clean(gaps.to_dict(orient="records")),
        "failure": _clean(failure_rows(df, ucfg)),
        "risk_coverage": _clean(rc_rows(df)),
        "reliability": _clean(reliability),
        "ece": _clean(pd.concat(rel_summary).to_dict(orient="records")) if rel_summary else [],
        "n_cases": int((df.status == "ok").sum()),
        "no_et_cases": int((~df.get("ref_has_et", pd.Series(True, index=df.index)).astype(bool)).sum()),
    }


def _clean(obj: Any) -> Any:
    """NaN -> None so the JSON is valid for browsers."""
    if isinstance(obj, dict):
        return {k: _clean(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_clean(v) for v in obj]
    if isinstance(obj, float | np.floating):
        return None if np.isnan(obj) else float(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    return obj
