# Phase 0 report: inspect the directory and the NIfTI files

**Data situation: C** (only unlabeled scans). **Compute tier: 0** (GTX 1650 Ti with 4 GB is below the 8 GB Tier 1 floor; torch is installed as the CPU build).

## What was done
- Inspected the raw root `D:\Foundation Project\MICCAI_FeTS2022_ValidationData` read-only: directory layout, every NIfTI header, per-file intensity statistics, SHA-256 checksums, and case-level grid consistency.
- Machine check: OS, CPU, RAM, disk, GPU (nvidia-smi), Python, torch and network.
- Searched for an institution table, both in the raw root and among CSV files near the project. None was found.
- Found the project inputs outside the data folder (`C:\Users\Dev\Downloads`): the proposal (`Project_Proposal_Brain_Tumor_Segmentation_IEEE (1).docx`, the newest version, used as the specification) and the two reference HTML files, under the names `Brain MRI viewer.html` and `Brain MRI viewer, finished-app example.html`.

## Files created
- `src/btqc/data/discover.py`, `nifti_io.py`, `manifest.py`, `labels.py`, `src/btqc/sysinfo.py`, `src/btqc/config.py`
- `scripts/data_report.py`, `configs/data.yaml`
- `docs/data_report.md` (generated, plus `docs/data_report_notes.md` with hand-checked notes)
- `data/manifest.csv` (219 rows), `data/file_inventory.csv` (876 rows), `data/phase0_summary.json`
- Tests: `tests/unit/test_discover.py`, `tests/unit/test_labels.py`

## Commands run
```
python scripts/data_report.py --workers 4     # 520 s, exit 0
python -m pytest tests/unit tests/integration # 141 passed
```

## Real numbers (from `data/phase0_summary.json`)
- 876 NIfTI files in 219 cases. 0 unparsed, 0 conflicts, 0 duplicates. 155 unrelated PNGs.
- All 219 cases have T1, T1ce, T2 and FLAIR with identical shape (240x240x155), spacing (1 mm) and affine (LPS). 0 segmentation files.
- Every file sits in a wrapper directory carrying the official name. 36 cases have inner names in the `<8 digits>_brain_<seq>.nii` pattern.
- Skull-stripped: median border-shell zero fraction 0.9994, median brain (nonzero) fraction 0.166.

## Deviations from the brief
- The project files are not in the data folder. The repository was created as a sibling folder (`D:\Foundation Project\brain-tumor-qc`) so that the data folder stays read-only (rule 6).
- `make` is not installed on this Windows machine. Every Makefile target delegates to `scripts/tasks.py`, which can be run directly.

## Proposal vs brief conflicts (the proposal is followed where they conflict)
1. **Baseline predictor.** The proposal says "a five-model ensemble is the baseline predictor", while the brief's leakage rule forbids ensembling models from different folds. These are reconciled as a per-fold ensemble of seed replicates: for each fold, `n_members` models trained on that fold's split (`configs/train.yaml`). This respects both documents.
2. **Test-time adaptation.** The proposal lists "test-time adaptation of normalization statistics". nnU-Net uses instance normalization, so statistic adaptation does not apply (brief, Phase 4). The adaptation is done on the instance-norm affine parameters by entropy minimization instead, which keeps the proposal's intent (`src/btqc/infer/tta_adapt.py`).

## Open risks
- No labeled training data and no institution table, so no model can be trained or scored (situation C).
- Tier 0 hardware: the 4 GB GPU is not usable with the installed CPU torch build. Full 3D nnU-Net training is not feasible here.

## Needed from the user
The labeled **FeTS 2022 training data** (1,251 cases, with `_seg` files) and the **FeTS 2022 partitioning CSV** (`partitioning_1.csv`, columns `Partition_ID, Subject_ID`). Both are available after registering on Synapse for the FeTS 2022 challenge. Point `raw_root` and `institution_table` in `configs/data.yaml` at them.

## Next step
Phase 1: conversion to canonical RAS, viewer bundles, montages and the nnU-Net dataset.
