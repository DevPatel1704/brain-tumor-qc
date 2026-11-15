# Phase 5 report: uncertainty, trust gate, failure detection

**Data situation: C. Compute tier: 0.**

## What was done
- **Members:** seed replicates × flip TTA. nnU-Net's own mirroring is disabled because it averages logits internally. A streaming `MemberAccumulator` keeps the mean probability and mean member entropy, giving predictive entropy and mutual information in constant memory (`btqc.infer.tta`, `btqc.infer.predict`).
- **Case scores:** the boundary band (dilate 3, erode 3) as the primary score, plus WT-mean entropy and band mutual information as alternatives (`btqc.uncertainty.case_score`).
- **Failure definition and gate parameters**, fixed in `configs/uncertainty.yaml` and committed in the first commit (`fdd23cf`) before any held-out run: τ = 0.70 on WT or ET; review limit = 80th percentile of the in-site validation scores; default dashboard limit 0.25.
- **Gate** (`btqc.uncertainty.gate`): `flag = score > limit`, NaN or None flags, the exact limit does not flag, and only stdlib imports. The browser mirror is `web/src/gate.js`.
- **Evaluation:**
  - ECE with 15 bins, in band and volume modes, accumulated across cases;
  - reliability curves;
  - AUROC by Mann-Whitney with bootstrap CIs (2,000 resamples);
  - risk-coverage with AURC, oracle AURC, retained Dice at 80% and the gain;
  - review-limit rules (quantile, Youden, fixed).
- **MC dropout:** not added. nnU-Net's default architecture has no dropout, and adding it would change the baseline. Ensembles plus TTA are the compared estimators, and the alternative scores give a second comparison axis.

## Tests
- `tests/unit/test_gate.py` (R4): exact threshold, NaN and None, empty prediction, numpy scalars, invalid limit, monotonicity, signature, stdlib-only imports.
- `tests/unit/test_uncertainty.py`: entropy range, MI, band geometry, scores, ECE of perfect and miscalibrated cases, accumulator merge, AUROC with ties and NaN, bootstrap, risk-coverage arithmetic, limit rules.
- `tests/integration/test_pipeline_e2e.py`: the full chain on fixtures with the stub predictor.

## Real numbers
None for a model. On the 219 validation cases, the rule-based EXAMPLE scores have a median of 0.253 (10th-90th percentile 0.194-0.322), and the default limit flags 52% (`docs/report`, Fig. 11). These describe brightness rules, not a model.

## Not run
ECE, AUROC and risk-coverage on real held-out data.

## Next step
Phase 6: evaluation and statistics.
