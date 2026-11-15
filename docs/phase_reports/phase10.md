# Phase 10 report: report and demo

**Data situation: C. Compute tier: 0.**

## What was done
- `docs/report/btqc_report.docx` and `.pdf`: an IEEE CS style technical report in Word (no LaTeX installed). 10 pages, about 6,800 words, 11 figures, 13 tables, 24 references.
  - Built by `scripts/build_report.py`, which reads every number at build time from `data/phase0_summary.json`, `data/processed/convert_log.json`, `results/*.json` and `results/ui_junit.xml`.
  - Sections: introduction and gaps, related work, system and architecture, requirements and traceability, methodology, implementation (with code snippets), evaluation and testing, software process and reproducibility, lessons learned, discussion (including threats to validity and the negative outcome), limitations, ethics, conclusion, references, appendix (deviations, reproduction, definition-of-done).
- References verified (DOIs resolve, arXiv titles match): `docs/report/reference_check.md`.
- `docs/demo.md`: a five-minute demonstration script and an 8-slide outline.
- Model card (`docs/model_card.md`, `results/model_card.json`) and README updated with the real status.

## Honesty checks
- H1-H3 are "not run", and the report says so plainly.
- Every synthetic figure carries "SYNTHETIC DATA - NOT A RESULT" in its title or caption.
- The rule-based outline on a real case is labeled EXAMPLE in the figure caption and in the UI.
- The HD95 penalty is described as a documented choice, not as the BraTS 2021 rule.
