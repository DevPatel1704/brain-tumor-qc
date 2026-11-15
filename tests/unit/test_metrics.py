import numpy as np
import pytest

from btqc.eval.metrics import BRATS_EMPTY_PENALTY_MM, EmptyPolicy, asd, dice, hd95, region_metrics


def _cube(shape, lo, hi):
    m = np.zeros(shape, dtype=bool)
    m[tuple(slice(a, b) for a, b in zip(lo, hi))] = True
    return m


def test_dice_basic():
    a = _cube((10, 10, 10), (2, 2, 2), (6, 6, 6))
    assert dice(a, a) == 1.0
    b = _cube((10, 10, 10), (4, 2, 2), (8, 6, 6))  # half overlap
    assert dice(a, b) == pytest.approx(0.5)
    assert dice(a, np.zeros_like(a)) == 0.0


def test_empty_mask_convention():
    z = np.zeros((5, 5, 5), dtype=bool)
    a = _cube((5, 5, 5), (1, 1, 1), (3, 3, 3))
    assert dice(z, z) == 1.0 and hd95(z, z) == 0.0 and asd(z, z) == 0.0
    assert dice(a, z) == 0.0 and dice(z, a) == 0.0
    assert hd95(a, z) == BRATS_EMPTY_PENALTY_MM == pytest.approx(373.13, abs=0.01)
    assert hd95(z, a, policy=EmptyPolicy(100.0)) == 100.0
    assert asd(z, a) == BRATS_EMPTY_PENALTY_MM


def test_hd95_shift_equals_shift_distance():
    a = _cube((30, 30, 30), (5, 5, 5), (15, 15, 15))
    b = np.roll(a, 3, axis=0)
    assert hd95(a, b) == pytest.approx(3.0)
    assert hd95(a, b, spacing=(2.0, 1.0, 1.0)) == pytest.approx(6.0)
    assert hd95(a, a) == 0.0
    assert 0 < asd(a, b) <= 3.0


def test_hd95_symmetric():
    rng = np.random.default_rng(0)
    a = rng.random((20, 20, 20)) > 0.7
    b = rng.random((20, 20, 20)) > 0.7
    assert hd95(a, b) == pytest.approx(hd95(b, a))


def test_region_metrics_flags_and_volume():
    a = _cube((10, 10, 10), (0, 0, 0), (10, 10, 1))  # 100 voxels
    z = np.zeros_like(a)
    m = region_metrics({"WT": a, "ET": z}, {"WT": a, "ET": a}, spacing=(1, 1, 1))
    assert m["dice_WT"] == 1.0 and m["vol_ref_ml_WT"] == pytest.approx(0.1)
    assert m["ref_empty_ET"] == 1.0 and m["penalized_ET"] == 1.0 and m["dice_ET"] == 0.0
