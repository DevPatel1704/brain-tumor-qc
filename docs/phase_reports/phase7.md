# Phase 7 report: dashboard

**Data situation: C. Compute tier: 0.**

## What was done
- **Reuse.** Both prototypes (`Brain MRI viewer.html` and `Brain MRI viewer, finished-app example.html`, found in Downloads) were refactored into ES modules: `nifti.js` (reader and orienter), `viewer.js` (slice views), `render3d.js` (WebGL 2 ray caster), `colors.js`. The reorientation rule is the same as `orient.py`. The Google Fonts link was removed (no runtime network), and the intensity mapping now keeps dark tissue distinct from background, matching the Python bundles.
- **Backend** (`btqc.serve`): every endpoint from the brief. `/api/predict` returns 503 unless a GPU and a model are configured. NIfTI uploads are validated, case ids are sanitized, review limits are range-checked, and logs record route templates only. A SQLite review log was added.
- **Pages:**
  - Viewer: case picker, local files, 3 views, 3D, overlays, report with flag, "go to most uncertain spot", volumes, hemisphere.
  - Review queue.
  - Generalization explorer (filters, 6 charts, synthetic demo toggle).
  - Site risk.
  - Model card.

  The disclaimer is shown on every page.
- **Charts:** validated palette slots 1-3 (`validate_palette.js`: all checks pass in light and dark mode; aqua is below 3:1 contrast on light, so direct labels and table views are provided). Bars anchor at zero, NaN values render as "not defined" with the reason, and every chart has hover tooltips.
- **Export:** `scripts/export_demo.py` bundles the modules and embeds case `FeTS2022_00153`, cropped to the brain box with the crop offset kept for exact file indices, plus its EXAMPLE record. The result is `dist/btqc_demo.html` (6.4 MB) and needs no network.

## Real-data run
- API on the 219 validation cases: all have EXAMPLE records; 113 are flagged at limit 0.25.
- Screenshots in `results/screenshots/`: real-case viewer with the EXAMPLE banner, hot spot, review queue, site risk, model card, and mobile at 390 px (scrollWidth 390).
- After fixes, no console errors. Fixes made: no reference request for unlabeled cases, an inline favicon, and right-aligned numeric headers.

## Problems found by looking at screenshots
1. Gap bars were anchored at the axis edge rather than at zero.
2. The failure panel listed three score types and showed only "–" (AUROC undefined).
3. End labels overlapped.

All three are fixed and re-checked.

## Next step
Phase 8 (optional modules) and Phase 9 (QA).
