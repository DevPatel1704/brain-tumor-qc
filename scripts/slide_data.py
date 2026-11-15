"""Export the numbers the presentation needs to results/slide_data.json (same sources as the report).

    python scripts/slide_data.py
"""

from __future__ import annotations

import importlib.util
import json
import math
import re
from typing import Any

from btqc.config import REPO_ROOT

R = REPO_ROOT / "results"


def _clean(x: Any) -> Any:
    if isinstance(x, float):
        return None if math.isnan(x) else x
    if isinstance(x, dict):
        return {str(k): _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    return x


def main() -> int:
    spec = importlib.util.spec_from_file_location("build_report", REPO_ROOT / "scripts" / "build_report.py")
    assert spec and spec.loader
    br = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(br)
    rr = br.real_results()
    if rr is None:
        print("no model results; nothing exported")
        return 2
    e6 = br.j(R / "e6_software.json") or {}
    ui = br.junit(R / "ui_junit.xml")
    out = {
        "epochs": rr["tcfg"]["epochs"],
        "plans": rr["tcfg"]["plans"],
        "epoch_min": rr["epoch_s"] / 60 if rr.get("epoch_s") else None,
        "n_epochs_run": rr.get("n_epochs_run"),
        "nnunet_val": rr["nnunet_val"],
        "infer_s": rr.get("infer_s"),
        "n_split": rr["n_split"],
        "n_total_split": rr["n_total_split"],
        "gaps": {f"{r}_{m}": g for (r, m), g in rr["gaps"].items()},
        "fail": rr["fail"],
        "rc": rr["rc"],
        "inst": rr["inst"].to_dict("records"),
        "emb": rr.get("emb"),
        "w1": {x["fold"]: x["w1_mean"] for x in (rr.get("e2") or {}).get("shift", [])},
        "e3": rr.get("e3"),
        "e4": rr.get("e4tta"),
        "r7r8": rr.get("r7r8"),
        "tta_gaps": [g for g in rr["all_gaps"] if g["method"] == "tta_entropy" and g["metric"] == "dice"],
        "tests_line": re.sub(r" in [0-9.]+s.*$", "", e6.get("pytest_summary", "")) if e6 else None,
        "coverage": e6.get("coverage_percent"),
        "ui_tests": ui,
    }
    (R / "slide_data.json").write_text(json.dumps(_clean(out), indent=1, default=float), encoding="utf-8")
    print("wrote results/slide_data.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
