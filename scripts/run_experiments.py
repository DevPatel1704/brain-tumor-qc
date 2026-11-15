"""Run experiments E1-E6 in order (Phase 6). Each writes results/e<N>_*.json.

    python scripts/run_experiments.py [--only e1 e5]
"""

import argparse

from btqc.eval.runs import ALL

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--only", nargs="*", default=None)
    a = ap.parse_args()
    for k, fn in ALL.items():
        if a.only is None or k in a.only:
            fn()
