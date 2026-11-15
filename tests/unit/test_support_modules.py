"""Tests for supporting modules: manifest, sysinfo tiers, ensemble leakage rule,
standardization, runner helpers, tables, figures and experiment outputs."""

import json

import numpy as np
import pandas as pd
import pytest

from btqc.data.discover import discover
from btqc.data.manifest import build_case_table, build_inventory, load_institution_table
from btqc.data.standardize import standardize
from btqc.infer.ensemble import check_ensemble, group_of_index, member_indices
from btqc.sysinfo import choose_tier
from btqc.train.runner import estimate_hours, parse_losses


def test_manifest_on_fixtures(synthetic_root):
    disc = discover(synthetic_root)
    files = build_inventory(disc, workers=1)
    assert len(files) == 12 * 5 and set(files.sequence) == {"t1", "t1ce", "t2", "flair", "seg"}
    assert (files.axcodes == "LPS").all() and files.sha256.str.len().eq(64).all()
    inst = load_institution_table(synthetic_root / "partitioning_synthetic.csv")
    cases = build_case_table(files, inst)
    assert len(cases) == 12 and cases.grid_ok.all() and (cases.problems == "").all()
    assert cases.has_seg.all() and cases.institution.notna().all()
    seg = files[files.sequence == "seg"].iloc[0]
    assert set(json.loads(seg.unique_values)) <= {"0", "1", "2", "4"}


def test_institution_table_requires_columns(tmp_path):
    p = tmp_path / "t.csv"
    p.write_text("a,b\n1,2\n")
    with pytest.raises(ValueError):
        load_institution_table(p)


@pytest.mark.parametrize("gpus,tier", [([], 0), ([{"name": "x", "memory_gb": 4.0}], 0),
                                       ([{"name": "x", "memory_gb": 12.0}], 1),
                                       ([{"name": "x", "memory_gb": 24.0}], 2),
                                       ([{"name": "a", "memory_gb": 11.0}, {"name": "b", "memory_gb": 11.0}], 2)])
def test_choose_tier(gpus, tier):
    assert choose_tier(gpus)[0] == tier


def test_ensemble_membership_and_leakage():
    order = ["inst_1", "inst_18", "lgg_only", "mid", "small"]
    assert member_indices(order, "lgg_only", 3) == [6, 7, 8]
    assert group_of_index(order, 7, 3) == "lgg_only"
    check_ensemble(order, "lgg_only", [6, 7, 8], 3)
    with pytest.raises(ValueError):
        check_ensemble(order, "lgg_only", [6, 7, 9], 3)


@pytest.mark.parametrize("method", ["pct", "mode"])
def test_standardize_keeps_background_and_is_scale_invariant(method):
    rng = np.random.default_rng(0)
    v = np.zeros((10, 10, 10), np.float32)
    v[2:8, 2:8, 2:8] = rng.normal(500, 60, (6, 6, 6))
    a, b = standardize(v, method), standardize(v * 3, method)
    assert (a[v == 0] == 0).all() and (a[v != 0] != 0).all()
    np.testing.assert_allclose(a, b, atol=1e-4)
    with pytest.raises(ValueError):
        standardize(v, "nope")


def test_runner_helpers():
    log = "2026: train_loss 0.75\n2026: val_loss 0.6\n2026: train_loss 0.5\n"
    assert parse_losses(log) == {"train_loss": [0.75, 0.5], "val_loss": [0.6]}
    assert estimate_hours(5, 3, 4, 100, 240) == pytest.approx(400.0)


def _summary():
    from btqc.config import REPO_ROOT

    p = REPO_ROOT / "results" / "eval_summary_synthetic.json"
    if not p.exists():
        pytest.skip("run scripts/synthetic_demo.py first")
    return json.loads(p.read_text())


def test_tables_and_figures_from_summary(tmp_path):
    from btqc.eval.figures import all_figures
    from btqc.eval.tables import to_latex, to_markdown, write_tables

    s = _summary()
    t = write_tables(s, tmp_path / "tables")
    assert {p.name for p in t} >= {"gap_dice.md", "gap_dice.tex", "failure.md", "risk_coverage.tex"}
    assert "NOT A RESULT" in (tmp_path / "tables" / "gap_dice.tex").read_text()
    f = all_figures(s, tmp_path / "fig")
    assert any(p.suffix == ".pdf" for p in f) and all(p.stat().st_size > 1000 for p in f)
    df = pd.DataFrame({"a": ["x_y"], "b": [0.12345], "c": [float("nan")]})
    assert "0.123" in to_markdown(df) and r"x\_y" in to_latex(df, "cap", "tab:x") and "–" in to_markdown(df)


def test_experiment_outputs_and_not_run(tmp_path, monkeypatch):
    from btqc.eval import runs
    from btqc.eval.experiments import write_outputs

    s = _summary()
    cases = pd.DataFrame([{"method": "m", "fold": "f", "split": "heldout", "case_id": "c", "status": "ok"}])
    out = write_outputs(s, cases, tmp_path, tag="t")
    assert (tmp_path / "eval_summary_t.json").exists() and len(out) > 5
    monkeypatch.setattr(runs, "RESULTS", tmp_path / "r")
    monkeypatch.setattr(runs, "context", lambda: None)
    for name in ("e1", "e2", "e3", "e4", "e5"):
        p = runs.ALL[name]()
        assert json.loads(p.read_text())["status"] == "not run"
