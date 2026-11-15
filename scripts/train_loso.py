"""Phase 3/4: site-held-out training of every method, fold and seed replicate.

Prints an estimate first and asks for --yes before any job longer than 30
minutes. Resumable: folds with checkpoint_final.pth are skipped, folds with
checkpoint_latest.pth continue (nnU-Net --c).

    python scripts/train_loso.py --dry-run
    python scripts/train_loso.py --methods baseline --device cuda --yes
"""

from __future__ import annotations

import argparse
import json
import sys

from btqc.config import REPO_ROOT, load_config, resolve
from btqc.sysinfo import machine_report
from btqc.train.nnunet_setup import dataset_name
from btqc.train.runner import estimate_hours, mlflow_log, parse_losses, run_nnunet


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--methods", nargs="*", default=None)
    ap.add_argument("--groups", nargs="*", default=None)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--yes", action="store_true", help="confirm long jobs after reading the estimate")
    a = ap.parse_args(argv)
    tcfg, dcfg = load_config("train"), load_config("data")
    folds_p = REPO_ROOT / "data" / "splits" / "folds.json"
    if not folds_p.exists():
        print("data/splits/folds.json missing: run `make sitegroups` with labeled data and an institution table.",
              file=sys.stderr)
        return 2
    fj = json.loads(folds_p.read_text(encoding="utf-8"))
    order, nm = fj["fold_order"], int(fj["meta"]["n_members"])
    groups = a.groups or order
    methods = {k: v for k, v in tcfg["methods"].items() if not v.get("inference")}
    if a.methods:
        methods = {k: v for k, v in methods.items() if k in a.methods}
    mach = machine_report(REPO_ROOT, check_network=False)
    tier = mach["compute_tier"]
    gpu_key = "gpu_24gb" if tier == 2 else ("gpu_8gb" if tier == 1 else "gpu_4gb")
    spe = tcfg["seconds_per_epoch"]["cpu" if a.device == "cpu" else gpu_key]
    hours = estimate_hours(len(groups), nm, len(methods), int(tcfg["epochs"]), spe)
    print(f"plan: {len(methods)} methods x {len(groups)} folds x {nm} members x {tcfg['epochs']} epochs "
          f"on {a.device} (tier {tier}) ~ {hours:.1f} h (estimate from configs/train.yaml seconds_per_epoch={spe})")
    if a.dry_run:
        return 0
    if hours > 0.5 and not a.yes:
        print("This is longer than 30 minutes. Re-run with --yes to start.", file=sys.stderr)
        return 3
    did, name = int(tcfg["dataset"]["id"]), tcfg["dataset"]["name"]
    for mname, m in methods.items():
        dsid = did + (1 if m["dataset_suffix"] else 0)
        dsname = name + m["dataset_suffix"]
        for g in groups:
            for k in range(nm):
                idx = order.index(g) * nm + k
                out = (resolve(dcfg["nnunet_results"]) / dataset_name(dsid, dsname) /
                       f"{m['trainer']}__{tcfg['plans']}__{tcfg['configuration']}" / f"fold_{idx}")
                if (out / "checkpoint_final.pth").exists():
                    print(f"skip {mname}/{g}/member {k}: done")
                    continue
                args = ["nnUNetv2_train", str(dsid), tcfg["configuration"], str(idx), "-tr", m["trainer"],
                        "-p", tcfg["plans"], "-device", a.device, "--npz"]
                if (out / "checkpoint_latest.pth").exists():
                    args.append("--c")
                log = REPO_ROOT / "results" / "train_logs" / f"{mname}_{g}_m{k}.log"
                rc = run_nnunet(args, {"BTQC_EPOCHS": str(tcfg["epochs"]), "BTQC_SEED": str(tcfg["seed"]),
                                       "BTQC_CUDNN_BENCHMARK": "1" if tcfg.get("cudnn_benchmark", True) else "0"},
                                log)
                losses = parse_losses(log.read_text(encoding="utf-8", errors="replace"))
                mlflow_log(f"{mname}_{g}_m{k}", {"method": mname, "fold_group": g, "fold_index": idx, "member": k,
                                                 "trainer": m["trainer"], "dataset": dataset_name(dsid, dsname),
                                                 "epochs": tcfg["epochs"], "seed": int(tcfg["seed"]) + idx,
                                                 "group_counts": json.dumps(fj["meta"]["group_counts"])},
                           {"train_loss_last": losses["train_loss"][-1] if losses["train_loss"] else float("nan"),
                            "returncode": rc}, [log])
                if rc:
                    print(f"training failed for {mname}/{g}/member {k}; see {log}", file=sys.stderr)
                    return rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
