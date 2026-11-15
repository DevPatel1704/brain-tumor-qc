"""SYNTHETIC pipeline demo: the whole evaluation chain on fixtures with the stub
predictor (derived from the reference masks; NOT A MODEL). Produces
results/eval_summary_synthetic.json, figures and tables, all labeled
SYNTHETIC. This demonstrates the software; it is not a result.

    python scripts/synthetic_demo.py [--n-cases 40]
"""

from __future__ import annotations

import argparse
import shutil

import nibabel as nib
import numpy as np
import yaml

from btqc.config import REPO_ROOT, load_config
from btqc.data.convert import ConvertOptions, convert_all
from btqc.data.discover import discover
from btqc.data.fixtures import make_dataset
from btqc.data.manifest import load_institution_table
from btqc.data.sitegroups import assign_groups
from btqc.eval.experiments import evaluate_methods, write_outputs
from btqc.eval.summary import build_summary
from btqc.infer.record import save_record
from btqc.infer.stub import stub_record
from btqc.train.splits import check_folds, make_folds

NOTE = ("Synthetic ellipsoid fixtures and a stub predictor that perturbs the reference mask, with harder "
        "perturbation for held-out groups by construction. It demonstrates the harness, uncertainty, failure "
        "detection and charts end to end. It says nothing about real model behavior.")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n-cases", type=int, default=40)
    a = ap.parse_args(argv)
    base = REPO_ROOT / "data" / "synthetic_demo"
    if base.exists():
        shutil.rmtree(base)
    raw, proc, preds = base / "raw", base / "processed", base / "predictions"
    make_dataset(raw, n_cases=a.n_cases, shape=(64, 64, 48), seed=100)
    convert_all(discover(raw), ConvertOptions(out_root=proc, raw_root=raw, montage=False), workers=1)
    inst = load_institution_table(raw / "partitioning_synthetic.csv")
    ci = dict(zip(inst.case_id, inst.institution, strict=True))
    rules = yaml.safe_load((REPO_ROOT / "configs" / "sitegroups.yaml").read_text())["rules"]
    cg = assign_groups(ci, rules)
    folds = make_folds(ci, cg, seed=load_config("sitegroups")["splits"]["seed"])
    assert check_folds(folds, cg) == []
    can = proc / "canonical"
    rng = np.random.default_rng(0)
    group_difficulty = {g: d for g, d in zip(sorted(folds), np.linspace(0.3, 0.9, len(folds)))}
    for method, factor in (("stub_baseline", 1.0), ("stub_mitigated", 0.7)):
        for g, f in folds.items():
            for split in ("val", "insite_test", "heldout"):
                for cid in f[split]:
                    seg = np.asarray(nib.load(str(can / cid / f"{cid}_seg.nii.gz")).dataobj).astype(np.uint8)
                    brain = np.asarray(nib.load(str(can / cid / f"{cid}_flair.nii.gz")).dataobj) != 0
                    # per-case difficulty: wide spread for held-out cases so both outcomes occur
                    top = group_difficulty[g] * 1.3 if split == "heldout" else 0.3
                    d = float(np.clip(rng.uniform(0.02, top) * factor, 0, 1))
                    save_record(stub_record(cid, seg, brain, (1.0, 1.0, 1.0), d, g, method,
                                            seed=int(rng.integers(1 << 30))), preds / method / g)
    cases, calib = evaluate_methods(preds, can, folds, ci, "brats_124")
    summ = build_summary(cases, calib, load_config("uncertainty"), load_config("eval"), "synthetic", NOTE,
                         "scripts/synthetic_demo.py")
    out = write_outputs(summ, cases, REPO_ROOT / "results", tag="synthetic")
    print(f"SYNTHETIC demo: {summ['n_cases']} case rows; wrote {len(out)} files (labeled SYNTHETIC)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
