"""Gate G3 smoke test on SYNTHETIC fixtures (works on CPU).

Steps: synthetic cases -> conversion -> nnU-Net raw dataset -> plan and
preprocess -> site-held-out folds from the fake institution table ->
a few tiny epochs of nnUNetTrainer_btqcSmoke on fold 0 -> prediction records
for the fold's in-site test and held-out cases (2 flips) -> harness metrics.
Checks: loss decreases, prediction files exist, the harness scores them.
Everything is logged to MLflow. Numbers describe a toy model on synthetic
ellipsoids and are NOT segmentation results.

    python scripts/train_smoke.py [--n-cases 10] [--epochs 3] [--iters 8]
"""

from __future__ import annotations

import argparse
import json
import shutil
import time

import numpy as np
import pandas as pd
import yaml

from btqc.config import REPO_ROOT, load_config
from btqc.data.convert import ConvertOptions, convert_all
from btqc.data.discover import discover
from btqc.data.fixtures import make_dataset
from btqc.data.manifest import load_institution_table
from btqc.data.sitegroups import assign_groups, group_summary
from btqc.eval.loso import evaluate_fold
from btqc.infer.predict import NnunetMember, load_canonical_case, predict_case
from btqc.infer.record import save_record
from btqc.train.nnunet_setup import build_raw_dataset, dataset_name, install_splits
from btqc.train.runner import mlflow_log, parse_losses, run_nnunet
from btqc.train.splits import check_folds, make_folds, to_nnunet_splits


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n-cases", type=int, default=12)
    ap.add_argument("--shape", type=int, nargs=3, default=(48, 48, 40))
    ap.add_argument("--epochs", type=int, default=None)
    ap.add_argument("--iters", type=int, default=None)
    ap.add_argument("--keep", action="store_true", help="reuse existing preprocessed fixture data")
    a = ap.parse_args(argv)
    tcfg = load_config("train")
    sm = tcfg["smoke"]
    epochs = a.epochs or sm["epochs"]
    iters = a.iters or sm["iterations"]
    did, dname = tcfg["dataset"]["fixture_id"], tcfg["dataset"]["fixture_name"]
    base = REPO_ROOT / "data" / "fixtures"
    raw, proc = base / "raw", base / "processed"
    t0 = time.time()
    if not a.keep and base.exists():
        shutil.rmtree(base)
    for sub in ("nnUNet_raw", "nnUNet_preprocessed", "nnUNet_results"):
        d = REPO_ROOT / "data" / sub / dataset_name(did, dname)
        if d.exists() and not a.keep:
            shutil.rmtree(d)

    # 1. synthetic data with a fake institution table (labeled SYNTHETIC)
    if not raw.exists():
        make_dataset(raw, n_cases=a.n_cases, shape=tuple(a.shape))
    convert_all(discover(raw), ConvertOptions(out_root=proc, raw_root=raw, montage=False), workers=1)
    inst = load_institution_table(raw / "partitioning_synthetic.csv")
    ci = dict(zip(inst.case_id, inst.institution, strict=True))
    rules = yaml.safe_load((REPO_ROOT / "configs" / "sitegroups.yaml").read_text())["rules"]
    cg = assign_groups(ci, rules)
    folds = make_folds(ci, cg, seed=1)
    assert check_folds(folds, cg) == []
    order = sorted(folds)
    # smoke: fold 0 = first group that leaves >= 2 training cases
    group = next(g for g in order if len(folds[g]["train"]) >= 2 and folds[g]["heldout"])
    print("fixture groups:", json.dumps(group_summary(ci, cg)))
    print(
        f"smoke fold: hold out {group!r}: train {len(folds[group]['train'])}, val {len(folds[group]['val'])}, "
        f"in-site test {len(folds[group]['insite_test'])}, held-out {len(folds[group]['heldout'])}"
    )

    model_dir = (
        REPO_ROOT
        / "data"
        / "nnUNet_results"
        / dataset_name(did, dname)
        / f"{sm['trainer']}__nnUNetPlans__{sm['configuration']}"
    )
    log = base / "train.log"
    reuse = a.keep and (model_dir / "fold_0" / "checkpoint_final.pth").exists() and log.exists()
    # 2. nnU-Net raw dataset, plan + preprocess, custom splits
    build_raw_dataset(
        proc / "canonical",
        REPO_ROOT / "data" / "nnUNet_raw",
        did,
        dname,
        sorted(ci),
        [],
        "SYNTHETIC fixture for the smoke test",
    )
    if not reuse and run_nnunet(
        [
            "nnUNetv2_plan_and_preprocess",
            "-d",
            str(did),
            "-c",
            sm["configuration"],
            "-np",
            "1",
            "-npfp",
            "1",
            "--verify_dataset_integrity",
        ],
        log=base / "plan.log",
    ):
        print("plan_and_preprocess failed; see", base / "plan.log")
        return 1
    # fold 0 = the smoke group; val must be non-empty for nnU-Net
    sp = to_nnunet_splits(folds, [group])
    if not sp[0]["val"]:
        sp[0]["val"] = sp[0]["train"][-1:]
    install_splits(sp, REPO_ROOT / "data" / "nnUNet_preprocessed", did, dname)

    # 3. train
    env = {"BTQC_EPOCHS": str(epochs), "BTQC_ITERS": str(iters), "BTQC_VAL_ITERS": "2", "BTQC_SEED": "12345"}
    rc = (
        0
        if reuse
        else run_nnunet(
            ["nnUNetv2_train", str(did), sm["configuration"], "0", "-tr", sm["trainer"], "-device", sm["device"]],
            extra_env=env,
            log=log,
        )
    )
    losses = parse_losses(log.read_text(encoding="utf-8", errors="replace"))
    print("train losses:", losses["train_loss"])
    if rc:
        print("training failed; see", log)
        return 1
    if reuse:
        print("reused the trained smoke model (--keep)")

    # 4. predict fold cases with 2 flips -> prediction records
    member = NnunetMember(model_dir, 0, device="cpu")
    pred_dir = base / "predictions" / "smoke" / group
    t_inf = []
    for cid in folds[group]["insite_test"] + folds[group]["heldout"]:
        img, spacing, _ = load_canonical_case(proc / "canonical", cid)
        t1 = time.time()
        rec = predict_case(
            [member], img, spacing, [(), (0,)], cid, {"method": "smoke", "fold": group, "source": "model"}
        )
        t_inf.append(time.time() - t1)
        save_record(rec, pred_dir)
    # 5. harness
    df = evaluate_fold(
        "smoke", group, folds[group], pred_dir, proc / "canonical", ci, "brats_124", splits=("insite_test", "heldout")
    )
    df.to_csv(base / "smoke_cases.csv", index=False)
    ok = df[df.status == "ok"]
    decreasing = len(losses["train_loss"]) >= 2 and losses["train_loss"][-1] < losses["train_loss"][0]
    gate = {
        "loss_decreased": bool(decreasing),
        "n_prediction_files": len(list(pred_dir.glob("*.npz"))),
        "n_scored": len(ok),
        "passed": bool(decreasing and len(ok) > 0 and len(list(pred_dir.glob("*.npz"))) == len(df)),
    }
    metrics = {
        "train_loss_first": losses["train_loss"][0] if losses["train_loss"] else float("nan"),
        "train_loss_last": losses["train_loss"][-1] if losses["train_loss"] else float("nan"),
        "mean_dice_WT": float(ok["dice_WT"].mean()) if len(ok) else float("nan"),
        "mean_infer_s": float(np.mean(t_inf)) if t_inf else float("nan"),
        "elapsed_s": time.time() - t0,
    }
    run_id = mlflow_log(
        "smoke_G3",
        {
            "dataset": dataset_name(did, dname),
            "trainer": sm["trainer"],
            "configuration": sm["configuration"],
            "epochs": epochs,
            "iters": iters,
            "seed": 12345,
            "fold_group": group,
            "n_cases": a.n_cases,
            "group_counts": json.dumps(group_summary(ci, cg)),
            "data": "SYNTHETIC",
        },
        {**metrics, **{k: float(v) for k, v in gate.items()}},
        [log, base / "smoke_cases.csv"],
    )
    out = {
        "gate_G3": gate,
        "metrics": metrics,
        "losses": losses,
        "mlflow_run_id": run_id,
        "fold_group": group,
        "note": "SYNTHETIC fixture; toy model; not a segmentation result",
        "cases": pd.read_csv(base / "smoke_cases.csv").to_dict(orient="records"),
    }
    (REPO_ROOT / "results").mkdir(exist_ok=True)
    (REPO_ROOT / "results" / "smoke_G3.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    print(json.dumps({"gate_G3": gate, "metrics": metrics, "mlflow_run_id": run_id}, indent=1))
    return 0 if gate["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
