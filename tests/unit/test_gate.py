"""Requirement R4: the flag depends only on the score and the review limit."""

import ast
import inspect
import math
from pathlib import Path

import numpy as np
import pytest

from btqc.uncertainty import gate
from btqc.uncertainty.gate import LOOKS_RELIABLE, NEEDS_REVIEW, decide, flag


def test_exact_threshold_not_flagged():
    assert flag(0.25, 0.25) is False
    assert flag(np.nextafter(0.25, 1), 0.25) is True
    assert flag(np.nextafter(0.25, 0), 0.25) is False


@pytest.mark.parametrize("s", [float("nan"), None, np.nan, np.float32("nan"), "abc"])
def test_nan_or_missing_score_is_flagged(s):
    assert flag(s, 0.3) is True
    assert decide(s, 0.3).label == NEEDS_REVIEW


def test_empty_prediction_score_flagged():
    """An empty prediction has an empty boundary band, so its score is NaN -> flagged."""
    from btqc.uncertainty.case_score import score_boundary_band

    s = score_boundary_band(np.zeros((8, 8, 8)), np.zeros((8, 8, 8), dtype=bool))
    assert math.isnan(s)
    assert flag(s, 1.0) is True


def test_numpy_scalars():
    assert flag(np.float32(0.1), 0.2) is False
    assert flag(np.float64(0.3), np.float32(0.2)) is True


def test_invalid_limit_raises():
    with pytest.raises(ValueError):
        flag(0.1, float("nan"))
    with pytest.raises(ValueError):
        flag(0.1, None)  # type: ignore[arg-type]


def test_decision_labels_and_reason():
    d = decide(0.4, 0.3)
    assert d.flag and d.label == NEEDS_REVIEW and "above" in d.reason
    d = decide(0.2, 0.3)
    assert not d.flag and d.label == LOOKS_RELIABLE


def test_monotone_in_score():
    lim = 0.3
    scores = np.linspace(0, 1, 101)
    flags = [flag(s, lim) for s in scores]
    assert flags == sorted(flags)


def test_signature_has_only_score_and_limit():
    assert list(inspect.signature(flag).parameters) == ["score", "review_limit"]
    assert list(inspect.signature(decide).parameters) == ["score", "review_limit"]


def test_gate_module_imports_only_stdlib():
    """Code-review aid for R4: the gate cannot reach the network, an LLM or metadata."""
    tree = ast.parse(Path(gate.__file__).read_text(encoding="utf-8"))
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            mods.add((node.module or "").split(".")[0])
    assert mods <= {"__future__", "math", "dataclasses"}
