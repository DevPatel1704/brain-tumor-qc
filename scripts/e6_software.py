"""E6 software requirements (tests, coverage, latency).
Writes results/e6_software.json ("not run" with the reason when inputs are missing).

    python scripts/e6_software.py
"""

from btqc.eval.runs import ALL

if __name__ == "__main__":
    ALL["e6"]()
