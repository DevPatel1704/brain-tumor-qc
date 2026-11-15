# Metric and label conventions

## Labels
- BraTS labels: 1 necrotic or non-enhancing core (NCR), 2 edema (ED), 4 enhancing tumor (ET). Some releases use 3 for ET.
- `btqc.data.labels.detect_convention` decides which convention applies from the label values present. `convert()` maps between conventions, and the round trips are unit-tested.
- Regions: WT = {NCR, ED, ET}, TC = {NCR, ET}, ET = {ET}.
- nnU-Net labels (from nnU-Net's own `Dataset137_BraTS21.py`): edema→1, NCR→2, ET→3. `dataset.json` regions: whole tumor [1, 2, 3], tumor core [2, 3], enhancing tumor [3], with `regions_class_order` [1, 2, 3]. Key order is preserved, as `documentation/region_based_training.md` requires. A test checks that the regions rebuilt from the remapped labels equal the original regions.

## Overlap and distance
- **Dice** = 2|A∩B| / (|A| + |B|).
- **HD95** is the 95th percentile of the pooled symmetric surface distances (prediction→reference and reference→prediction concatenated, as in MedPy `hd95`), in mm using the voxel spacing. Surfaces are the voxels removed by one 6-connected binary erosion.
- **ASD** is the mean of the same pooled distances.

## Empty masks (`configs/eval.yaml`)
| Reference | Prediction | Dice | HD95 / ASD |
|---|---|---|---|
| empty | empty | 1 | 0 |
| empty | non-empty | 0 | 373.13 mm |
| non-empty | empty | 0 | 373.13 mm |

373.13 mm = sqrt(240² + 240² + 155²), the diagonal of the BraTS 240×240×155 grid at 1 mm, which is the largest possible distance. The same constant (373.1287) is used in published BraTS-family evaluations, for example FANCL on BraTS-METS 2023 ([arXiv:2410.22057](https://arxiv.org/abs/2410.22057)). BraTS 2023 adult-glioma reports use 374 ([arXiv:2402.17317](https://arxiv.org/abs/2402.17317)). **We could not find this constant in an official BraTS 2021 document**, so it is a documented choice rather than a citation of the 2021 rules. Every HD95 mean is reported with the fraction of penalized cases (`penalized_frac_heldout`), and cases without enhancing tumor in the reference are counted separately (`ref_has_et`).

## Uncertainty and calibration
- Voxel uncertainty: the binary entropy (bits) of the member-mean sigmoid per region, averaged over WT, TC and ET, so it lies in [0, 1]. Members are seed replicates × flip TTA. Member disagreement is the mutual information.
- Case score: the mean voxel uncertainty in the band `dilate(WT, 3) AND NOT erode(WT, 3)` around the predicted whole tumor. NaN if the prediction is empty, which the gate flags.
- ECE: 15 equal-width bins on [0, 1] over the positive-class probability of each region, weighted by voxel count. The "band" mode uses voxels within 5 voxels of the predicted or reference WT, inside the brain. The "volume" mode uses all brain voxels.

## Failure detection and risk-coverage
- Failure: WT Dice < τ or ET Dice < τ, with τ = 0.70 (`configs/uncertainty.yaml`, fixed before any held-out run).
- AUROC by Mann-Whitney U with average ranks, with a 95% percentile bootstrap over cases (2,000 resamples). NaN scores rank as most uncertain.
- Risk-coverage: cases are sorted by score ascending, and the mean Dice (average of WT, TC, ET) of the retained set is reported against coverage. We report AURC (risk = 1 − Dice), the oracle AURC, the area under the retained-Dice curve, and the gain at 80% coverage.
- Review limit: chosen on each fold's in-site validation cases with the configured rule (default: 80th percentile of the validation scores), then applied unchanged to the held-out group.

## Statistics
Case-level percentile bootstrap (2,000 resamples), two-sided paired Wilcoxon signed-rank tests (`zero_method="wilcox"`), and Spearman correlations. Groups with fewer than 15 held-out cases are marked "small n".
