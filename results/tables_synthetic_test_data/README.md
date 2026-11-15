# Synthetic test-data tables (not real results)

These tables are produced by `scripts/synthetic_demo.py`. It runs the full evaluation pipeline (harness, statistics, failure detection, table writer) on small **synthetic test scans** with a simple stub predictor instead of a trained model.

They exist only to show that the evaluation code works end to end without any patient data or GPU. **They are not results of the brain tumor model.** The real pilot results are in `results/tables/` and `results/*.json`.
