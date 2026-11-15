# Phase 3 report: baseline and site-held-out protocol

**Data situation: C. Compute tier: 0.**

## What was done
- `configs/sitegroups.yaml` holds the rules only: LGG-only (12-15) first, then institution 1, institution 18, small (< 15 cases) and mid. `btqc.data.sitegroups` computes group membership from the manifest.
- `btqc.train.splits`: one fold per group. The rest is split stratified by institution into 80/10/10 with a systematic slot pattern. `check_folds` rejects overlap and leakage. Output is `folds.json` plus nnU-Net `splits_final.json`, where each group's split is repeated `n_members` times (seed replicates).
- Leakage: `btqc.infer.ensemble.check_ensemble` and the harness's fold check (`LeakageError`).
- Custom trainers (`src/btqc/train/trainers/`, found via `nnUNet_extTrainer`):
  - `nnUNetTrainer_btqc`: `BTQC_EPOCHS` epochs (default 100, the same for every method), seed = `BTQC_SEED` + fold.
  - `nnUNetTrainer_btqcSmoke`: for gate G3.
- `scripts/make_splits.py`, `scripts/train_loso.py` (prints an estimate, requires `--yes` for jobs over 30 minutes, resumable with `--c`), MLflow tracking (SQLite backend).

## Real-data status
`scripts/make_splits.py` refuses to run: there are no labeled cases and no institution table, and site labels are never invented. **Real site groups, folds and baseline training: not run.**

## Gate G3 (smoke test, synthetic fixtures, CPU)
Command: `python scripts/train_smoke.py` (then `--keep` to reuse the model after fixing the inference environment).

| Item | Value (from `results/smoke_G3.json`) |
|---|---|
| Dataset | `Dataset990_BtqcFixture`: 12 SYNTHETIC cases, 48×48×40 |
| nnU-Net plan | 3d_fullres, patch [40, 48, 40], batch 2, ZScore normalization, SimpleITK I/O |
| Fold | hold out `inst_1`: train 7, val 1, in-site test 1, held-out 3 |
| Training loss per epoch | 0.7553 → 0.5321 → 0.3869 (decreasing) |
| Epoch time on CPU | about 36-40 s (8 iterations each) |
| Prediction files | 4 of 4, all scored by the harness |
| Inference (2 flip members, CPU) | 0.94 s per fixture case |
| MLflow run | `5ad1947178764c699bbd2cb148e7dcab` |
| Gate G3 | **passed** |

The mean WT Dice of 0.775 in this run belongs to a 3-epoch toy model on synthetic ellipsoids. It is not a segmentation result.

## Problems found and fixed
1. nnU-Net fingerprinting started 8 workers of about 1 GB each and exhausted 7.4 GB of RAM. Fixed with `-npfp 1`.
2. With `nnUNet_n_proc_DA=0`, the planner called `torch.set_num_threads(0)`. The runner now uses 0 only for `nnUNetv2_train`.
3. In-process inference could not find the custom trainer. The wrapper now sets `nnUNet_extTrainer` before importing nnU-Net.
4. MLflow 3.17 rejects the file store, so tracking now uses SQLite (`mlflow.db`).

## Estimate for the full protocol
5 folds × 3 seeds × 4 trained methods × 100 epochs: about 400 GPU hours at the configured 240 s per epoch (8-12 GB GPU), and about 200 h at 24 GB. These are planning figures in `configs/train.yaml`, to be replaced by the measured time of the first epoch.

## Next step
Phase 4: shift metrics and mitigations.
