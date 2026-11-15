"""Site risk report for a batch of unlabeled scans (Phase 7, item 7).

Computes z-scored brain-intensity histograms per case and sequence (cached),
the batch profile, its Wasserstein-1 / KS distance to a reference profile,
and, if a shift-versus-gap model from the site-held-out folds exists
(results/shift/gap_model.json, written by scripts/e2_shift.py), an ESTIMATE of
the expected held-out Dice with a range.

Reference profile: results/shift/reference_profile.json (training pool, written
by e2_shift.py). If it does not exist, an EXAMPLE reference made of the
remaining processed cases is used and labeled as such.

    python scripts/site_risk.py [--batch ID ...] [--first N]
"""

from __future__ import annotations

import argparse
import json

import numpy as np

from btqc.config import REPO_ROOT, load_config, resolve
from btqc.data.discover import SEQUENCES
from btqc.eval.shift import case_hists, estimate_performance, group_profile, profile_distances


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--batch", nargs="*", default=None, help="case ids of the new-site batch")
    ap.add_argument("--first", type=int, default=20, help="if no batch is given: the first N processed cases")
    a = ap.parse_args(argv)
    cfg = load_config("serve")
    can = resolve(cfg["processed_root"]) / "canonical"
    all_ids = sorted(p.name for p in can.iterdir() if (p / "meta.json").exists())
    unlabeled = [c for c in all_ids if not (can / c / f"{c}_seg.nii.gz").exists()]
    if a.batch:
        batch, desc = a.batch, "user-selected batch"
    elif unlabeled and len(unlabeled) < len(all_ids):
        # labeled data present: the natural "new scans" batch is the unlabeled FeTS 2022 validation set
        batch = unlabeled
        desc = f"the {len(batch)} unlabeled FeTS 2022 validation cases (sites not published)"
    else:
        batch = all_ids[: a.first]
        desc = f"EXAMPLE batch: the first {len(batch)} processed cases, site unknown"
    hists = case_hists(can, all_ids, REPO_ROOT / "results" / "cache" / "intensity_hists.npz")
    target = {s: group_profile([hists[c][s] for c in batch]) for s in SEQUENCES}
    ref_path = REPO_ROOT / "results" / "shift" / "reference_profile.json"
    if ref_path.exists():
        ref_json = json.loads(ref_path.read_text(encoding="utf-8"))
        reference = {s: np.asarray(ref_json["profile"][s]) for s in SEQUENCES}
        ref_info = {"kind": "training_pool", "note": ref_json.get("note", ""), "n_cases": ref_json.get("n_cases")}
    else:
        rest = [c for c in all_ids if c not in set(batch)]
        reference = {s: group_profile([hists[c][s] for c in rest]) for s in SEQUENCES}
        ref_info = {"kind": "example", "n_cases": len(rest),
                    "note": f"No training-pool profile exists (no labeled training data). The reference here is the "
                            f"other {len(rest)} processed validation cases, only to demonstrate the computation."}
    shift = profile_distances(target, reference)
    per_case = []
    for c in batch:
        d = profile_distances({s: hists[c][s] for s in SEQUENCES}, reference)
        per_case.append({"case_id": c, "w1_mean": d["w1_mean"], "ks_mean": d["ks_mean"]})
    gm_path = REPO_ROOT / "results" / "shift" / "gap_model.json"
    if gm_path.exists() and ref_info["kind"] == "training_pool":
        gm = json.loads(gm_path.read_text(encoding="utf-8"))
        est = estimate_performance(gm["model"], shift[gm.get("shift_key", "w1_mean")], gm["insite_dice"])
        est["n_folds"] = gm["model"]["n"]
        if not np.isfinite(est["estimate"]):
            est = {"estimate": None, "n_folds": gm["model"]["n"],
                   "reason": f"Not available: the shift-versus-gap model needs at least 2 trained site-held-out "
                             f"folds; {gm['model']['n']} trained (docs/deviations.md D15)."}
    else:
        est = {"estimate": None, "reason": "Not available: no shift-versus-gap model from site-held-out folds exists "
               "(needs labeled training data and trained folds)."}
    out = {"status": "ok", "batch": {"n_cases": len(batch), "description": desc, "case_ids": batch},
           "reference": ref_info, "shift": shift, "cases": per_case, "estimate": est,
           "note": "Shift metrics are computed from images only. Any accuracy number here is an estimate."}
    p = REPO_ROOT / "results" / "site_risk.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
    print(json.dumps({"shift": shift, "estimate": est, "reference": ref_info["kind"]}, indent=1, default=float))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
