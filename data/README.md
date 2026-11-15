# data/ (not committed)

Everything here is generated and git-ignored except this file and `splits/`:

- `manifest.csv`, `file_inventory.csv`, `phase0_summary.json`: Phase 0 (`make data-report`)
- `processed/`: canonical RAS NIfTI, viewer bundles, montages (`make convert`)
- `nnUNet_raw/`, `nnUNet_preprocessed/`, `nnUNet_results/`: nnU-Net folders (`make nnunet-prep`, training)
- `fixtures/`, `synthetic_demo/`: SYNTHETIC data for the smoke test and the pipeline demo
- `splits/`: site groups and folds (commit these before training, rule 8)
- `review.sqlite`: reviewer decisions from the dashboard
