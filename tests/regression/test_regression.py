"""Regression: fixed seeds, stored baseline metrics, tolerance checks (R7).

The baseline in baseline.json was produced by this test's own pipeline on the
synthetic fixtures (stub predictor, seed 0). Regenerate deliberately with
``BTQC_UPDATE_BASELINE=1 pytest tests/regression`` and commit the change.
"""

import json
import os
from pathlib import Path

import numpy as np
import pytest

from btqc.data.fixtures import make_case
from btqc.data.labels import regions
from btqc.eval.metrics import region_metrics
from btqc.infer.stub import stub_record

BASELINE = Path(__file__).with_name("baseline.json")
TOL = 1e-6


def _metrics() -> dict:
    out = {}
    for seed, diff in ((0, 0.2), (1, 0.6)):
        c = make_case(f"r{seed}", shape=(40, 40, 30), seed=seed)
        brain = c.images["flair"] != 0
        rec = stub_record(c.case_id, c.seg, brain, (1.0, 1.0, 1.0), diff, "f", seed=seed)
        m = region_metrics(regions(c.seg, "brats_124"), regions(rec.seg, "brats_124"), (1.0, 1.0, 1.0))
        out[c.case_id] = {k: round(float(v), 6) for k, v in m.items() if k.startswith(("dice", "hd95"))}
        out[c.case_id]["score_boundary_band"] = round(float(rec.meta["scores"]["boundary_band"]), 6)
    return out


def test_metrics_match_stored_baseline():
    got = _metrics()
    if os.environ.get("BTQC_UPDATE_BASELINE") or not BASELINE.exists():
        BASELINE.write_text(json.dumps(got, indent=1, sort_keys=True))
        pytest.skip("baseline written; commit tests/regression/baseline.json")
    want = json.loads(BASELINE.read_text())
    assert set(got) == set(want)
    for cid in want:
        for k, v in want[cid].items():
            assert got[cid][k] == pytest.approx(v, abs=TOL), (cid, k)


def test_rerun_identical():
    assert _metrics() == _metrics()
    assert np.isfinite([v for c in _metrics().values() for v in c.values()]).all()
