"""E4 calibration of uncertainty estimators (ECE).
Writes results/e4_calibration.json ("not run" with the reason when inputs are missing).

    python scripts/e4_calibration.py
"""

from btqc.eval.runs import ALL

if __name__ == "__main__":
    ALL["e4"]()
