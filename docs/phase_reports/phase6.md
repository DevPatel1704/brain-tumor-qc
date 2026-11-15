# Phase 6 report: evaluation and statistics

**Data situation: C. Compute tier: 0.**

## What was done
- **Metrics** (`btqc.eval.metrics`): Dice, HD95 (pooled symmetric distances, 95th percentile) and ASD. Empty-mask convention: both empty gives 1/0/0; exactly one empty gives Dice 0 and 373.13 mm. The penalty's source was checked: it is not found in an official BraTS 2021 document but is used in published BraTS-family evaluations. See `docs/metrics.md` and D11.
- **Harness** (`btqc.eval.loso`): per-case metrics, scores, calibration counts, leakage guard, and a gap table with bootstrap CIs and a small-n marker.
- **Statistics** (`btqc.eval.stats`): bootstrap CI, bootstrap difference CI, paired Wilcoxon, Spearman, and Holm adjustment for the twelve mitigation × region comparisons.
- **Outputs:** `results/*.csv`, `eval_summary.json`, figures (PNG and PDF), and Markdown and LaTeX tables. E1-E6 live in `scripts/e1_gap.py` ... `scripts/e6_software.py`, run together by `scripts/run_experiments.py`.
- **Synthetic demonstration** (`scripts/synthetic_demo.py`): 40 SYNTHETIC cases and a stub predictor, written to `results/*_synthetic.*`. It exists only to exercise the chain and the explorer, and every output is labeled SYNTHETIC.

## Hypotheses
| Hypothesis | Status |
|---|---|
| H1: held-out Dice < in-site, largest for ET and LGG-only | not run |
| H2: a mitigation reduces the mean gap | not run |
| H3: AUROC CI excludes 0.5 and deferral raises retained Dice | not run |

## Real numbers
E1-E5 write `status: "not run"` with the reason: no site-held-out folds (situation C). E6 ran; see Phase 9.

## Next step
Phase 7: dashboard.
