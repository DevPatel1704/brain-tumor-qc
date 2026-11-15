import json

import nibabel as nib
import numpy as np

from btqc.data.convert import ConvertOptions, convert_all
from btqc.data.discover import discover
from btqc.data.labels import regions, regions_from_nnunet_definition
from btqc.train.nnunet_setup import build_raw_dataset, install_splits


def test_raw_dataset_matches_nnunet_format(synthetic_root, tmp_path):
    proc = tmp_path / "proc"
    convert_all(discover(synthetic_root), ConvertOptions(out_root=proc, raw_root=synthetic_root, montage=False),
                workers=1)
    can = proc / "canonical"
    out = build_raw_dataset(can, tmp_path / "raw", 990, "Fixture", ["FeTS2022_00000", "FeTS2022_00001"],
                            ["FeTS2022_00002"])
    dj = json.loads((out / "dataset.json").read_text())
    assert list(dj["labels"]) == ["background", "whole tumor", "tumor core", "enhancing tumor"]  # order kept
    assert dj["labels"]["whole tumor"] == [1, 2, 3] and dj["regions_class_order"] == [1, 2, 3]
    assert dj["numTraining"] == 2 and dj["channel_names"] == {"0": "T1", "1": "T1ce", "2": "T2", "3": "Flair"}
    assert sorted(p.name for p in (out / "imagesTr").iterdir())[:4] == [
        f"FeTS2022_00000_{i:04d}.nii.gz" for i in range(4)]
    assert len(list((out / "imagesTs").iterdir())) == 4
    # channel 0003 is FLAIR: identical voxels to the canonical FLAIR
    a = np.asarray(nib.load(str(out / "imagesTr" / "FeTS2022_00000_0003.nii.gz")).dataobj)
    b = np.asarray(nib.load(str(can / "FeTS2022_00000" / "FeTS2022_00000_flair.nii.gz")).dataobj)
    np.testing.assert_array_equal(a, b)
    # WT/TC/ET reconstructed from nnU-Net labels with the dataset.json regions equal the original BraTS regions
    lab = np.asarray(nib.load(str(out / "labelsTr" / "FeTS2022_00000.nii.gz")).dataobj)
    ref = np.asarray(nib.load(str(can / "FeTS2022_00000" / "FeTS2022_00000_seg.nii.gz")).dataobj)
    assert set(np.unique(lab)) <= {0, 1, 2, 3}
    got, want = regions_from_nnunet_definition(lab), regions(ref, "brats_124")
    for r in ("WT", "TC", "ET"):
        np.testing.assert_array_equal(got[r], want[r])
    p = install_splits([{"train": ["a"], "val": ["b"]}], tmp_path / "pre", 990, "Fixture")
    assert p.name == "splits_final.json" and p.parent.name == "Dataset990_Fixture"
