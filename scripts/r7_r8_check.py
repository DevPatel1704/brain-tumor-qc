"""R7 and R8 checks on the trained model, without training.

R7 (reproducibility of inference): re-predict cases that already have a stored record, with the same
members and flips, and compare labels, probabilities and the case score with the stored record.
R8 (latency): time one case end to end (load, all members x flips, uncertainty, scores) with 8 flips
and with 1 flip (no test-time augmentation). Writes results/r7_r8.json.

    python scripts/r7_r8_check.py --fold mid --cases 3
"""

from __future__ import annotations

import argparse
import json
import time

import numpy as np

from btqc.config import REPO_ROOT, load_config, resolve
from btqc.infer.ensemble import member_indices
from btqc.infer.predict import NnunetMember, load_canonical_case, predict_case
from btqc.infer.record import load_record, save_record
from btqc.infer.tta import flip_sets
from btqc.train.nnunet_setup import dataset_name


def dice(a: np.ndarray, b: np.ndarray) -> float:
    s = a.sum() + b.sum()
    return 1.0 if s == 0 else float(2 * (a & b).sum() / s)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fold", default="mid")
    ap.add_argument("--cases", type=int, default=3)
    ap.add_argument("--device", default="cuda")
    a = ap.parse_args(argv)
    tcfg, dcfg, ucfg = load_config("train"), load_config("data"), load_config("uncertainty")
    fj = json.loads((REPO_ROOT / "data" / "splits" / "folds.json").read_text())
    model_dir = (resolve(dcfg["nnunet_results"]) / dataset_name(int(tcfg["dataset"]["id"]), tcfg["dataset"]["name"])
                 / f"nnUNetTrainer_btqc__{tcfg['plans']}__{tcfg['configuration']}")
    idx = member_indices(fj["fold_order"], a.fold, int(fj["meta"]["n_members"]))
    members = [NnunetMember(model_dir, i, device=a.device) for i in idx]
    can = resolve(dcfg["processed_root"]) / "canonical"
    pred_dir = REPO_ROOT / "results" / "predictions" / "baseline" / a.fold
    band = int(ucfg["case_score"]["band_width_voxels"])
    cases = sorted(p.stem for p in pred_dir.glob("*.npz"))[: a.cases]
    r7, r8 = [], []
    for cid in cases:
        stored = load_record(pred_dir, cid)
        t0 = time.time()
        img, spacing, _ = load_canonical_case(can, cid)
        t_load = time.time() - t0
        meta = {"method": "baseline", "fold": a.fold, "member_indices": idx}
        t1 = time.time()
        rec8 = predict_case(members, img, spacing, flip_sets()[:8], cid, meta, band)
        t8 = time.time() - t1
        # compare like with like: the stored record went through save_record's quantization
        tmp = REPO_ROOT / "results" / "cache" / "r7_rerun"
        save_record(rec8, tmp)
        rec8 = load_record(tmp, cid)
        t2 = time.time()
        predict_case(members, img, spacing, flip_sets()[:1], cid, meta, band)
        t1f = time.time() - t2
        s_old, s_new = stored.meta["scores"]["boundary_band"], rec8.meta["scores"]["boundary_band"]
        r7.append({"case": cid, "label_agreement": float((stored.seg == rec8.seg).mean()),
                   "dice_WT_vs_stored": dice(stored.seg > 0, rec8.seg > 0),
                   "max_abs_prob_diff": float(np.abs(stored.prob.astype(np.float32) -
                                                     rec8.prob.astype(np.float32)).max()),
                   "score_stored": s_old, "score_rerun": s_new, "score_abs_diff": abs(s_old - s_new)})
        r8.append({"case": cid, "load_s": round(t_load, 1), "predict_8_flips_s": round(t8, 1),
                   "predict_1_flip_s": round(t1f, 1), "total_8_flips_s": round(t_load + t8, 1),
                   "total_1_flip_s": round(t_load + t1f, 1)})
        print(r7[-1], r8[-1], flush=True)
    out = {"status": "ok", "fold": a.fold, "device": a.device, "r7": r7, "r8": r8,
           "r8_target_s": 60,
           "r8_mean_total_8_flips_s": float(np.mean([r["total_8_flips_s"] for r in r8])),
           "r8_mean_total_1_flip_s": float(np.mean([r["total_1_flip_s"] for r in r8])),
           "r7_max_score_abs_diff": float(max(r["score_abs_diff"] for r in r7)),
           "r7_min_label_agreement": float(min(r["label_agreement"] for r in r7))}
    (REPO_ROOT / "results" / "r7_r8.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("wrote results/r7_r8.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
