"""Build the nnU-Net raw dataset(s) from the canonical files.

Labeled cases -> imagesTr/labelsTr; unlabeled cases (e.g. the validation
download) -> imagesTs. With --standardized, also writes the per-case
percentile-standardized variant (mitigation 3) as a second dataset.
If data/splits/splits_final.json exists and the dataset is already planned,
installs it into nnUNet_preprocessed.

    python scripts/nnunet_prep.py [--standardized] [--plan]
"""

from __future__ import annotations

import argparse
import shutil

import pandas as pd

from btqc.config import REPO_ROOT, load_config, resolve
from btqc.train.nnunet_setup import build_raw_dataset, dataset_name


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--standardized", action="store_true")
    ap.add_argument("--plan", action="store_true", help="run nnUNetv2_plan_and_preprocess afterwards")
    a = ap.parse_args(argv)
    dcfg, tcfg = load_config("data"), load_config("train")
    man = pd.read_csv(resolve(dcfg["manifest"]))
    can = resolve(dcfg["processed_root"]) / "canonical"
    done = {p.name for p in can.iterdir() if (p / "meta.json").exists()}
    labeled = sorted(c for c, s in zip(man.case_id, man.has_seg.astype(bool), strict=True) if s and c in done)
    unlabeled = sorted(c for c, s in zip(man.case_id, man.has_seg.astype(bool), strict=True) if not s and c in done)
    did, name = int(tcfg["dataset"]["id"]), tcfg["dataset"]["name"]
    raw_root = resolve(dcfg["nnunet_raw"])
    out = build_raw_dataset(can, raw_root, did, name, labeled, unlabeled,
                            "FeTS 2022, canonical RAS copies; labels remapped 2->1, 1->2, 4->3")
    print(f"{dataset_name(did, name)}: {len(labeled)} training cases, {len(unlabeled)} test cases -> {out}")
    if a.standardized:
        from btqc.data.standardize import build_standardized_dataset

        out2 = build_standardized_dataset(can, raw_root, did + 1, name + "_pct", labeled, unlabeled)
        print(f"standardized variant -> {out2}")
    if not labeled:
        print("No labeled cases: nnU-Net planning and training are not possible (situation C). "
              "imagesTs is ready for inference once a trained model exists.")
        return 0
    if a.plan:
        from btqc.train.runner import run_nnunet

        # -npfp also sets the integrity-check pool (nnU-Net default 8). One BLAS thread
        # per worker: each OpenBLAS thread commits its own buffer, which exhausted the
        # Windows commit limit on an 8 GB laptop.
        nw = str(tcfg.get("preprocess_workers", 4))
        cmd = ["nnUNetv2_plan_and_preprocess", "-d", str(did), "-c", tcfg["configuration"],
               "--verify_dataset_integrity", "-np", nw, "-npfp", nw]
        if tcfg.get("gpu_memory_target"):
            cmd += ["-gpu_memory_target", str(tcfg["gpu_memory_target"]), "-overwrite_plans_name", tcfg["plans"]]
        if run_nnunet(cmd, extra_env={"nnUNet_def_n_proc": nw, "OPENBLAS_NUM_THREADS": "1",
                                      "OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"}):
            return 1
    sp = REPO_ROOT / "data" / "splits" / "splits_final.json"
    pre = resolve(dcfg["nnunet_preprocessed"]) / dataset_name(did, name)
    if sp.exists() and pre.exists():
        shutil.copy(sp, pre / "splits_final.json")
        print(f"installed {sp} -> {pre}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
