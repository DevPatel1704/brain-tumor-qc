"""E2 shift metrics vs gap (Spearman).
Writes results/e2_shift.json ("not run" with the reason when inputs are missing).

    python scripts/e2_shift.py
"""

from btqc.eval.runs import ALL

if __name__ == "__main__":
    ALL["e2"]()
