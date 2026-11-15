# Phase 9 report: testing, QA and reproducibility

**Data situation: C. Compute tier: 0.**

## Results (all on synthetic fixtures unless stated)
| Suite | Command | Result |
|---|---|---|
| Lint | `ruff check src scripts tests` | pass |
| Types | `mypy` (src, 50 files) | no issues |
| CI suite: unit, integration, metamorphic, regression | `python scripts/tasks.py test` / `scripts/e6_software.py` | **177 passed, 16 deselected**, statement coverage **81.1%** (`results/e6_software.json`) |
| Browser | `pytest tests/ui` (headless Chromium, SwiftShader WebGL) | **14 passed** (`results/ui_junit.xml`) |
| Performance | `pytest tests/perf` | passed; see below |
| Slow metamorphic on the smoke nnU-Net model | `pytest -m slow tests/metamorphic` | available when `data/nnUNet_results/Dataset990*` exists |

Test inventory: unit 155, integration 12, metamorphic 9, regression 2, perf 1, ui 14.

## Coverage of the brief's checklist
- **Unit:** filename parsing, orientation and round trip (48 orientations, nibabel cross-check), label remap, metrics including empty masks, uncertainty functions, trust gate, split generation (no overlap, no leakage), manifest.
- **Integration:** conversion end to end, nnU-Net dataset format, then stub predictor → records → harness → summary → API (cases, volumes, prediction, flag flip, reviews, bad ids, upload rejection, no ids in logs).
- **Metamorphic:** translation by (3, −2, 1), Dice ≥ 0.95; ×0.95 and ×1.05 intensity, Dice ≥ 0.99; flips, Dice ≥ 0.99 (rule-based predictor). The toy-model version uses looser stated tolerances.
- **Regression:** fixed seeds, stored baseline (`tests/regression/baseline.json`), tolerance 1e-6, identical re-run.
- **Performance** (`results/perf.json`, 240×240×155 synthetic case, CPU, measured while another job was running, so upper bounds): conversion 25.7 s; 3 stub members + uncertainty + scores 16.8 s; about 40,000 gate decisions per second; viewer bundles 8.8 MB. Single-file demo: 6.4 MB. **GPU model latency (R8): not run.**
- **Browser:** synthetic NIfTI planted-voxel readout; non-NIfTI rejection message; mask overlay; flag flip around the score; review persistence; WebGL render; 390 px with no overflow on 5 pages; no console errors; synthetic explorer; offline export (no requests, exact cropped-index round trip).
- **Reproducibility:** configs + seeds; `requirements.lock`; manifest SHA-256 for all 876 inputs; Docker app and train images; compose file for app + MLflow; README quickstart from a clean clone on fixtures.

## Not committed
Data, checkpoints, prediction records, MLflow DB/artifacts and caches. Locations are listed in the README under "Where things live".

## Not run
The Docker build was not run locally (CI job only). Tolerance re-runs of real nnU-Net training (R7) and GPU latency (R8) were not run.
