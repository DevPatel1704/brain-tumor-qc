import numpy as np
import pytest

from btqc.data.labels import (
    convert,
    detect_convention,
    labels_from_regions,
    regions,
    regions_from_nnunet_definition,
)


def _random_brats(rng, conv_et=4, shape=(12, 10, 8)):
    return rng.choice(np.array([0, 1, 2, conv_et], dtype=np.uint8), size=shape, p=[0.6, 0.1, 0.2, 0.1])


@pytest.mark.parametrize(
    "values,expected",
    [({0, 1, 2, 4}, "brats_124"), ({0, 1, 2, 3}, "brats_123"), ({0, 2, 4}, "brats_124"),
     ({0, 1, 2}, "ambiguous_no_enhancing"), ({0}, "unknown"), ({0, 1, 5}, "unknown:1,5")],
)
def test_detect_convention(values, expected):
    assert detect_convention(values) == expected


@pytest.mark.parametrize("src,et", [("brats_124", 4), ("brats_123", 3)])
def test_nnunet_regions_match_original_regions(src, et):
    """WT/TC/ET reconstructed from the remapped labels with the dataset.json region
    definitions must equal WT/TC/ET computed from the original BraTS labels."""
    rng = np.random.default_rng(0)
    seg = _random_brats(rng, et)
    ref = regions(seg, src)
    remapped = convert(seg, src, "nnunet")
    assert set(np.unique(remapped)) <= {0, 1, 2, 3}
    got = regions_from_nnunet_definition(remapped)
    for r in ("WT", "TC", "ET"):
        np.testing.assert_array_equal(got[r], ref[r])


def test_round_trip_conventions():
    rng = np.random.default_rng(1)
    seg = _random_brats(rng, 4)
    back = convert(convert(seg, "brats_124", "nnunet"), "nnunet", "brats_124")
    np.testing.assert_array_equal(back, seg)
    np.testing.assert_array_equal(convert(convert(seg, "brats_124", "brats_123"), "brats_123", "brats_124"), seg)


def test_convert_rejects_foreign_labels():
    with pytest.raises(ValueError):
        convert(np.array([0, 1, 3]), "brats_124", "nnunet")


def test_labels_from_regions_inverts_regions():
    rng = np.random.default_rng(2)
    seg = _random_brats(rng, 4)
    r = regions(seg, "brats_124")
    np.testing.assert_array_equal(labels_from_regions(r["WT"], r["TC"], r["ET"], "brats_124"), seg)


def test_region_nesting():
    rng = np.random.default_rng(3)
    r = regions(_random_brats(rng, 4), "brats_124")
    assert not (r["ET"] & ~r["TC"]).any()
    assert not (r["TC"] & ~r["WT"]).any()
