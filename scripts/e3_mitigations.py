"""E3 mitigation comparison (Wilcoxon, bootstrap).
Writes results/e3_mitigations.json ("not run" with the reason when inputs are missing).

    python scripts/e3_mitigations.py
"""

from btqc.eval.runs import ALL

if __name__ == "__main__":
    ALL["e3"]()
