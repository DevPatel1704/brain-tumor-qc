from pathlib import Path

import pytest

from btqc.data.discover import classify_file, discover, parse_filename


@pytest.mark.parametrize(
    "name,case,seq",
    [
        ("00000096_brain_t1.nii", "00000096", "t1"),
        ("00000096_brain_t1ce.nii", "00000096", "t1ce"),
        ("00000096_brain_t2.nii", "00000096", "t2"),
        ("00000096_brain_flair.nii", "00000096", "flair"),
        ("BraTS2021_00000_t1.nii.gz", "BraTS2021_00000", "t1"),
        ("BraTS2021_00000_t1ce.nii.gz", "BraTS2021_00000", "t1ce"),
        ("FeTS2022_00000_flair.nii.gz", "FeTS2022_00000", "flair"),
        ("FeTS2022_00000_seg.nii.gz", "FeTS2022_00000", "seg"),
        ("FeTS2022_01234_T2.NII.GZ", "FeTS2022_01234", "t2"),
        ("BraTS2021_00495_t1gd.nii.gz", "BraTS2021_00495", "t1ce"),
    ],
)
def test_parse_known_patterns(name, case, seq):
    p = parse_filename(name)
    assert p is not None
    assert (p.case_id, p.sequence) == (case, seq)


@pytest.mark.parametrize(
    "name",
    ["notes.nii", "scan.nii.gz", "FeTS2022_00000_dwi.nii.gz", "FeTS2022_00000_t1.nii.bak", "t1.nii", "_t1.nii"],
)
def test_parse_rejects_unknown(name):
    assert parse_filename(name) is None


def test_t1ce_not_confused_with_t1():
    assert parse_filename("X_1_t1ce.nii").sequence == "t1ce"
    assert parse_filename("X_1_t1.nii").sequence == "t1"


def _touch(p: Path) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"")
    return p


def test_wrapper_directory_wins_and_keeps_inner_name(tmp_path):
    f = _touch(tmp_path / "FeTS2022_00027" / "FeTS2022_00027_flair.nii" / "00000019_brain_flair.nii")
    entry, problem = classify_file(f)
    assert problem is None
    assert entry.case_id == "FeTS2022_00027"
    assert entry.sequence == "flair"
    assert entry.inner_name == "00000019_brain_flair.nii"


def test_wrapper_sequence_conflict_is_reported(tmp_path):
    f = _touch(tmp_path / "C" / "FeTS2022_00001_t1.nii" / "FeTS2022_00001_t2.nii")
    entry, problem = classify_file(f)
    assert entry is None and "conflict" in problem


def test_discover_groups_and_lists_unparsed(tmp_path):
    for s in ("t1", "t1ce", "t2", "flair"):
        _touch(tmp_path / "FeTS2022_00001" / f"FeTS2022_00001_{s}.nii" / f"FeTS2022_00001_{s}.nii")
    for s in ("t1", "t2"):
        _touch(tmp_path / "BraTS2021_00002" / f"BraTS2021_00002_{s}.nii.gz")
    _touch(tmp_path / "misc" / "weird_scan.nii.gz")
    _touch(tmp_path / "FeTS2022_00001" / "FeTS2022_00001_flair.nii" / "png" / "slice_000.png")
    d = discover(tmp_path)
    assert set(d.cases) == {"FeTS2022_00001", "BraTS2021_00002"}
    assert d.cases["FeTS2022_00001"].has_all_sequences
    assert d.cases["BraTS2021_00002"].missing == ["t1ce", "flair"]
    assert [p.name for p in d.unparsed] == ["weird_scan.nii.gz"]
    assert d.other_files == {".png": 1}


def test_duplicate_sequence_reported(tmp_path):
    _touch(tmp_path / "a" / "X_1_t1.nii")
    _touch(tmp_path / "b" / "X_1_t1.nii.gz")
    d = discover(tmp_path)
    assert len(d.duplicates) == 1
