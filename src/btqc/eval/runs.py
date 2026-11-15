"""Experiment implementations E1-E6 (scripts/e1_gap.py ... e6_software.py call these).

Each experiment writes results/e<N>_<name>.json. When its inputs do not exist
(no labeled data, no trained models), it writes ``status: "not run"`` with the
reason instead of any number.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd

from btqc.config import REPO_ROOT, load_config, resolve

RESULTS = REPO_ROOT / "results"


def _write(name: str, obj: dict[str, Any]) -> Path:
    RESULTS.mkdir(exist_ok=True)
    p = RESULTS / f"{name}.json"
    p.write_text(json.dumps(obj, indent=1, default=float), encoding="utf-8")
    print(f"{name}: {obj.get('status')} -> {p}")
    return p


def _not_run(name: str, reason: str) -> Path:
    return _write(name, {"status": "not run", "reason": reason})


def context() -> dict[str, Any] | None:
    fj = REPO_ROOT / "data" / "splits" / "folds.json"
    sg = REPO_ROOT / "data" / "sitegroups.json"
    if not fj.exists() or not sg.exists():
        return None
    return {"folds": json.loads(fj.read_text())["folds"], "ci": json.loads(sg.read_text())["case_institution"],
            "canonical": resolve(load_config("data")["processed_root"]) / "canonical",
            "preds": RESULTS / "predictions"}


NO_DATA = ("no site-held-out folds: labeled FeTS 2022 training data and the partitioning CSV are not available "
           "(data situation C)")


def evaluate_all(ctx: dict[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]] | None:
    from btqc.eval.experiments import evaluate_methods, write_outputs
    from btqc.eval.summary import build_summary

    methods = [m for m in sorted(p.name for p in ctx["preds"].iterdir() if p.is_dir())
               if m not in ("example_rule_based", "live")] if ctx["preds"].exists() else []
    if not methods:
        return None
    cases, calib = evaluate_methods(ctx["preds"], ctx["canonical"], ctx["folds"], ctx["ci"], "brats_124", methods)
    summ = build_summary(cases, calib, load_config("uncertainty"), load_config("eval"), "model",
                         "site-held-out harness", "scripts/run_experiments.py")
    write_outputs(summ, cases, RESULTS)
    return cases, summ


def e1_gap() -> Path:
    ctx = context()
    if ctx is None:
        return _not_run("e1_gap", NO_DATA)
    r = evaluate_all(ctx)
    if r is None:
        return _not_run("e1_gap", "no prediction records (train models and run `make infer`)")
    _, summ = r
    g = pd.DataFrame(summ["gaps"])
    base = g[(g.method == "baseline") & (g.metric == "dice")] if len(g) else g
    if len(base):  # folds without in-site or held-out predictions have no gap
        base = base[pd.to_numeric(base["gap"], errors="coerce").notna()]
    h1 = {"largest_gap_region": base.groupby("region")["gap"].mean().idxmax() if len(base) else None,
          "largest_gap_group": base.groupby("fold")["gap"].mean().idxmax() if len(base) else None,
          "all_gaps_positive": bool((base["gap"] > 0).all()) if len(base) else None}
    return _write("e1_gap", {"status": "ok", "gaps": summ["gaps"], "H1": h1})


def e2_shift() -> Path:
    ctx = context()
    if ctx is None:
        return _not_run("e2_shift", NO_DATA)
    from btqc.data.discover import SEQUENCES
    from btqc.eval.shift import case_hists, fit_gap_model, group_profile, profile_distances
    from btqc.eval.stats import spearman

    sg = json.loads((REPO_ROOT / "data" / "sitegroups.json").read_text())["case_group"]
    ids = sorted(sg)
    hists = case_hists(ctx["canonical"], ids, RESULTS / "cache" / "intensity_hists.npz")
    rows = []
    for g, f in ctx["folds"].items():
        tgt = {s: group_profile([hists[c][s] for c in f["heldout"]]) for s in SEQUENCES}
        ref = {s: group_profile([hists[c][s] for c in f["train"]]) for s in SEQUENCES}
        rows.append({"fold": g, **profile_distances(tgt, ref)})
    pool = {s: group_profile([hists[c][s] for c in ids]) for s in SEQUENCES}
    (RESULTS / "shift").mkdir(exist_ok=True)
    (RESULTS / "shift" / "reference_profile.json").write_text(json.dumps(
        {"profile": {s: v.tolist() for s, v in pool.items()}, "n_cases": len(ids),
         "note": "training pool (all labeled cases)"}), encoding="utf-8")
    gaps_p = RESULTS / "gaps.csv"
    out: dict[str, Any] = {"status": "ok", "shift": rows}
    if gaps_p.exists():
        gaps = pd.read_csv(gaps_p)
        gb = gaps[(gaps.method == "baseline") & (gaps.metric == "dice") & (gaps.region == "WT")].set_index("fold")
        sh = pd.DataFrame(rows).set_index("fold").join(gb[["gap", "insite_mean"]], how="inner")
        out["spearman_w1_vs_gap"] = spearman(sh["w1_mean"].to_numpy(), sh["gap"].to_numpy())
        out["spearman_ks_vs_gap"] = spearman(sh["ks_mean"].to_numpy(), sh["gap"].to_numpy())
        model = fit_gap_model(sh["w1_mean"].to_numpy(), sh["gap"].to_numpy())
        (RESULTS / "shift" / "gap_model.json").write_text(json.dumps(
            {"model": model, "shift_key": "w1_mean", "insite_dice": float(sh["insite_mean"].mean())}),
            encoding="utf-8")
        out["gap_model"] = model
        out["caveat"] = f"only {len(sh)} folds: rank correlation has very low power"
    else:
        out["spearman_w1_vs_gap"] = "not run: no gap table (E1)"
    out["embedding_shift"] = "not run: needs trained encoders (btqc.eval.shift.frechet_distance is implemented)"
    return _write("e2_shift", out)


def e3_mitigations() -> Path:
    ctx = context()
    if ctx is None:
        return _not_run("e3_mitigations", NO_DATA)
    p = RESULTS / "cases.csv"
    if not p.exists():
        return _not_run("e3_mitigations", "no per-case table (run E1 first)")
    from btqc.eval.stats import bootstrap_ci, paired_wilcoxon

    df = pd.read_csv(p)
    df = df[(df.status == "ok") & (df.split == "heldout")]
    base = df[df.method == "baseline"].set_index(["fold", "case_id"])
    rows = []
    for m in sorted(set(df.method) - {"baseline"}):
        mm = df[df.method == m].set_index(["fold", "case_id"])
        j = base.join(mm, lsuffix="_b", rsuffix="_m", how="inner")
        for r in ("WT", "TC", "ET"):
            d = (j[f"dice_{r}_m"] - j[f"dice_{r}_b"]).to_numpy()
            rows.append({"method": m, "region": r, "n": len(j), **{f"diff_{k}": v for k, v in bootstrap_ci(d).items()},
                         "wilcoxon": paired_wilcoxon(j[f"dice_{r}_m"].to_numpy(), j[f"dice_{r}_b"].to_numpy())})
    if not rows:
        return _not_run("e3_mitigations", "only the baseline has predictions")
    from btqc.eval.stats import holm

    for r, padj in zip(rows, holm([r["wilcoxon"]["p"] for r in rows]), strict=True):
        r["wilcoxon"]["p_holm"] = padj
    return _write("e3_mitigations", {"status": "ok", "comparisons": rows,
                                     "H2": any(r["diff_lo"] > 0 for r in rows)})


def e4_calibration() -> Path:
    p = RESULTS / "eval_summary.json"
    if not p.exists():
        return _not_run("e4_calibration", NO_DATA if context() is None else "no evaluation summary (run E1)")
    s = json.loads(p.read_text())
    return _write("e4_calibration", {"status": "ok", "ece": s["ece"],
                                     "note": "estimators compared = methods with records (ensemble, TTA variants)"})


def e5_failure() -> Path:
    p = RESULTS / "eval_summary.json"
    if not p.exists():
        return _not_run("e5_failure", NO_DATA if context() is None else "no evaluation summary (run E1)")
    s = json.loads(p.read_text())
    f = [r for r in s["failure"] if r["score"] == "boundary_band"]
    h3 = {"auroc_ci_excludes_half": [r for r in f if r.get("lo") is not None and r["lo"] > 0.5],
          "retained_dice_gain": [r for r in s["risk_coverage"] if (r.get("gain_at_80") or 0) > 0]}
    return _write("e5_failure", {"status": "ok", "failure": s["failure"], "risk_coverage": s["risk_coverage"],
                                 "H3": {"n_folds_auroc_ok": len(h3["auroc_ci_excludes_half"]),
                                        "n_folds_gain_positive": len(h3["retained_dice_gain"]), "n_folds": len(f)}})


def e6_software() -> Path:
    """Test pass rate and coverage (synthetic fixtures), plus latency of the CPU parts."""
    t0 = time.time()
    cmd = [sys.executable, "-m", "pytest", "-q", "-m", "not ui and not slow", "--cov=btqc", "--cov-report=json:"
           + str(RESULTS / "coverage.json"), "-p", "no:cacheprovider"]
    proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True)
    tail = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else ""
    cov = None
    cj = RESULTS / "coverage.json"
    if cj.exists():
        cov = json.loads(cj.read_text())["totals"]["percent_covered"]
    perf = RESULTS / "perf.json"
    ui = RESULTS / "ui_tests.json"
    return _write("e6_software", {
        "status": "ok", "pytest_summary": tail, "returncode": proc.returncode, "coverage_percent": cov,
        "elapsed_s": round(time.time() - t0, 1),
        "performance": json.loads(perf.read_text()) if perf.exists() else "not run (tests/perf)",
        "ui": json.loads(ui.read_text()) if ui.exists() else "not run (tests/ui)",
        "latency_R8": "not run: needs a trained model and a GPU (target 60 s per case)",
    })


ALL = {"e1": e1_gap, "e2": e2_shift, "e3": e3_mitigations, "e4": e4_calibration, "e5": e5_failure, "e6": e6_software}

