import numpy as np
import pytest

from btqc.uncertainty.calibration import ReliabilityAccumulator, calibration_mask, ece
from btqc.uncertainty.case_score import all_scores, boundary_band, score_boundary_band
from btqc.uncertainty.entropy import (
    binary_entropy,
    categorical_entropy,
    mutual_information,
    predictive_entropy,
    to_uint8,
    voxel_uncertainty,
)
from btqc.uncertainty.failure_detection import (
    auroc,
    bootstrap_auroc,
    dice_at_coverage,
    failure_labels,
    risk_coverage,
    select_review_limit,
)


def test_binary_entropy_range():
    assert binary_entropy(np.array(0.5)) == pytest.approx(1.0)
    assert binary_entropy(np.array([0.0, 1.0])) == pytest.approx([0, 0], abs=1e-5)
    p = np.linspace(0, 1, 101)
    h = binary_entropy(p)
    assert h.min() >= 0 and h.max() <= 1 + 1e-6
    np.testing.assert_allclose(h, h[::-1], atol=1e-5)


def test_categorical_entropy_normalized():
    p = np.full((4, 3), 0.25)
    np.testing.assert_allclose(categorical_entropy(p, axis=0), 1.0, rtol=1e-5)


def test_ensemble_entropy_and_mutual_information():
    agree = np.stack([np.full((3, 4), 0.9)] * 3)
    disagree = np.stack([np.full((3, 4), 0.99), np.full((3, 4), 0.01), np.full((3, 4), 0.99)])
    assert mutual_information(agree).max() == pytest.approx(0, abs=1e-5)
    assert mutual_information(disagree).min() > 0.5
    assert predictive_entropy(disagree).shape == (3, 4)


def test_voxel_uncertainty_and_uint8():
    h = np.stack([np.zeros(5), np.ones(5), np.full(5, 0.5)])
    np.testing.assert_allclose(voxel_uncertainty(h, "mean"), 0.5)
    np.testing.assert_allclose(voxel_uncertainty(h, "max"), 1.0)
    assert to_uint8(np.array([0.0, 1.0, 2.0])).tolist() == [0, 255, 255]
    with pytest.raises(ValueError):
        voxel_uncertainty(h, "nope")


def test_boundary_band_contains_boundary_not_core():
    wt = np.zeros((30, 30, 30), dtype=bool)
    wt[5:25, 5:25, 5:25] = True
    band = boundary_band(wt, 2)
    assert band[5, 15, 15] and band[4, 15, 15] and band[3, 15, 15]
    assert not band[15, 15, 15]
    assert not band[1, 15, 15]


def test_case_score_reflects_boundary_uncertainty():
    wt = np.zeros((20, 20, 20), dtype=bool)
    wt[5:15, 5:15, 5:15] = True
    u = np.zeros(wt.shape)
    assert score_boundary_band(u, wt) == 0.0
    u[boundary_band(wt, 3)] = 0.8
    s = all_scores(u, wt, 3, mi=u / 2)
    assert s["boundary_band"] == pytest.approx(0.8)
    assert s["band_disagreement"] == pytest.approx(0.4)
    assert 0 < s["wt_mean"] < 0.8


def test_ece_perfect_and_miscalibrated():
    rng = np.random.default_rng(0)
    p = rng.random(200_000)
    y = rng.random(200_000) < p
    assert ece(p, y) < 0.01
    assert ece(np.full(1000, 0.9), np.zeros(1000, bool)) == pytest.approx(0.9)


def test_reliability_accumulator_merge_equals_joint():
    rng = np.random.default_rng(1)
    p1, p2 = rng.random(1000), rng.random(500)
    y1, y2 = rng.random(1000) < 0.3, rng.random(500) < 0.6
    a, b, j = ReliabilityAccumulator(), ReliabilityAccumulator(), ReliabilityAccumulator()
    a.add(p1, y1)
    b.add(p2, y2)
    a.merge(b)
    j.add(np.concatenate([p1, p2]), np.concatenate([y1, y2]))
    assert a.ece() == pytest.approx(j.ece())
    assert len(a.curve()) == 15 and sum(c["count"] for c in a.curve()) == 1500


def test_calibration_mask_band():
    wt = np.zeros((20, 20, 20), bool)
    wt[8:12, 8:12, 8:12] = True
    m = calibration_mask(wt, wt, None, "band", 2)
    assert m[6, 10, 10] and not m[2, 10, 10]
    assert calibration_mask(wt, wt, None, "volume").all()


def test_auroc_perfect_random_and_ties():
    failed = np.array([0, 0, 0, 1, 1], bool)
    assert auroc(np.array([0.1, 0.2, 0.3, 0.8, 0.9]), failed) == 1.0
    assert auroc(np.array([0.9, 0.8, 0.7, 0.1, 0.2]), failed) == 0.0
    assert auroc(np.full(5, 0.5), failed) == 0.5
    assert np.isnan(auroc(np.arange(3.0), np.zeros(3, bool)))
    # NaN score ranks as most uncertain
    assert auroc(np.array([0.1, 0.2, 0.3, np.nan, 0.9]), failed) == 1.0


def test_bootstrap_auroc_interval_contains_point():
    rng = np.random.default_rng(0)
    y = rng.random(200) < 0.3
    s = y + rng.normal(0, 0.8, 200)
    r = bootstrap_auroc(s, y, n_boot=300)
    assert r["lo"] <= r["auroc"] <= r["hi"] and r["lo"] > 0.5


def test_risk_coverage():
    scores = np.array([0.1, 0.5, 0.2, 0.9])
    dice = np.array([0.9, 0.6, 0.8, 0.2])
    rc = risk_coverage(scores, dice)
    assert rc["coverage"] == [0.25, 0.5, 0.75, 1.0]
    np.testing.assert_allclose(rc["mean_dice"], [0.9, 0.85, 2.3 / 3, 0.625])
    assert rc["dice_full"] == pytest.approx(0.625)
    assert rc["dice_at_80"] == pytest.approx(2.3 / 3)
    assert rc["aurc"] >= rc["oracle_aurc"]
    assert dice_at_coverage(np.array([0.5, 1.0]), np.array([0.9, 0.7]), 0.4) == 0.9


def test_failure_labels():
    f = failure_labels(np.array([0.9, 0.6, 0.9]), np.array([0.9, 0.9, 0.69]), 0.7)
    assert f.tolist() == [False, True, True]


def test_select_review_limit_rules():
    s = np.arange(10.0)
    assert select_review_limit(s, {"method": "quantile", "q": 0.8}) == pytest.approx(7.2)
    assert select_review_limit(s, {"method": "fixed", "value": 3}) == 3.0
    failed = s >= 7
    t = select_review_limit(s, {"method": "youden"}, failed)
    assert t == 6.0
    with pytest.raises(ValueError):
        select_review_limit(s, {"method": "bogus"})
