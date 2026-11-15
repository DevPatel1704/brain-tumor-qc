"""Generate the model card (results/model_card.json for the dashboard and
docs/model_card.md) from files that exist in results/. Anything missing is
written as "not run".

    python scripts/build_docs.py
"""

from __future__ import annotations

import json
from typing import Any

from btqc import DISCLAIMER
from btqc.config import REPO_ROOT, load_config


def _load(name: str) -> dict[str, Any] | None:
    p = REPO_ROOT / "results" / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def main() -> int:
    s0 = json.loads((REPO_ROOT / "data" / "phase0_summary.json").read_text()) if (
        REPO_ROOT / "data" / "phase0_summary.json").exists() else {}
    ucfg, tcfg = load_config("uncertainty"), load_config("train")
    ev = _load("eval_summary.json")
    smoke = _load("smoke_G3.json")
    perf = _load("perf.json")
    results_body: Any
    trained = bool(ev and ev.get("source") == "model")
    fail = _load("e5_failure.json")
    if trained:
        assert ev is not None
        results_body = [f"{g['method']} / {g['fold']} / {g['region']}: in-site Dice {g['insite_mean']:.3f} "
                        f"(n = {g['n_insite']}), held-out Dice {g['heldout_mean']:.3f} (n = {g['n_heldout']}), "
                        f"gap {g['gap']:.3f} [95% CI {g['gap_lo']:.3f}, {g['gap_hi']:.3f}]"
                        for g in ev["gaps"] if g["metric"] == "dice" and g.get("gap") is not None]
        for f in (fail or {}).get("failure", []):
            if f.get("score") == "boundary_band":
                results_body.append(
                    f"{f['method']} / {f['fold']}: failure detection (held-out) AUROC {f['auroc']:.2f} "
                    f"[{f['lo']:.2f}, {f['hi']:.2f}], {f['n_failed']} of {f['n']} cases failed; review limit "
                    f"{f['review_limit']:.3f} flags {f['flagged_frac']:.0%}; failure rate flagged "
                    f"{f['fail_rate_flagged']:.0%} vs unflagged {f['fail_rate_unflagged']:.0%}")
        results_body.append("Pilot result: seeded random test samples (docs/deviations.md D15-D17); "
                            "confidence intervals are wide.")
    else:
        results_body = ("Not run. No model has been trained on real data: the labeled FeTS 2022 training data and "
                        "the institution partitioning were not available (data situation C), and the machine has no "
                        "usable GPU (compute tier 0). No accuracy, calibration or failure-detection number exists.")
    sections = [
        {"title": "Intended use", "body": [
            "Research prototype to study accuracy loss at unseen hospitals and uncertainty-based review flags.",
            "Not a medical device, not for diagnosis or treatment decisions. The flag is advisory.",
            "Does not estimate tumor grade or stage."]},
        {"title": "Model", "body": {
            "Base": "nnU-Net v2 (2.8.1), region-based (WT, TC, ET), configuration " + tcfg["configuration"],
            "Training budget": f"{tcfg['epochs']} epochs, seed {tcfg['seed']} + fold index, "
                               f"{tcfg['n_members']} seed replicates per fold",
            "Uncertainty": "binary entropy of the member-mean sigmoid; members = seed replicates x flip TTA",
            "Case score": f"mean uncertainty in a {ucfg['case_score']['band_width_voxels']}-voxel band around the "
                          "predicted whole tumor",
            "Trust gate": "flag = score > review limit (NaN -> flag); limit chosen on in-site validation by rule "
                          f"{ucfg['gate']['review_limit_rule']}",
            "Failure definition": f"WT or ET Dice < {ucfg['failure']['tau']} (fixed before held-out evaluation)",
            "Plans": tcfg["plans"],
            "Trained": ("yes: baseline only, site-held-out fold(s) listed under Per-group results "
                        "(docs/deviations.md D15-D17)") if trained else "no (no labeled data available)"}},
        {"title": "Data", "body": {
            "Training data": "FeTS 2022: 1,251 labeled cases from 23 institutions, partitioning_1.csv for sites",
            "Unlabeled": "219 FeTS 2022 validation cases, used for the interface (EXAMPLE outlines unless predicted)",
            "Data situation": s0.get("situation", "?"),
            "Site labels": "FeTS 2022 partitioning CSV (institution per case)"}} if trained else {
            "title": "Data", "body": {
            "Expected training data": "FeTS 2022: 1,251 labeled cases from 23 institutions (not available here)",
            "Available": f"{s0.get('n_cases', '?')} unlabeled FeTS 2022 validation cases "
                         f"({s0.get('n_nifti', '?')} NIfTI files), used only for the interface and EXAMPLE outlines",
            "Data situation": s0.get("situation", "?"),
            "Site labels": "none available; none invented"}},
        {"title": "Per-group results", "body": results_body},
        {"title": "Software checks", "body": {
            "Smoke test (G3, synthetic)": json.dumps(smoke["gate_G3"]) if smoke else "not run",
            "CPU performance (synthetic 240x240x155)": json.dumps(perf) if perf else "not run",
            "GPU latency (R8)": "not run"}},
        {"title": "Limitations", "body": [
            ("Laptop pilot: 10 epochs, one held-out site group, seeded random test samples; other methods and folds "
             "not run." if trained else
             "No real accuracy has been measured; every outline shown on real scans is a rule-based EXAMPLE."),
            "Site is only a proxy for scanner and protocol; grade and site are confounded for the LGG-only group.",
            "Five site groups give very low power for shift-versus-gap correlations.",
            "Entropy-based uncertainty can be confidently wrong under strong shift; AUROC must be checked per site.",
            "nnU-Net training is seeded but not bit-exact."]},
        {"title": "Disclaimer", "body": DISCLAIMER},
    ]
    card = {"status": "ok", "sections": sections}
    (REPO_ROOT / "results").mkdir(exist_ok=True)
    (REPO_ROOT / "results" / "model_card.json").write_text(json.dumps(card, indent=1), encoding="utf-8")
    md = ["# Model card", "", f"> {DISCLAIMER}", "", "Generated by `scripts/build_docs.py` from `results/`.", ""]
    for s in sections:
        md += [f"## {s['title']}", ""]
        b = s["body"]
        if isinstance(b, list):
            md += [f"- {x}" for x in b]
        elif isinstance(b, dict):
            md += ["| Item | Value |", "|---|---|"] + [f"| {k} | {v} |" for k, v in b.items()]
        else:
            md.append(str(b))
        md.append("")
    (REPO_ROOT / "docs" / "model_card.md").write_text("\n".join(md), encoding="utf-8")
    print("wrote results/model_card.json and docs/model_card.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
