"""Run nnU-Net v2 command-line entry points with the project's environment,
track runs in MLflow, and estimate durations before long jobs."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from btqc.config import REPO_ROOT
from btqc.train.nnunet_setup import nnunet_env


def nnunet_exe(name: str) -> str:
    """Path of an nnU-Net console script next to the running interpreter."""
    d = Path(sys.executable).parent
    for cand in (d / f"{name}.exe", d / name, d / "Scripts" / f"{name}.exe"):
        if cand.exists():
            return str(cand)
    found = shutil.which(name)
    if not found:
        raise FileNotFoundError(f"{name} not found; is nnunetv2 installed in this environment?")
    return found


def run_nnunet(args: list[str], extra_env: dict[str, str] | None = None, log: Path | None = None) -> int:
    env = dict(os.environ)
    env.update(nnunet_env(REPO_ROOT))
    # Windows: in-process augmentation for training (0 workers). The planner calls
    # torch.set_num_threads(nnUNet_n_proc_DA), so every other command needs >= 1.
    if os.name == "nt":
        env.setdefault("nnUNet_n_proc_DA", "0" if args[0] == "nnUNetv2_train" else "1")
    else:
        env.setdefault("nnUNet_n_proc_DA", "4")
    env["PYTHONUNBUFFERED"] = "1"  # stream nnU-Net progress into the log
    env["PYTHONPATH"] = str(REPO_ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    if extra_env:
        env.update(extra_env)
    cmd = [nnunet_exe(args[0]), *args[1:]]
    print("+", " ".join(cmd), flush=True)
    if log is None:
        return subprocess.call(cmd, env=env, cwd=REPO_ROOT)
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "w", encoding="utf-8") as fh:
        p = subprocess.Popen(cmd, env=env, cwd=REPO_ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                             encoding="utf-8", errors="replace")
        assert p.stdout is not None
        for line in p.stdout:
            fh.write(line)
            if any(k in line for k in ("Epoch", "train_loss", "val_loss", "Pseudo dice", "Error", "error")):
                print("  " + line.rstrip(), flush=True)
        return p.wait()


_LOSS = re.compile(r"train_loss\s+(-?\d+\.\d+)")
_VAL = re.compile(r"val_loss\s+(-?\d+\.\d+)")


def parse_losses(log_text: str) -> dict[str, list[float]]:
    return {"train_loss": [float(x) for x in _LOSS.findall(log_text)],
            "val_loss": [float(x) for x in _VAL.findall(log_text)]}


def estimate_hours(n_folds: int, n_members: int, n_methods: int, epochs: int, seconds_per_epoch: float) -> float:
    return n_folds * n_members * n_methods * epochs * seconds_per_epoch / 3600.0


def git_commit() -> str:
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def mlflow_log(run_name: str, params: dict[str, Any], metrics: dict[str, float], artifacts: list[Path] | None = None,
               experiment: str = "btqc-site-heldout", tracking_uri: str | None = None) -> str | None:
    """Log one run to MLflow (local file store by default). Returns the run id, or None if mlflow is missing."""
    try:
        import mlflow
    except ImportError:
        return None
    # MLflow >= 3 needs a database backend; a local SQLite file keeps runs out of git
    mlflow.set_tracking_uri(tracking_uri or "sqlite:///" + (REPO_ROOT / "mlflow.db").as_posix())
    mlflow.set_experiment(experiment)
    with mlflow.start_run(run_name=run_name) as run:
        mlflow.log_params({k: (str(v)[:500]) for k, v in params.items()})
        mlflow.set_tag("git_commit", git_commit())
        for k, v in metrics.items():
            if v == v:  # skip NaN
                mlflow.log_metric(k, float(v))
        for a in artifacts or []:
            if a.exists():
                mlflow.log_artifact(str(a))
        return str(run.info.run_id)
