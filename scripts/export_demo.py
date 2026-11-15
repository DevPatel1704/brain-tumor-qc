"""Build a single self-contained HTML demo (Phase 7, item 9).

Embeds one or two cases (cropped to the brain bounding box, canonical RAS,
gzip + base64), their prediction records (model output if available,
otherwise the rule-based EXAMPLE records, which the page labels as examples),
the CSS and the viewer's JS modules (bundled by a small deterministic module wrapper).
No network access at runtime. Output: dist/btqc_demo.html

    python scripts/export_demo.py [--cases FeTS2022_00001 ...] [--max-mb 15]
"""

from __future__ import annotations

import argparse
import base64
import gzip
import json
import re

import numpy as np

from btqc import DISCLAIMER
from btqc.config import REPO_ROOT, load_config, resolve
from btqc.data.convert import read_bundle
from btqc.serve.store import EXAMPLE_NOTE, Store
from btqc.uncertainty.gate import decide

WEB = REPO_ROOT / "web"
ENTRY = "app"
MODULE_ORDER = ["colors", "gate", "ui", "colormaps", "geometry", "nifti", "data", "nav", "render3d", "viewer", "app"]
IMPORT_RE = re.compile(r"^import\s*\{([^}]*)\}\s*from\s*'\./([a-z0-9]+)\.js';\s*$", re.M)
EXPORT_RE = re.compile(r"^export\s+(async\s+function|function|class|const|let)\s+([A-Za-z0-9_$]+)", re.M)
DYN_RE = re.compile(r"await import\('\./([a-z0-9]+)\.js'\)")


def bundle_modules() -> str:
    parts = ["const __m = {};"]
    for name in MODULE_ORDER:
        src = (WEB / "src" / f"{name}.js").read_text(encoding="utf-8")
        exports = [m.group(2) for m in EXPORT_RE.finditer(src)]

        def imp(m: re.Match[str]) -> str:
            names = ", ".join(n.strip().replace(" as ", ": ") for n in m.group(1).split(",") if n.strip())
            return f"const {{ {names} }} = __m['{m.group(2)}'];"

        src = IMPORT_RE.sub(imp, src)
        src = DYN_RE.sub(lambda m: f"__m['{m.group(1)}']", src)
        src = EXPORT_RE.sub(lambda m: f"{m.group(1)} {m.group(2)}", src)
        if re.search(r"^\s*(import|export)\s", src, re.M):
            raise RuntimeError(f"{name}.js has an import/export form the bundler does not handle")
        parts.append(f"__m['{name}'] = (() => {{\n{src}\nreturn {{ {', '.join(exports)} }};\n}})();")
    return "\n".join(parts)


def b64gz(arr: np.ndarray) -> str:
    return base64.b64encode(gzip.compress(np.asarray(arr, np.uint8).ravel(order="F").tobytes(), 9)).decode("ascii")


def crop_box(flair: np.ndarray, margin: int = 2) -> tuple[slice, slice, slice]:
    idx = np.argwhere(flair > 0)
    lo = np.maximum(idx.min(0) - margin, 0)
    hi = np.minimum(idx.max(0) + margin + 1, flair.shape)
    return (slice(int(lo[0]), int(hi[0])), slice(int(lo[1]), int(hi[1])), slice(int(lo[2]), int(hi[2])))


def embed_case(store: Store, cid: str, limit: float) -> dict:
    vdir = store.viewer / cid
    flair, meta = read_bundle(vdir, "flair")
    box = crop_box(flair)
    off = [s.start for s in box]
    seqs = {}
    for s in ("t1", "t1ce", "t2", "flair"):
        arr, _ = read_bundle(vdir, s)
        seqs[s] = b64gz(arr[box])
    m = dict(meta)
    m["dims"] = [s.stop - s.start for s in box]
    m["crop_offset"] = off
    out = {"meta": m, "seqs": seqs, "group": store.groups.get(cid)}
    if (vdir / "seg.json").exists():
        out["reference"] = b64gz(read_bundle(vdir, "seg")[0][box])
    got = store.prediction(cid)
    if got is not None:
        method, fold, rec = got
        score = rec.meta.get("scores", {}).get("boundary_band")
        d = decide(score, limit)
        shift = lambda p: [int(v) - o for v, o in zip(p, off)] if p is not None else None  # noqa: E731
        out["labels"] = b64gz(rec.seg[box])
        out["unc"] = b64gz(rec.unc[box])
        out["prediction"] = {
            "case_id": cid, "method": method, "fold": fold, "source": rec.source, "is_example": rec.source != "model",
            "example_note": EXAMPLE_NOTE if rec.source != "model" else None, "score": score,
            "flag": d.flag, "flag_label": d.label, "reason": d.reason,
            "volumes_ml": rec.meta.get("volumes_ml"), "hemisphere": rec.meta.get("hemisphere"),
            "hot_spot": shift(rec.meta.get("hot_spot")),
            "centroid": shift(rec.meta.get("centroid")),
        }
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cases", nargs="*", default=None)
    ap.add_argument("--max-mb", type=float, default=15.0)
    ap.add_argument("--out", default="dist/btqc_demo.html")
    a = ap.parse_args(argv)
    cfg = load_config("serve")
    store = Store(resolve(cfg["processed_root"]), resolve(cfg["predictions_root"]), resolve(cfg["results_dir"]),
                  resolve(cfg["sitegroups"]), list(cfg["methods"]))
    limit = float(load_config("uncertainty")["gate"]["default_review_limit"])
    ids = a.cases or [c for c in store.case_ids() if store.find_prediction(c)][:2] or store.case_ids()[:1]
    embed = {"disclaimer": DISCLAIMER, "review_limit": limit, "cases": {c: embed_case(store, c, limit) for c in ids},
             "eval": store.eval_summary(), "site_risk": store.json_result("site_risk.json"),
             "model_card": store.json_result("model_card.json")}
    html = (WEB / "viewer.html").read_text(encoding="utf-8")
    css = (WEB / "styles.css").read_text(encoding="utf-8")
    html = html.replace('<link rel="stylesheet" href="styles.css">', f"<style>\n{css}\n</style>")
    html = html.replace("<title>BTQC · Imaging workspace</title>", "<title>BTQC · single-file demo</title>")
    data = json.dumps(embed, separators=(",", ":")).replace("</", "<\\/")
    script = f"<script>window.BTQC_EMBED = {data};</script>\n<script type=\"module\">\n{bundle_modules()}\n</script>"
    html = html.replace('<script type="module" src="src/app.js"></script>', script)
    out = REPO_ROOT / a.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    mb = out.stat().st_size / 2**20
    print(f"wrote {out} ({mb:.1f} MB) with cases {ids}")
    if mb > a.max_mb:
        print(f"warning: larger than {a.max_mb} MB; export fewer cases")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
