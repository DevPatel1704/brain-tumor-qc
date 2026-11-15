# Phase 2 report: repository, environment, CI

**Data situation: C. Compute tier: 0.**

## What was done
- Repository `brain-tumor-qc/` with package `btqc` (src layout), configs, web, tests, docker, docs and scripts, as specified in the brief.
- Environment: Python 3.12.8 venv. Pinned in `requirements.lock` (torch 2.15.0+cpu, nnunetv2 2.8.1, nibabel 5.4.2, numpy 2.5.4, fastapi 0.162.0, mlflow 3.17.2, playwright 1.64.1, ...). `requirements-ci.txt` carries platform markers for Windows-only packages.
- Makefile targets `data-report convert nnunet-prep train-smoke train-loso infer uncertainty eval app export-demo test docs` (plus `sitegroups example-predictions site-risk fixtures lint test-ui test-all`). All delegate to `scripts/tasks.py`, because `make` is not installed on this Windows machine.
- CI (`.github/workflows/ci.yml`): ruff + mypy, tests with coverage, Playwright browser tests, and a Docker build. All jobs use synthetic fixtures only, with no data and no GPU.
- `docs/requirements.md`: R1-R8 traced to tests.
- Pre-commit config (ruff, YAML check, large-file guard), `.gitignore` (no data, checkpoints, runs or databases), `.gitattributes` (LF line endings).

## Gate G2
- `python scripts/tasks.py test` passes locally. The final numbers are in `results/e6_software.json` and the Phase 9 report.
- The CI workflow file parses as valid YAML. It could not be executed on GitHub from here: there is no remote, and pushing needs your approval.

## Deviations
- The Makefile wraps the Python task runner (D10 in `docs/deviations.md`).
- The Docker image build was not run locally. Docker Desktop is installed but the image was not built, to save time and disk; the CI job builds it.

## Next step
Phase 3: site groups, folds, baseline and the smoke test.
