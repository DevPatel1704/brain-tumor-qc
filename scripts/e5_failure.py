"""E5 failure detection (AUROC, risk-coverage).
Writes results/e5_failure.json ("not run" with the reason when inputs are missing).

    python scripts/e5_failure.py
"""

from btqc.eval.runs import ALL

if __name__ == "__main__":
    ALL["e5"]()
