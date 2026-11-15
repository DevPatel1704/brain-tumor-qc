# Phase 1 report: convert and prepare the data

**Data situation: C. Compute tier: 0.**

## What was done
- Canonical RAS copies of all 219 cases (876 files): original dtype, clean header (no free-text fields), original affine and orientation kept in `meta.json`.
- Viewer bundles: gzip uint8, x-fastest, with nonzero voxels mapped from the 1st-99th percentile to 1..255 and background kept at 0. One JSON per sequence holds dims, spacing, affine, window limits and the original-orientation mapping.
- QA montages (4 sequences × 3 planes, radiological display, with orientation letters).
- nnU-Net raw dataset `Dataset501_FeTS2022`: 219 cases in `imagesTs` as hard links to the canonical files (no extra disk space), and a `dataset.json` in the region format. There are 0 training cases because none are labeled.
- Synthetic fixtures (`btqc.data.fixtures`): ellipsoid tumors, four fake sequences with BraTS-like contrasts, LPS affine like the real files, per-institution intensity gain and gamma, and a fake partition CSV labeled SYNTHETIC.

## Files
`src/btqc/data/orient.py`, `convert.py`, `fixtures.py`, `standardize.py`; `src/btqc/train/nnunet_setup.py`; `scripts/convert.py`, `scripts/nnunet_prep.py`; tests `tests/unit/test_orient.py`, `tests/integration/test_convert.py`, `tests/integration/test_nnunet_setup.py`.

## Commands and results
```
python scripts/convert.py --workers 3      # {'converted': 219} in 1999 s (data/processed/convert_log.json)
python scripts/nnunet_prep.py              # Dataset501_FeTS2022: 0 training cases, 219 test cases
```
Disk use: canonical copies and bundles about 2 GB on D:.

## Gate G1
- **Orientation round trip:** passes for all 48 axis permutations and sign combinations. It matches `nibabel.as_closest_canonical`, the planted voxel at file index (95, 150, 82) lands at RAS index (144, 89, 82) and maps back, and the planted marker survives a full conversion.
- **nnU-Net labels:** WT, TC and ET rebuilt from the remapped labels with the `dataset.json` regions equal the regions from the original BraTS labels (both conventions).
- **Montages viewed by eye:**
  - `FeTS2022_00001`: FLAIR-bright lesion in the patient-left frontotemporal region, shown on screen right (radiological). Anterior at the top of the axial view, superior at the top of the coronal and sagittal views, frontal pole on the left of the sagittal view.
  - `FeTS2022_00467` (negative T2 voxels): normal anatomy, midline sagittal with the corpus callosum, small patient-left frontal FLAIR lesion.
  - `FeTS2022_00153` (qform only, no sform): ring-enhancing patient-left temporal lesion, consistent across all sequences and planes.
  - `FeTS2022_00573` (float32 storage): its T1 was acquired sagittally (sharp only in the sagittal plane). An acquisition difference, not a geometry error.

  All four agree with the expected anatomy, so G1 passes.

## Deviations
- 2D slices for optional 2D experiments are written only with `--slices2d`, stored per case so any split is by case.
- nnU-Net training data cannot be created without labels (situation C).

## Next step
Phase 2: repository, environment, CI.
