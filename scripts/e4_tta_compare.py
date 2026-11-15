"""E4 (no-training part): is the uncertainty from 8 flip members better calibrated and a better failure
detector than a single prediction? Compares the baseline records with 8 flips (results/predictions) and with
1 flip (results/predictions_notta) on exactly the same cases. Writes results/e4_tta_compare.json.

    python scripts/e4_tta_compare.py --fold mid
"""

from __future__ import annotations

import argparse
import json

from btqc.config import REPO_ROOT, load_config, resolve
from btqc.eval.experiments import evaluate_methods
from btqc.eval.summary import build_summary


def summarize(pred_root, folds, ctx):  # type: ignore[no-untyped-def]
    cases, calib = evaluate_methods(pred_root, ctx["canonical"], folds, ctx["ci"], "brats_124", ["baseline"])
    summ = build_summary(cases, calib, load_config("uncertainty"), load_config("eval"), "model", "e4 tta compare")
    ok = cases[cases.status == "ok"]
    return {
        "n_cases": len(ok),
        "mean_dice": {r: float(ok[f"dice_{r}"].mean()) for r in ("WT", "TC", "ET")},
        "ece": [e for e in summ["ece"] if e["mode"] == "band"],
        "failure": [f for f in summ["failure"] if f["score"] == "boundary_band"],
        "risk_coverage": [{k: v for k, v in r.items() if k not in ("coverage", "mean_dice")}
                          for r in summ["risk_coverage"] if r["score"] == "score_boundary_band"],
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fold", default="mid")
    a = ap.parse_args(argv)
    notta = REPO_ROOT / "results" / "predictions_notta"
    d = notta / "baseline" / a.fold
    ids = {p.stem for p in d.glob("*.npz")}
    if not ids:
        print("no no-TTA records; run scripts/infer.py --flips 1 --pred-root results/predictions_notta first")
        return 2
    fj = json.loads((REPO_ROOT / "data" / "splits" / "folds.json").read_text())
    sg = json.loads((REPO_ROOT / "data" / "sitegroups.json").read_text())
    f = fj["folds"][a.fold]
    # restrict both runs to the cases that have a 1-flip record, so the comparison is paired
    folds = {a.fold: {s: [c for c in f[s] if c in ids] for s in ("val", "insite_test", "heldout")}}
    ctx = {"canonical": resolve(load_config("data")["processed_root"]) / "canonical", "ci": sg["case_institution"]}
    out = {"status": "ok", "fold": a.fold, "n_cases": len(ids),
           "flips_8": summarize(REPO_ROOT / "results" / "predictions", folds, ctx),
           "flips_1": summarize(notta, folds, ctx)}
    (REPO_ROOT / "results" / "e4_tta_compare.json").write_text(json.dumps(out, indent=1, default=float),
                                                               encoding="utf-8")
    print("wrote results/e4_tta_compare.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
