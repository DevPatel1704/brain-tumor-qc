"""Cross-platform task runner. Every Makefile target calls this file, so
``make <target>`` and ``python scripts/tasks.py <target>`` are identical
(useful on Windows, where make is usually missing).

    python scripts/tasks.py --list
    python scripts/tasks.py test
    python scripts/tasks.py convert -- --max-cases 5
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def run(*args: str, env: dict[str, str] | None = None) -> int:
    print("+", " ".join(args), flush=True)
    e = dict(os.environ)
    e.setdefault("PYTHONPATH", str(ROOT / "src"))
    e.update(_nnunet_env())
    if env:
        e.update(env)
    return subprocess.call(list(args), cwd=ROOT, env=e)


def _nnunet_env() -> dict[str, str]:
    d = ROOT / "data"
    return {
        "nnUNet_raw": os.environ.get("nnUNet_raw", str(d / "nnUNet_raw")),
        "nnUNet_preprocessed": os.environ.get("nnUNet_preprocessed", str(d / "nnUNet_preprocessed")),
        "nnUNet_results": os.environ.get("nnUNet_results", str(d / "nnUNet_results")),
    }


TASKS: dict[str, tuple[str, list[list[str]]]] = {
    "data-report": ("Phase 0: inspect raw data, write docs/data_report.md + data/manifest.csv",
                    [[PY, "scripts/data_report.py"]]),
    "convert": ("Phase 1: canonical NIfTI, viewer bundles, PNG montages", [[PY, "scripts/convert.py"]]),
    "nnunet-prep": ("Phase 1/3: nnU-Net raw dataset, site groups, folds, splits_final.json",
                    [[PY, "scripts/nnunet_prep.py"]]),
    "sitegroups": ("Phase 3: compute site groups and folds from the manifest", [[PY, "scripts/make_splits.py"]]),
    "train-smoke": ("Phase 3 gate G3: tiny nnU-Net training on synthetic fixtures (CPU ok)",
                    [[PY, "scripts/train_smoke.py"]]),
    "train-loso": ("Phase 3: site-held-out training (GPU; prints an estimate first)",
                   [[PY, "scripts/train_loso.py"]]),
    "infer": ("Phase 5: ensemble + TTA inference, writes prediction records", [[PY, "scripts/infer.py"]]),
    "example-predictions": ("Rule-based EXAMPLE predictions for the dashboard (not a model)",
                            [[PY, "scripts/example_predictions.py"]]),
    "uncertainty": ("Phase 5: calibration, failure detection, risk-coverage", [[PY, "scripts/e4_calibration.py"],
                                                                               [PY, "scripts/e5_failure.py"]]),
    "eval": ("Phase 6: experiments E1-E6", [[PY, "scripts/run_experiments.py"]]),
    "site-risk": ("Phase 7: shift metrics for a batch of unlabeled scans", [[PY, "scripts/site_risk.py"]]),
    "app": ("Phase 7: run the dashboard at http://127.0.0.1:8000",
            [[PY, "-m", "uvicorn", "btqc.serve.api:create_app", "--factory", "--host", "127.0.0.1", "--port", "8000"]]),
    "export-demo": ("Phase 7: single-file HTML demo", [[PY, "scripts/export_demo.py"]]),
    "fixtures": ("Write synthetic fixtures to data/fixtures", [[PY, "-m", "btqc.data.fixtures", "--out",
                                                               "data/fixtures/raw"]]),
    "lint": ("ruff + mypy", [[PY, "-m", "ruff", "check", "src", "tests", "scripts"], [PY, "-m", "mypy"]]),
    "test": ("unit + integration + metamorphic tests with coverage (synthetic fixtures only)",
             [[PY, "-m", "pytest", "-m", "not ui and not realdata and not slow", "--cov=btqc",
               "--cov-report=term-missing:skip-covered", "--cov-report=xml"]]),
    "test-ui": ("browser tests (Playwright, headless Chromium + SwiftShader)", [[PY, "-m", "pytest", "tests/ui"]]),
    "test-all": ("every test including slow and real-data tests", [[PY, "-m", "pytest"]]),
    "docs": ("model card and IEEE-style report from results/", [[PY, "scripts/build_docs.py"],
                                                                  [PY, "scripts/build_report.py"]]),
}


def main(argv: list[str]) -> int:
    if not argv or argv[0] in ("-h", "--help", "--list"):
        for k, (d, _) in TASKS.items():
            print(f"  {k:20s} {d}")
        return 0
    name, extra = argv[0], argv[1:]
    if extra and extra[0] == "--":
        extra = extra[1:]
    if name not in TASKS:
        print(f"unknown task {name!r}; use --list", file=sys.stderr)
        return 2
    for i, cmd in enumerate(TASKS[name][1]):
        rc = run(*cmd, *(extra if i == len(TASKS[name][1]) - 1 else []))
        if rc:
            return rc
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
