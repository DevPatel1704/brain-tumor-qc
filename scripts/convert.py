"""Phase 1: convert the raw data root (read-only) into data/processed.

    python scripts/convert.py [--config data] [--max-cases N] [--workers 2] [--force] [--no-montage]
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter

from btqc.config import load_config, raw_root, resolve
from btqc.data.convert import ConvertOptions, convert_all
from btqc.data.discover import discover


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="data")
    ap.add_argument("--raw-root", default=None, help="override raw root (e.g. synthetic fixtures)")
    ap.add_argument("--out", default=None, help="override processed root")
    ap.add_argument("--max-cases", type=int, default=None)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--no-montage", action="store_true")
    ap.add_argument("--slices2d", action="store_true")
    a = ap.parse_args(argv)
    cfg = load_config(a.config)
    root = resolve(a.raw_root) if a.raw_root else raw_root(cfg)
    out = resolve(a.out or cfg["processed_root"])
    opt = ConvertOptions(out_root=out, raw_root=root, window_percentiles=tuple(cfg["viewer_window_percentiles"]),
                         montage=not a.no_montage, force=a.force, slices2d=a.slices2d)
    disc = discover(root)
    t0 = time.time()

    def prog(i: int, n: int, r: dict) -> None:
        if r["status"] not in ("converted", "skipped"):
            print(f"  {r}")
        if i % 10 == 0 or i == n:
            el = time.time() - t0
            print(f"  {i}/{n} cases, {el:.0f}s elapsed, est. {el / i * (n - i):.0f}s left", flush=True)

    print(f"converting {min(len(disc.cases), a.max_cases or 10**9)} cases from {root} -> {out}")
    res = convert_all(disc, opt, workers=a.workers, max_cases=a.max_cases, progress=prog)
    counts = Counter(r["status"] for r in res)
    log = out / "convert_log.json"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(json.dumps({"raw_root": str(root), "counts": counts, "results": res,
                               "elapsed_s": round(time.time() - t0, 1)}, indent=1), encoding="utf-8")
    print(f"done: {dict(counts)} in {time.time() - t0:.0f}s; log {log}")
    return 0 if not (counts.get("error") or counts.get("grid_mismatch")) else 1


if __name__ == "__main__":
    raise SystemExit(main())
