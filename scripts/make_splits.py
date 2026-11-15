"""Phase 3: site groups and site-held-out folds from the manifest's institution column.

Writes data/sitegroups.json and data/splits/{folds.json, splits_final.json}.
nnU-Net fold index = group_position * n_members + member (see btqc.infer.ensemble).
Refuses to invent site labels: without an institution table it exits with a
message (situation B/C).

    python scripts/make_splits.py [--institution-table PATH]
"""

from __future__ import annotations

import argparse
import json
import sys

import pandas as pd

from btqc.config import REPO_ROOT, load_config, resolve
from btqc.data.manifest import load_institution_table
from btqc.data.sitegroups import assign_groups, group_summary
from btqc.train.splits import check_folds, make_folds, save_folds


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--institution-table", default=None)
    a = ap.parse_args(argv)
    dcfg, scfg, tcfg = load_config("data"), load_config("sitegroups"), load_config("train")
    man = pd.read_csv(resolve(dcfg["manifest"]))
    man = man[man["has_seg"].astype(bool)]
    table = a.institution_table or dcfg.get("institution_table")
    if man.empty:
        print("No labeled cases in the manifest (situation C). Site groups need labeled FeTS 2022 training data.",
              file=sys.stderr)
        return 2
    if not table:
        print("No institution table configured (situation B). Site labels are never invented; set "
              "institution_table in configs/data.yaml to the FeTS partitioning CSV.", file=sys.stderr)
        return 2
    inst = load_institution_table(resolve(table))
    ci = {c: int(i) for c, i in zip(inst.case_id, inst.institution, strict=True) if c in set(man.case_id)}
    missing = sorted(set(man.case_id) - set(ci))
    if missing:
        print(f"warning: {len(missing)} labeled cases have no institution and are excluded: {missing[:5]}...")
    cg = assign_groups(ci, scfg["rules"])
    summary = group_summary(ci, cg)
    for g, s in summary.items():
        print(f"  {g:10s} {s['n_cases']:5d} cases from {s['n_institutions']} institutions")
    folds = make_folds(ci, cg, seed=scfg["splits"]["seed"], fractions=scfg["splits"]["fractions"])
    problems = check_folds(folds, cg)
    if problems:
        print("\n".join(problems), file=sys.stderr)
        return 1
    order = sorted(folds)
    n_members = int(tcfg["n_members"])
    out = REPO_ROOT / "data" / "splits"
    meta = {"seed": scfg["splits"]["seed"], "fractions": scfg["splits"]["fractions"], "group_counts": summary,
            "n_members": n_members, "fold_index": "group_position * n_members + member",
            "institution_table": str(table)}
    p1, _ = save_folds(folds, order, out, meta)
    # nnU-Net list: each group's split repeated n_members times (seed replicates)
    nn = [{"train": folds[g]["train"], "val": folds[g]["val"]} for g in order for _ in range(n_members)]
    (out / "splits_final.json").write_text(json.dumps(nn, indent=1), encoding="utf-8")
    (REPO_ROOT / "data" / "sitegroups.json").write_text(json.dumps({"case_group": cg, "case_institution": ci,
                                                                     "summary": summary}, indent=1), encoding="utf-8")
    print(f"wrote {p1} and splits_final.json ({len(nn)} nnU-Net folds). Commit data/splits/ before training.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
