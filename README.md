# Uncertainty-Gated Brain Tumor Segmentation Across Hospitals

**Engineering a trustworthy ML-enabled medical imaging system**

Applied-track course project, Ontario Tech University.
Dev Patel, Priyanka Gupta, Slesha Vora.

> **Research prototype only. Not a medical device and not for diagnosis.**

## The problem

Software can draw the outline of a brain tumor on an MRI scan automatically, which is much faster than drawing it by hand. These models are usually tested on scans from the same hospitals that supplied their training data. At a **new hospital**, with different scanners and settings, the same model can quietly become less accurate. Its output still looks just as confident, so a wrong outline can look exactly like a correct one.

This project asks two questions:

1. How much accuracy does a model lose at hospitals it has never seen?
2. Can the software warn the user when a particular result should be checked by a person?

## What we built

We took **nnU-Net**, an existing open-source segmentation tool, and the **FeTS 2022** dataset (1,251 labeled brain MRI cases from 23 institutions). Around them we built the parts a real system would need:

| Part | What it does |
|---|---|
| **Hospital-held-out evaluation** | Trains on some hospital groups and tests on a group the model never saw, then reports the accuracy drop for each tumor region with confidence intervals. It also checks automatically that no test case leaks into training |
| **Accuracy-improving methods** | Three training variants (stronger augmentation, style augmentation, per-scan standardization) and one test-time method (test-time adaptation), all run through the same evaluation |
| **Uncertainty monitor and trust gate** | The model predicts each scan 8 times on mirrored copies; where the predictions disagree, it is uncertain. A per-scan score above a fixed review limit, or a missing score, marks the scan **"Needs review"** |
| **Review dashboard** | A browser application with 2D and 3D views, tumor and uncertainty overlays, the review flag, a review queue (accept/reject, stored in SQLite), a hospital explorer, a site-risk page and a model card |
| **Quality assurance** | Eight requirements (R1–R8) traced to automated tests (unit, integration, metamorphic, regression, performance, browser), continuous integration on GitHub Actions, and Docker images |

## Requirements

| ID | Requirement | Status |
|---|---|---|
| R1 | Segment the whole tumor, tumor core and enhancing tumor | Met (pilot) |
| R2 | Report accuracy per hospital group | Partly met (1 of 5 groups run) |
| R3 | Give a voxel uncertainty map and a per-scan score | Met (pilot) |
| R4 | The review flag depends only on the score and the review limit | Met |
| R5 | Show scans in the correct orientation | Met |
| R6 | Store or share no patient identifiers | Met |
| R7 | Reproduce results from the configuration files | Partly met (training re-run not done) |
| R8 | Process one scan in under 60 s on one GPU | Not met (124 s with 8 passes; 17 s with 1 pass) |

Details and the test for each requirement are in [`docs/requirements.md`](docs/requirements.md).

## Main results (pilot)

The experiments ran on a 4 GB laptop GPU, which allowed a small pilot: one model, one held-out group of 7 institutions, 10 training epochs, and 98 randomly sampled test scans.

- **Accuracy (Dice, 1 = perfect).** At the training hospitals the scores were 0.88, 0.87 and 0.83, and at the unseen hospitals 0.86, 0.79 and 0.76 (whole tumor, tumor core, enhancing tumor). The drop is not statistically significant at this sample size.
- **Failure detection.** The uncertainty score separated failed from successful predictions with an AUROC of 0.84. 33% of flagged scans had failed, against 0% of unflagged scans.
- **Setting aside uncertain scans.** Setting aside the 20% most uncertain scans raised the average Dice of the rest from 0.80 to 0.86.
- **Test-time adaptation.** It gave no significant improvement.

The other four hospital groups and the three training variants were not trained (see [`docs/deviations.md`](docs/deviations.md)). Result files are in `results/`, and a summary is in [`docs/model_card.md`](docs/model_card.md).

## Repository contents

```
configs/   six YAML files: data, hospital groups, training, uncertainty (failure threshold, review-limit rule), metrics, server
src/btqc/  data/ (files, orientation, splits)  train/ (nnU-Net trainers)  infer/ (predictions, uncertainty)
           uncertainty/ (scores, trust gate)  eval/ (harness, statistics)  serve/ (FastAPI backend)
web/       browser dashboard: viewer, compare, review queue, explorer, site risk, model card (plain JavaScript + WebGL 2)
tests/     unit/ integration/ metamorphic/ regression/ perf/ ui/ (browser)
scripts/   command-line tasks: data report, conversion, training, inference, experiments E1-E6, documentation
docs/      requirements, architecture, metrics, deviations, model card, data report, phase reports
results/   experiment results (E1-E6 JSON, per-case and gap tables, training log);
           tables_synthetic_test_data/ = pipeline check on synthetic scans, not real results
data/      splits/ only (which cases are used for training and testing); the MRI data are never committed
docker/    application image, GPU training image, compose file
```

## Quick start (clean clone, synthetic test data, no MRI data needed)

```bash
python -m venv .venv && . .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -r requirements.lock --extra-index-url https://download.pytorch.org/whl/cpu
pip install -e . --no-deps
python scripts/tasks.py test                          # unit, integration, metamorphic, regression tests
python scripts/synthetic_demo.py                      # synthetic demo data for the explorer
python -m playwright install chromium && python scripts/tasks.py test-ui   # browser tests
python scripts/tasks.py app                           # dashboard at http://127.0.0.1:8000
```

## Reproduce the pilot (needs the FeTS 2022 data and a GPU)

1. Get the FeTS 2022 training data and the partitioning CSV (registration on Synapse).
2. Set `raw_root` and `institution_table` in `configs/data.yaml`.
3. Run:

```bash
python scripts/tasks.py data-report && python scripts/tasks.py convert
python scripts/tasks.py sitegroups && python scripts/tasks.py nnunet-prep
python scripts/train_loso.py --methods baseline --groups mid --yes
python scripts/infer.py --methods baseline --groups mid --per-split 15 --rolling
python scripts/run_experiments.py && python scripts/build_docs.py
```

For the full protocol, set `epochs: 100` in `configs/train.yaml` and train all methods and groups. `train_loso.py --dry-run` prints the time estimate first.

## Privacy

- **Data stays local.** No patient data is sent anywhere, and the API makes no outbound calls.
- **Logs.** The API logs only route templates, with no case IDs or file names.
- **Scans opened in the viewer** stay in the browser.
- **The FeTS data use agreement** applies to any redistribution of scans.

## License

MIT for the code. The data are governed by their own agreements.
