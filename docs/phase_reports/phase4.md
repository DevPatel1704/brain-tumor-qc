# Phase 4 report: shift characterization and mitigations

**Data situation: C. Compute tier: 0.**

## What was done
- **Shift metrics** (`btqc.eval.shift`): per-case histograms of z-scored brain intensities (100 bins over [-4, 6]), group profiles, Wasserstein-1 and KS distances on the binned distributions, Fréchet distance of feature Gaussians, a linear gap-versus-shift model with leave-one-out RMSE, and an estimate with a range.
- **E2** (`scripts/e2_shift.py`): computes per-fold shift against the fold's training pool, Spearman correlation with the gap, the training-pool reference profile and the gap model. Not run, because there are no folds.
- **Mitigations** (same budget and seeds):
  1. `nnUNetTrainer_btqcStrongAug`: polynomial bias field (order 3, ±0.3), noise variance up to 0.2, gamma 0.5-2.0.
  2. `nnUNetTrainer_btqcStyle`: random monotone Bézier intensity curve, the documented fallback for MaxStyle (D5).
  3. Per-case standardization (`btqc.data.standardize`: `pct` and `mode`), written as a separate nnU-Net dataset.
  4. Test-time adaptation (`btqc.infer.tta_adapt`): entropy minimization of instance-norm affine parameters only (D4).
- `docs/deviations.md` records every deviation.

## Tests
`tests/unit/test_torch_parts.py`:
- the adaptation lowers entropy, changes only the norm affine parameters and leaves the original model untouched;
- the bias-field and curve transforms keep shape and range, and the curve is monotone.

`tests/unit/test_shift_stats.py`:
- histograms are invariant to affine intensity changes;
- W1 equals the bin shift;
- the Fréchet distance matches the analytic value;
- the gap model recovers a known line.

`tests/unit/test_support_modules.py`: standardization is scale-invariant and keeps the background.

## Real numbers
Site-risk demo on the validation download: an EXAMPLE batch of the first 20 cases against an EXAMPLE reference made of the other 199 (`results/site_risk.json`). W1 mean 0.054 z-units (T1 0.022, T1ce 0.090, T2 0.063, FLAIR 0.042). This is computed from images only, so it is a real measurement of intensity-shape differences. It is not related to model accuracy.

## Not run
Training of all mitigations, E2 correlations, embedding shift.

## Next step
Phase 5: uncertainty, gate, failure detection.
