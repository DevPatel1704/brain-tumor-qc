"""E1 generalization gap per held-out group.
Writes results/e1_gap.json ("not run" with the reason when inputs are missing).

    python scripts/e1_gap.py
"""

from btqc.eval.runs import ALL

if __name__ == "__main__":
    ALL["e1"]()
