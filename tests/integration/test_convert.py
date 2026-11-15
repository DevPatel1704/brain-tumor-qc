import json

import nibabel as nib
import numpy as np

from btqc.data.convert import ConvertOptions, convert_all, read_bundle
from btqc.data.discover import discover
from btqc.data.fixtures import LPS_AFFINE
from btqc.data.orient import canonical_to_original_index


def test_convert_fixture_end_to_end(synthetic_root, tmp_path):
    out = tmp_path / "processed"
    disc = discover(synthetic_root)
    res = convert_all(disc, ConvertOptions(out_root=out, raw_root=synthetic_root), workers=1)
    assert {r["status"] for r in res} == {"converted"}
    cid = "FeTS2022_00000"
    meta = json.loads((out / "canonical" / cid / "meta.json").read_text())
    assert meta["label_convention"] == "brats_124"
    img = nib.load(str(out / "canonical" / cid / f"{cid}_t1.nii.gz"))
    assert "".join(nib.aff2axcodes(img.affine)) == "RAS"
    assert img.get_data_dtype() == np.int16
    # canonical seg equals mirrored original seg (LPS -> RAS flips x and y)
    raw = np.asarray(nib.load(str(synthetic_root / cid / f"{cid}_seg.nii.gz")).dataobj)
    can = np.asarray(nib.load(str(out / "canonical" / cid / f"{cid}_seg.nii.gz")).dataobj)
    np.testing.assert_array_equal(can, raw[::-1, ::-1, :])
    # viewer bundle round trip and background preserved
    u8, bmeta = read_bundle(out / "viewer" / cid, "flair")
    assert bmeta["dims"] == list(can.shape) and bmeta["orientation"] == "RAS"
    flair = np.asarray(nib.load(str(out / "canonical" / cid / f"{cid}_flair.nii.gz")).dataobj)
    assert ((u8 == 0) == (flair == 0)).all()
    assert u8[flair != 0].min() >= 1
    seg_u8, _ = read_bundle(out / "viewer" / cid, "seg")
    np.testing.assert_array_equal(seg_u8, can)
    assert (out / "montage" / f"{cid}.png").stat().st_size > 1000
    # second run is skipped (resumable)
    res2 = convert_all(disc, ConvertOptions(out_root=out, raw_root=synthetic_root), workers=1, max_cases=2)
    assert {r["status"] for r in res2} == {"skipped"}


def test_planted_marker_through_conversion(tmp_path):
    """Plant a marker at a known original index, convert, find it at the expected canonical index."""
    from btqc.data.fixtures import make_case, write_case

    c = make_case("FeTS2022_00099", shape=(20, 18, 12))
    orig = (3, 14, 7)
    for s in c.images:
        c.images[s][orig] = 3000
    raw = tmp_path / "raw"
    write_case(c, raw, with_seg=False)
    out = tmp_path / "out"
    convert_all(discover(raw), ConvertOptions(out_root=out, raw_root=raw, montage=False), workers=1)
    meta = json.loads((out / "canonical" / c.case_id / "meta.json").read_text())
    assert np.allclose(meta["original_affine"], LPS_AFFINE)
    can = np.asarray(nib.load(str(out / "canonical" / c.case_id / f"{c.case_id}_t2.nii.gz")).dataobj)
    hit = tuple(int(v) for v in np.argwhere(can == 3000)[0])
    assert hit == (20 - 1 - 3, 18 - 1 - 14, 7)
    from btqc.data.orient import Orientation

    o = Orientation(tuple(meta["orientation"]["perm"]), tuple(meta["orientation"]["flip"]),
                    tuple(meta["orientation"]["shape"]))
    assert canonical_to_original_index(hit, o) == orig


def test_wrapped_unlabeled_layout(synthetic_wrapped_root, tmp_path):
    disc = discover(synthetic_wrapped_root)
    assert len(disc.cases) == 4 and all(c.has_all_sequences and not c.has_seg for c in disc.cases.values())
    res = convert_all(disc, ConvertOptions(out_root=tmp_path, raw_root=synthetic_wrapped_root, montage=False),
                      workers=1)
    assert {r["status"] for r in res} == {"converted"}
