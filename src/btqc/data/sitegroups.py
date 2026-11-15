"""Assign institutions to site groups from rules in configs/sitegroups.yaml.

Membership is always computed from data (case -> institution); nothing about
which institution is large or small is hard-coded beyond the rule thresholds.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from typing import Any


def assign_groups(case_institution: Mapping[str, int], rules: list[dict[str, Any]]) -> dict[str, str]:
    """Return case_id -> group name. Raises if a case has no institution or no rule matches."""
    sizes = Counter(case_institution.values())
    inst_group: dict[int, str] = {}
    for inst, n in sizes.items():
        for r in rules:
            if "institutions" in r and inst in r["institutions"]:
                inst_group[inst] = r["name"]
                break
            if "max_cases" in r and n <= r["max_cases"]:
                inst_group[inst] = r["name"]
                break
            if r.get("otherwise"):
                inst_group[inst] = r["name"]
                break
        else:
            raise ValueError(f"no site-group rule matches institution {inst}")
    out = {}
    for case, inst in case_institution.items():
        if inst is None:
            raise ValueError(f"case {case} has no institution")
        out[case] = inst_group[int(inst)]
    return out


def group_summary(case_institution: Mapping[str, int], case_group: Mapping[str, str]) -> dict[str, Any]:
    groups: dict[str, dict[str, Any]] = {}
    for case, g in case_group.items():
        d = groups.setdefault(g, {"n_cases": 0, "institutions": Counter()})
        d["n_cases"] += 1
        d["institutions"][int(case_institution[case])] += 1
    return {
        g: {"n_cases": d["n_cases"], "n_institutions": len(d["institutions"]),
            "institutions": dict(sorted(d["institutions"].items()))}
        for g, d in sorted(groups.items())
    }
