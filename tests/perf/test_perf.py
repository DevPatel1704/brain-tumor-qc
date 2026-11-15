"""Performance measurements on a full-size (240x240x155) synthetic case, CPU only.

Records wall time and peak traced Python memory of the CPU stages to
results/perf.json and asserts loose budgets so regressions are noticed.
GPU inference latency (R8, 60 s per case) needs a trained model: not run here.
"""

import json
import time
import tracemalloc

import numpy as np
import pytest

from btqc.config import REPO_ROOT
from btqc.data.convert import ConvertOptions, convert_all
from btqc.data.discover import discover
from btqc.data.fixtures import make_case, write_case
from btqc.infer.stub import stub_record
from btqc.uncertainty.gate import decide

pytestmark = pytest.mark.slow
SHAPE = (240, 240, 155)


def _timed(fn):
    tracemalloc.start()
    t0 = time.perf_counter()
    out = fn()
    dt = time.perf_counter() - t0
    peak = tracemalloc.get_traced_memory()[1] / 2**20
    tracemalloc.stop()
    return out, dt, peak


def test_cpu_stage_latency_and_bundle_size(tmp_path):
    c = make_case("FeTS2022_99999", shape=SHAPE, seed=0)
    raw = tmp_path / "raw"
    write_case(c, raw)
    _, t_conv, m_conv = _timed(lambda: convert_all(discover(raw), ConvertOptions(out_root=tmp_path / "p", raw_root=raw),
                                                   workers=1))
    brain = c.images["flair"] != 0
    rec, t_unc, m_unc = _timed(lambda: stub_record(c.case_id, c.seg, brain, (1.0, 1.0, 1.0), 0.5, "f"))
    _, t_gate, _ = _timed(lambda: [decide(rec.meta["scores"]["boundary_band"], 0.25) for _ in range(10000)])
    vdir = tmp_path / "p" / "viewer" / c.case_id
    bundle_mb = sum(p.stat().st_size for p in vdir.glob("*.u8.gz")) / 2**20
    perf = {
        "shape": list(SHAPE), "convert_case_s": round(t_conv, 2), "convert_peak_traced_mb": round(m_conv, 1),
        "stub_members_uncertainty_scores_s": round(t_unc, 2), "uncertainty_peak_traced_mb": round(m_unc, 1),
        "gate_decisions_per_s": round(10000 / t_gate), "viewer_bundle_mb_all_sequences_plus_seg": round(bundle_mb, 2),
        "note": "synthetic case, CPU; GPU model latency (R8) not run",
    }
    out = REPO_ROOT / "results"
    out.mkdir(exist_ok=True)
    (out / "perf.json").write_text(json.dumps(perf, indent=1))
    assert t_conv < 120 and t_unc < 120 and bundle_mb < 40
    assert np.isfinite(rec.meta["scores"]["boundary_band"])
