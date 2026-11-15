"""Shared driver for the experiment scripts (E1-E6).

``evaluate_methods`` runs the harness over every method and fold that has
prediction records and returns the per-case table plus calibration counts.
``write_outputs`` writes results/*.csv, the JSON summary, figures (PNG and
PDF) and Markdown/LaTeX tables.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from btqc.eval.loso import CalibrationSet, evaluate_fold


def evaluate_methods(pred_root: Path, canonical_dir: Path, folds: dict[str, dict[str, list[str]]],
                     case_institution: dict[str, Any], convention: str, methods: list[str] | None = None,
                     max_cases: int | None = None) -> tuple[pd.DataFrame, dict[tuple[str, str], CalibrationSet]]:
    rows, calib = [], {}
    if methods is None:
        methods = sorted(p.name for p in pred_root.iterdir() if p.is_dir()) if pred_root.exists() else []
    for m in methods:
        for g, f in folds.items():
            d = pred_root / m / g
            if not d.exists():
                continue
            cs = CalibrationSet()
            rows.append(evaluate_fold(m, g, f, d, canonical_dir, case_institution, convention, calib=cs,
                                      max_cases=max_cases))
            calib[(m, g)] = cs
    return (pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()), calib


def write_outputs(summary: dict[str, Any], cases: pd.DataFrame, out_dir: Path, tag: str = "") -> list[Path]:
    from btqc.eval.figures import all_figures
    from btqc.eval.tables import write_tables

    out_dir.mkdir(parents=True, exist_ok=True)
    sfx = f"_{tag}" if tag else ""
    written = []
    p = out_dir / f"cases{sfx}.csv"
    cases.to_csv(p, index=False)
    written.append(p)
    for key in ("gaps", "failure", "ece"):
        q = out_dir / f"{key}{sfx}.csv"
        pd.DataFrame(summary[key]).to_csv(q, index=False)
        written.append(q)
    q = out_dir / f"eval_summary{sfx}.json"
    q.write_text(json.dumps(summary, indent=1), encoding="utf-8")
    written.append(q)
    written += all_figures(summary, out_dir / f"figures{sfx}")
    written += write_tables(summary, out_dir / (f"tables{sfx}_test_data" if tag == "synthetic" else f"tables{sfx}"))
    return written
