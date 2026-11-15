"""Write RULE-BASED EXAMPLE prediction records for the dashboard (NOT A MODEL).

Every record has source="example"; the API and UI label it as an example.
These records must never be reported as segmentation results.

    python scripts/example_predictions.py [--max-cases N] [--cases ID ...]
"""

from __future__ import annotations

import argparse
import time

import nibabel as nib
import numpy as np

from btqc.config import load_config, resolve
from btqc.data.discover import SEQUENCES
from btqc.infer.example_rules import example_record
from btqc.infer.record import save_record


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--max-cases", type=int, default=None)
    ap.add_argument("--cases", nargs="*", default=None)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    cfg = load_config("serve")
    can = resolve(cfg["processed_root"]) / "canonical"
    out = resolve(cfg["predictions_root"]) / "example_rule_based" / "example"
    ids = a.cases or sorted(p.name for p in can.iterdir() if (p / "meta.json").exists())
    ids = ids[: a.max_cases]
    t0 = time.time()
    for i, cid in enumerate(ids):
        if (out / f"{cid}.npz").exists() and not a.force:
            continue
        vols = {}
        spacing: tuple[float, ...] = (1.0, 1.0, 1.0)
        for s in SEQUENCES:
            img = nib.load(str(can / cid / f"{cid}_{s}.nii.gz"))
            vols[s] = img.get_fdata(dtype=np.float32)
            spacing = tuple(float(z) for z in img.header.get_zooms()[:3])
        rec = example_record(cid, vols, spacing)
        save_record(rec, out)
        if (i + 1) % 10 == 0 or i + 1 == len(ids):
            print(f"  {i + 1}/{len(ids)} example records, {time.time() - t0:.0f}s", flush=True)
    print(f"wrote EXAMPLE (rule-based, not a model) records to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
