| method | fold | score | n | n_failed | auroc | lo | hi | review_limit | flagged_frac | dice_mean_all | dice_mean_unflagged |
|---|---|---|---|---|---|---|---|---|---|---|---|
| baseline | mid | boundary_band | 32 | 5 | 0.837 | 0.650 | 0.968 | 0.172 | 0.469 | 0.803 | 0.919 |
| baseline | mid | wt_mean | 32 | 5 | 0.822 | 0.625 | 0.966 | – | – | – | – |
| baseline | mid | band_disagreement | 32 | 5 | 0.941 | 0.830 | 1.000 | – | – | – | – |
| tta_entropy | mid | boundary_band | 15 | 3 | 0.833 | 0.571 | 1.000 | 0.139 | 0.733 | 0.806 | 0.912 |
| tta_entropy | mid | wt_mean | 15 | 3 | 0.833 | 0.571 | 1.000 | – | – | – | – |
| tta_entropy | mid | band_disagreement | 15 | 3 | 0.917 | 0.692 | 1.000 | – | – | – | – |
