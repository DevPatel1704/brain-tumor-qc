"""E2 (embedding part): Frechet distance between encoder-bottleneck features of each site group and the rest
of the training pool, using the trained baseline model of one fold.

Features: the trained nnU-Net encoder is applied to a centred patch of each case's preprocessed
(nnU-Net-normalized) arrays; the bottleneck is global-average-pooled to one vector per case. For each site
group g the reference is the fold's training pool without g's cases, so the held-out group and the in-training
groups are measured the same way. Writes results/e2_embedding_shift.json.

    python scripts/embedding_shift.py --fold mid --per-group 30
"""

from __future__ import annotations

import argparse
import json
import os
import random
import time

import numpy as np

from btqc.config import REPO_ROOT, load_config, resolve
from btqc.eval.shift import frechet_distance
from btqc.train.nnunet_setup import dataset_name, nnunet_env


def centre_patch(a: np.ndarray, patch: list[int]) -> np.ndarray:
    """(C, z, y, x) -> centred (C, *patch), zero-padded where the case is smaller."""
    out = np.zeros((a.shape[0], *patch), dtype=np.float32)
    src, dst = [], []
    for n, p in zip(a.shape[1:], patch):
        if n >= p:
            s = (n - p) // 2
            src.append(slice(s, s + p))
            dst.append(slice(0, p))
        else:
            s = (p - n) // 2
            src.append(slice(0, n))
            dst.append(slice(s, s + n))
    out[(slice(None), *dst)] = a[(slice(None), *src)]
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fold", default="mid")
    ap.add_argument("--per-group", type=int, default=30)
    ap.add_argument("--device", default="cuda")
    a = ap.parse_args(argv)
    for k, v in nnunet_env(REPO_ROOT).items():
        os.environ.setdefault(k, v)
    import blosc2
    import torch
    from nnunetv2.inference.predict_from_raw_data import nnUNetPredictor

    tcfg, dcfg = load_config("train"), load_config("data")
    fj = json.loads((REPO_ROOT / "data" / "splits" / "folds.json").read_text())
    sg = json.loads((REPO_ROOT / "data" / "sitegroups.json").read_text())
    order, folds, case_group = fj["fold_order"], fj["folds"], sg["case_group"]
    fold_idx = order.index(a.fold) * int(fj["meta"]["n_members"])
    dsname = dataset_name(int(tcfg["dataset"]["id"]), tcfg["dataset"]["name"])
    model_dir = (resolve(dcfg["nnunet_results"]) / dsname /
                 f"nnUNetTrainer_btqc__{tcfg['plans']}__{tcfg['configuration']}")
    pre = resolve(dcfg["nnunet_preprocessed"]) / dsname
    plans = json.loads((pre / f"{tcfg['plans']}.json").read_text())
    cfg = plans["configurations"][tcfg["configuration"]]
    data_dir = pre / cfg["data_identifier"]
    patch = cfg["patch_size"]

    dev = torch.device(a.device if torch.cuda.is_available() else "cpu")
    pred = nnUNetPredictor(device=dev, verbose=False, allow_tqdm=False)
    pred.initialize_from_trained_model_folder(str(model_dir), use_folds=(fold_idx,),
                                              checkpoint_name="checkpoint_final.pth")
    net = getattr(pred.network, "_orig_mod", pred.network)
    net.load_state_dict(pred.list_of_parameters[0])
    net.to(dev).eval()

    f = folds[a.fold]
    pool = set(f["train"])
    groups = {g: sorted(c for c in pool if case_group.get(c) == g) for g in order if g != a.fold}
    groups[a.fold] = sorted(f["heldout"])
    rng = random.Random(int(tcfg["seed"]))
    sample = {g: sorted(rng.sample(cs, min(a.per_group, len(cs)))) for g, cs in groups.items()}

    feats: dict[str, np.ndarray] = {}
    t0 = time.time()
    with torch.no_grad():
        for g, cs in sample.items():
            rows = []
            for cid in cs:
                arr = np.asarray(blosc2.open(str(data_dir / f"{cid}.b2nd"), mode="r")[:], dtype=np.float32)
                x = torch.from_numpy(centre_patch(arr, patch))[None].to(dev)
                with torch.autocast(dev.type, enabled=dev.type == "cuda"):
                    skips = net.encoder(x)
                rows.append(skips[-1].float().mean(dim=(2, 3, 4))[0].cpu().numpy())
            feats[g] = np.stack(rows)
            print(f"{g}: {len(cs)} cases, feature dim {feats[g].shape[1]}", flush=True)

    rows_out = []
    for g in sample:
        ref = np.concatenate([feats[h] for h in sample if h not in (g, a.fold)])
        rows_out.append({"group": g, "role": "held-out" if g == a.fold else "in training",
                         "n": len(feats[g]), "n_reference": len(ref),
                         "frechet": frechet_distance(feats[g], ref)})
        print(f"  {g:10s} FD = {rows_out[-1]['frechet']:.3f}", flush=True)
    out = {"status": "ok", "fold": a.fold, "per_group": a.per_group, "patch": patch,
           "feature": "global-average-pooled encoder bottleneck of the trained baseline",
           "reference": "fold training pool without the group's own cases",
           "rows": rows_out, "seconds": round(time.time() - t0, 1)}
    (REPO_ROOT / "results" / "e2_embedding_shift.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("wrote results/e2_embedding_shift.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
