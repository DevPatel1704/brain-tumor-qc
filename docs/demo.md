# Five-minute demonstration

Audience: course instructor and classmates. Setup: `python scripts/tasks.py app` running and the browser at `http://127.0.0.1:8000`. As a fallback, open `dist/btqc_demo.html` (works offline).

**Say at the start:** "This is a laptop pilot. I trained one baseline nnU-Net for 10 epochs on a 4 GB GPU, holding out seven hospitals (group `mid`) completely, and tested it on a random sample of cases. Labeled test cases show the trained model; the 219 unlabeled validation scans still show rule-based example outlines, marked EXAMPLE. The numbers are a pilot, not final results."

| Time | Step | What to show | What to say |
|---|---|---|---|
| 0:00-0:40 | Data inspection | `docs/data_report.md` sections 2-4, 8 | 1,251 labeled training cases from 23 institutions (partitioning CSV) plus 219 unlabeled validation cases; all geometry-consistent, LPS on disk: situation A |
| 0:40-1:20 | Conversion | A montage (`data/processed/montage/FeTS2022_00153.png`); `tests/unit/test_orient.py` | Every volume becomes RAS. A planted voxel round-trips in Python and in the browser |
| 1:20-2:00 | Held-out evaluation (real, pilot) | Generalization page; `docs/model_card.md` | In-site versus held-out Dice per region with bootstrap intervals, risk-coverage and calibration on fold `mid`. Read the numbers from the page; say the sample is small and the intervals wide |
| 2:00-3:30 | Viewer | Home → **Open Imaging Workspace** → a labeled test case with a model prediction (e.g. a held-out case from the Review page) → display mode **MRI + segmentation**; then FeTS2022_00153 for an unlabeled EXAMPLE case; region toggles; **Pseudocolor** with a color map; zoom (Ctrl + wheel); 3D glass mode; cut-away; **Compare** page with two cases and the split view | Radiological display with R/L, A/P, S/I letters. The status bar shows the file's own voxel index and world millimetres. Pseudocolor is labeled as a display transform. Model outlines carry no EXAMPLE banner; the EXAMPLE banner on unlabeled cases says that outline is rule-based |
| 3:30-4:10 | Uncertainty and flag | Heat map, **Go to the most uncertain spot**, drag the review limit across the score | The flag is `score > limit` and nothing else. It flips exactly at the score |
| 4:10-4:40 | Review queue | Review page: sort order, Accept / Reject / Note, decision log | Decisions persist in SQLite |
| 4:40-5:00 | Close | Model card, requirements table, `docs/deviations.md` D15-D17 | What was cut for the deadline (4 more folds, 3 trained mitigations, seeds, 100 epochs; test-time adaptation needs no training) and that the same scripts run the full protocol on a larger GPU |

## Slide outline (8 slides)
1. Problem: silent accuracy loss at new hospitals. Applied track: nnU-Net + FeTS 2022.
2. Gaps G1-G4 and contributions C1-C4.
3. Architecture (docs/architecture.md diagram).
4. Requirements R1-R8 and how each is verified.
5. Protocol: five site groups, leakage rules, tau fixed in advance.
6. Uncertainty and trust gate: band score, fail-safe NaN, review-limit rule.
7. Pilot results (fold `mid`): in-site vs held-out Dice, failure-detection AUROC; what was built and verified versus what is "not run" and why.
8. Next steps: remaining folds and mitigations on a larger GPU; ethics and limitations.
