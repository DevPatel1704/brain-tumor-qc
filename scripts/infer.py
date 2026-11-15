"""Phase 5: ensemble + flip-TTA inference for every method and fold, writing
prediction records to results/predictions/<method>/<fold>/.

Leakage rule: fold g is predicted only by the members of fold g
(btqc.infer.ensemble.check_ensemble). Cases: the fold's val (review-limit
selection), insite_test and heldout lists. ``--deploy`` predicts the
unlabeled imagesTs cases with the members of one fold for the dashboard.

    python scripts/infer.py --methods baseline [--max-cases 5] [--flips 8] [--device cuda]
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

from btqc.config import REPO_ROOT, load_config, resolve
from btqc.infer.ensemble import check_ensemble, member_indices
from btqc.infer.predict import NnunetMember, load_canonical_case, predict_case
from btqc.infer.record import save_record
from btqc.infer.tta import flip_sets
from btqc.train.nnunet_setup import dataset_name

SPLITS = ("val", "insite_test", "heldout")


def _rolling_order(fold: dict[str, list[str]], seed: int, n_first: int) -> list[str]:
    """Each split: the n_first seeded draw (sorted), then the remaining cases shuffled with seed + 1.
    Splits are interleaved round-robin, so any prefix holds about equally many random cases per split."""
    per = []
    for s in SPLITS:
        first = sorted(random.Random(seed).sample(fold[s], min(n_first, len(fold[s]))))
        rest = [c for c in fold[s] if c not in set(first)]
        random.Random(seed + 1).shuffle(rest)
        per.append(first + rest)
    out = []
    for i in range(max(len(p) for p in per)):
        out += [p[i] for p in per if i < len(p)]
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--methods", nargs="*", default=["baseline"])
    ap.add_argument("--groups", nargs="*", default=None)
    ap.add_argument("--flips", type=int, default=8, help="number of flip members (1 = no TTA)")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--max-cases", type=int, default=None)
    ap.add_argument("--per-split", type=int, default=None,
                    help="undersample: N cases drawn (seeded) from each of val, insite_test and heldout")
    ap.add_argument("--rolling", action="store_true",
                    help="all cases in an any-time order: the --per-split seeded draw first, then the rest of each "
                         "split in seeded random order, alternating val/insite_test/heldout, so stopping at any "
                         "point leaves each split a random sample of about equal size")
    ap.add_argument("--stop-at", default=None, help="HH:MM local time after which no new case is started")
    ap.add_argument("--splits", nargs="*", default=None,
                    help="only these splits (val, insite_test, heldout); e.g. a mitigation compared on held-out cases")
    ap.add_argument("--pred-root", default=None,
                    help="write records under this folder instead of results/predictions (side analyses such as a "
                         "no-TTA comparison, kept out of the main experiments)")
    ap.add_argument("--deploy", default=None, help="fold group whose members predict the unlabeled cases")
    a = ap.parse_args(argv)
    tcfg, dcfg, ucfg = load_config("train"), load_config("data"), load_config("uncertainty")
    fj_p = REPO_ROOT / "data" / "splits" / "folds.json"
    if not fj_p.exists():
        print("No folds (needs labeled data). Nothing to predict with; see docs/phase_reports.", file=sys.stderr)
        return 2
    fj = json.loads(fj_p.read_text(encoding="utf-8"))
    order, nm, folds = fj["fold_order"], int(fj["meta"]["n_members"]), fj["folds"]
    can = resolve(dcfg["processed_root"]) / "canonical"
    flips = flip_sets()[: a.flips]
    band = int(ucfg["case_score"]["band_width_voxels"])
    for mname in a.methods:
        m = tcfg["methods"][mname]
        dsid = int(tcfg["dataset"]["id"]) + (1 if m["dataset_suffix"] else 0)
        model_dir = (resolve(dcfg["nnunet_results"]) / dataset_name(dsid, tcfg["dataset"]["name"] + m["dataset_suffix"])
                     / f"{m['trainer']}__{tcfg['plans']}__{tcfg['configuration']}")
        for g in ([a.deploy] if a.deploy else (a.groups or order)):
            idx = member_indices(order, g, nm)
            check_ensemble(order, g, idx, nm)
            members = [NnunetMember(model_dir, i, device=a.device) for i in idx]
            if a.deploy:
                cases = sorted(p.name for p in can.iterdir() if not (p / f"{p.name}_seg.nii.gz").exists())
                out = REPO_ROOT / "results" / "predictions" / mname / f"deploy_{g}"
            else:
                # split lists are sorted by ID (clustered by institution), so undersample with a seeded draw
                n = a.per_split
                if a.rolling:
                    cases = _rolling_order(folds[g], int(tcfg["seed"]), n or 15)
                else:
                    cases = [c for s in SPLITS for c in
                             (sorted(random.Random(int(tcfg["seed"])).sample(folds[g][s], min(n, len(folds[g][s]))))
                              if n else folds[g][s])]
                if a.splits:
                    keep = {c for sp in a.splits for c in folds[g][sp]}
                    cases = [c for c in cases if c in keep]
                out = (Path(a.pred_root) if a.pred_root else REPO_ROOT / "results" / "predictions") / mname / g
            for cid in cases[: a.max_cases]:
                if a.stop_at and time.strftime("%H:%M") >= a.stop_at:
                    print(f"stop time {a.stop_at} reached; finished cases are kept")
                    return 0
                if (out / f"{cid}.npz").exists():
                    continue
                img, spacing, _ = load_canonical_case(can, cid)
                t0 = time.time()
                if m.get("inference") == "entropy_tta":
                    from btqc.infer.tta_adapt_nnunet import adapted_members

                    use = adapted_members(members, img, spacing)
                else:
                    use = members
                rec = predict_case(use, img, spacing, flips, cid, {"method": mname, "fold": g if not a.deploy else
                                   f"deploy_{g}", "member_indices": idx, "model_dir": str(model_dir)}, band)
                save_record(rec, out)
                print(f"  {mname}/{g}/{cid}: {time.time() - t0:.1f}s, score {rec.meta['scores']['boundary_band']:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
