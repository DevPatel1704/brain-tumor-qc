import itertools

import nibabel as nib
import numpy as np
import pytest

from btqc.data.orient import (
    canonical_to_original_index,
    from_canonical,
    orientation_from_affine,
    original_to_canonical_index,
    to_canonical,
)

LPS =np.array([[-1.0, 0, 0, 0], [0, -1.0, 0, 239.0], [0, 0, 1.0, 0], [0, 0, 0, 1]])


def _affines():
    """All 48 axis permutations and sign combinations, with non-unit spacing and an offset."""
    out = []
    for perm in itertools.permutations(range(3)):
        for signs in itertools.product([1, -1], repeat=3):
            a = np.zeros((4, 4))
            for i, j in enumerate(perm):
                a[j, i] = signs[i] * (1.0 + 0.5 * i)
            a[:3, 3] = [10.0, -20.0, 5.0]
            a[3, 3] = 1
            out.append(a)
    return out


def test_planted_voxel_lps_brats_affine():
    """Real FeTS files have affine diag(-1,-1,1): planted voxel must land at the mirrored index."""
    shape = (240, 240, 155)
    data = np.zeros(shape, dtype=np.int16)
    orig = (95, 150, 82)
    data[orig] = 7
    can, aff, o = to_canonical(data, LPS)
    expected = (240 - 1 - 95, 240 - 1 - 150, 82)
    assert tuple(np.argwhere(can == 7)[0]) == expected
    assert original_to_canonical_index(orig, o) == expected
    assert canonical_to_original_index(expected, o) == orig
    assert "".join(nib.aff2axcodes(aff)) == "RAS"
    # same world position before and after
    np.testing.assert_allclose(aff @ [*expected, 1], LPS @ [*orig, 1])


@pytest.mark.parametrize("affine", _affines())
def test_round_trip_all_orientations(affine):
    rng = np.random.default_rng(0)
    shape = (7, 5, 4)
    data = np.zeros(shape, dtype=np.int16)
    idx = tuple(int(rng.integers(0, s)) for s in shape)
    data[idx] = 1
    can, aff, o = to_canonical(data, affine)
    assert "".join(nib.aff2axcodes(aff)) == "RAS"
    c = tuple(np.argwhere(can == 1)[0])
    assert original_to_canonical_index(idx, o) == c
    assert canonical_to_original_index(c, o) == idx
    np.testing.assert_allclose(aff @ [*c, 1], affine @ [*idx, 1])
    np.testing.assert_array_equal(from_canonical(can, o), data)


@pytest.mark.parametrize("affine", _affines()[::5])
def test_matches_nibabel_closest_canonical(affine):
    rng = np.random.default_rng(1)
    data = rng.integers(0, 100, size=(6, 5, 4)).astype(np.int16)
    can, aff, _ = to_canonical(data, affine)
    ref = nib.as_closest_canonical(nib.Nifti1Image(data, affine))
    np.testing.assert_array_equal(can, np.asarray(ref.dataobj))
    np.testing.assert_allclose(aff, ref.affine)


def test_oblique_affine_picks_dominant_axes():
    th = np.deg2rad(20)
    rot = np.array([[np.cos(th), -np.sin(th), 0], [np.sin(th), np.cos(th), 0], [0, 0, 1]])
    a = np.eye(4)
    a[:3, :3] = rot @ np.diag([-1, -1, 1])
    o = orientation_from_affine(a, (4, 4, 4))
    assert o.perm == (0, 1, 2) and o.flip == (True, True, False)


def test_channels_last_axis_preserved():
    data = np.zeros((4, 5, 6, 3))
    data[1, 2, 3, 2] = 1
    can, _, o = to_canonical(data, LPS)
    ci = original_to_canonical_index((1, 2, 3), o)
    assert can[(*ci, 2)] == 1
    assert can.shape == (4, 5, 6, 3)
