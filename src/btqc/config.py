"""Load YAML configs. Relative paths are resolved against the repository root."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]


def load_config(name_or_path: str | os.PathLike[str]) -> dict[str, Any]:
    p = Path(name_or_path)
    if not p.suffix:
        p = REPO_ROOT / "configs" / f"{p}.yaml"
    elif not p.is_absolute() and not p.exists():
        p = REPO_ROOT / p
    with open(p, encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    cfg["_config_path"] = str(p)
    return cfg


def resolve(path: str | os.PathLike[str]) -> Path:
    """Resolve a config path: environment variables expanded, relative to repo root."""
    p = Path(os.path.expandvars(str(path)))
    return p if p.is_absolute() else (REPO_ROOT / p).resolve()


def raw_root(cfg: dict[str, Any]) -> Path:
    """Raw data root; the BTQC_RAW_ROOT environment variable overrides the config."""
    return resolve(os.environ.get("BTQC_RAW_ROOT") or cfg["raw_root"])
