from collections import Counter

import pytest
import yaml

from btqc.config import REPO_ROOT
from btqc.data.sitegroups import assign_groups, group_summary
from btqc.train.splits import check_folds, make_folds, to_nnunet_splits

RULES = yaml.safe_load((REPO_ROOT / "configs" / "sitegroups.yaml").read_text())["rules"]


def _fets_like():
    """Synthetic institution sizes shaped like FeTS 2022 (not the real table)."""
    sizes = {1: 511, 18: 382, 2: 6, 3: 15, 4: 47, 5: 33, 6: 3, 7: 3, 8: 4, 9: 35, 10: 4, 11: 5, 12: 8, 13: 15, 14: 5,
             15: 4, 16: 31, 17: 12, 19: 30, 20: 47, 21: 5, 22: 8, 23: 36}
    ci, k = {}, 0
    for inst, n in sizes.items():
        for _ in range(n):
            ci[f"FeTS2022_{k:05d}"] = inst
            k += 1
    return ci


def test_lgg_precedence_and_small_merge():
    ci = _fets_like()
    g = assign_groups(ci, RULES)
    inst_group = {ci[c]: g[c] for c in ci}
    assert inst_group[13] == "lgg_only"  # 15 cases but LGG wins
    assert inst_group[12] == "lgg_only"  # small but LGG wins
    assert inst_group[1] == "inst_1" and inst_group[18] == "inst_18"
    assert inst_group[6] == "small" and inst_group[17] == "small"
    assert inst_group[3] == "mid" and inst_group[4] == "mid"
    s = group_summary(ci, g)
    assert sum(v["n_cases"] for v in s.values()) == len(ci)
    assert set(s) == {"lgg_only", "inst_1", "inst_18", "small", "mid"}


def test_folds_no_overlap_no_leakage_and_fractions():
    ci = _fets_like()
    g = assign_groups(ci, RULES)
    folds = make_folds(ci, g, seed=1)
    assert check_folds(folds, g) == []
    for name, f in folds.items():
        rest = len(f["train"]) + len(f["val"]) + len(f["insite_test"])
        assert abs(len(f["val"]) / rest - 0.1) < 0.01
        assert abs(len(f["insite_test"]) / rest - 0.1) < 0.01
        # stratified: institution 1 appears in val of every fold that does not hold it out
        if name != "inst_1":
            assert Counter(ci[c] for c in f["val"])[1] == pytest.approx(51, abs=1)


def test_folds_deterministic():
    ci = _fets_like()
    g = assign_groups(ci, RULES)
    assert make_folds(ci, g, seed=7) == make_folds(ci, g, seed=7)
    assert make_folds(ci, g, seed=7) != make_folds(ci, g, seed=8)


def test_check_folds_detects_leak():
    ci = _fets_like()
    g = assign_groups(ci, RULES)
    folds = make_folds(ci, g)
    folds["inst_18"]["train"].append(folds["inst_18"]["heldout"][0])
    probs = check_folds(folds, g)
    assert any("overlap" in p for p in probs) and any("held-out-group" in p for p in probs)


def test_nnunet_splits_format():
    ci = _fets_like()
    g = assign_groups(ci, RULES)
    folds = make_folds(ci, g)
    order = sorted(folds)
    s = to_nnunet_splits(folds, order)
    assert len(s) == 5 and set(s[0]) == {"train", "val"}
    assert s[order.index("lgg_only")]["train"] == folds["lgg_only"]["train"]


def test_missing_institution_raises():
    with pytest.raises((ValueError, TypeError)):
        assign_groups({"a": None}, RULES)  # type: ignore[dict-item]
