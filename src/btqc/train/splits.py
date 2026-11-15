"""Site-held-out folds and nnU-Net ``splits_final.json``.

Fold g holds out every case of site group g (``heldout``). The remaining
cases are split, stratified by institution, into ``train`` (80 %), ``val``
(10 %, checkpoint selection and review-limit selection) and ``insite_test``
(10 %, the in-site reference for the generalization gap).

Stratification is systematic: within each institution cases are shuffled
with the fold seed, institutions are concatenated, and position i receives
slot ``PATTERN[i % 10]``. Every institution therefore contributes in
proportion, including institutions with only a few cases.

Leakage rule: a model used to predict group g is trained only on the
``train`` list of fold g, which never contains a case of group g.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np

# 8 train, 1 val, 1 in-site test per 10 cases
PATTERN = ("train", "train", "train", "val", "train", "train", "train", "train", "insite_test", "train")


def _pattern(fractions: Mapping[str, float]) -> tuple[str, ...]:
    if dict(fractions) == {"train": 0.8, "val": 0.1, "insite_test": 0.1}:
        return PATTERN
    slots: list[str] = []
    for k, f in fractions.items():
        slots += [k] * round(f * 20)
    if len(slots) != 20:
        raise ValueError(f"fractions must be multiples of 0.05 and sum to 1: {fractions}")
    rng = np.random.default_rng(0)
    return tuple(rng.permutation(slots))


def make_folds(case_institution: Mapping[str, int], case_group: Mapping[str, str], seed: int = 12345,
               fractions: Mapping[str, float] | None = None) -> dict[str, dict[str, list[str]]]:
    fractions = fractions or {"train": 0.8, "val": 0.1, "insite_test": 0.1}
    pattern = _pattern(fractions)
    groups = sorted(set(case_group.values()))
    folds: dict[str, dict[str, list[str]]] = {}
    for gi, g in enumerate(groups):
        rng = np.random.default_rng(seed + gi)
        held = sorted(c for c, gg in case_group.items() if gg == g)
        rest = [c for c in case_group if case_group[c] != g]
        by_inst: dict[int, list[str]] = {}
        for c in sorted(rest):
            by_inst.setdefault(int(case_institution[c]), []).append(c)
        ordered: list[str] = []
        for inst in sorted(by_inst):
            cs = by_inst[inst]
            ordered += [cs[i] for i in rng.permutation(len(cs))]
        fold: dict[str, list[str]] = {"train": [], "val": [], "insite_test": [], "heldout": held}
        for i, c in enumerate(ordered):
            fold[pattern[i % len(pattern)]].append(c)
        for k in ("train", "val", "insite_test"):
            fold[k].sort()
        folds[g] = fold
    return folds


def check_folds(folds: Mapping[str, Mapping[str, list[str]]], case_group: Mapping[str, str]) -> list[str]:
    """Return a list of violations (empty if the folds are valid)."""
    problems = []
    all_cases = set(case_group)
    for g, f in folds.items():
        parts = {k: set(v) for k, v in f.items()}
        keys = list(parts)
        for i, a in enumerate(keys):
            for b in keys[i + 1:]:
                if parts[a] & parts[b]:
                    problems.append(f"fold {g}: {a} and {b} overlap ({len(parts[a] & parts[b])} cases)")
        union = set().union(*parts.values())
        if union != all_cases:
            problems.append(f"fold {g}: {len(all_cases - union)} cases unassigned")
        for k in ("train", "val", "insite_test"):
            leak = [c for c in parts[k] if case_group[c] == g]
            if leak:
                problems.append(f"fold {g}: {len(leak)} held-out-group cases in {k}")
        if any(case_group[c] != g for c in parts["heldout"]):
            problems.append(f"fold {g}: heldout contains other groups")
    return problems


def to_nnunet_splits(folds: Mapping[str, Mapping[str, list[str]]], order: list[str]) -> list[dict[str, list[str]]]:
    """nnU-Net v2 ``splits_final.json``: a list with one {"train", "val"} dict per fold.
    nnU-Net fold i corresponds to site group ``order[i]``."""
    return [{"train": list(folds[g]["train"]), "val": list(folds[g]["val"])} for g in order]


def save_folds(folds: Mapping[str, Any], order: list[str], out_dir: Path, meta: dict[str, Any]) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    p1 = out_dir / "folds.json"
    p1.write_text(json.dumps({"meta": meta, "fold_order": order, "folds": folds}, indent=1), encoding="utf-8")
    p2 = out_dir / "splits_final.json"
    p2.write_text(json.dumps(to_nnunet_splits(folds, order), indent=1), encoding="utf-8")
    return p1, p2
