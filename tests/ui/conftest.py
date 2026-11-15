"""Browser-test fixtures: a live API server on synthetic data and headless Chromium
with software WebGL (SwiftShader)."""

from __future__ import annotations

import socket
import threading
import time
from pathlib import Path

import nibabel as nib
import numpy as np
import pytest
import yaml

from btqc.config import REPO_ROOT
from btqc.data.convert import ConvertOptions, convert_all
from btqc.data.discover import discover
from btqc.data.fixtures import LPS_AFFINE, make_case, make_dataset
from btqc.data.manifest import load_institution_table
from btqc.data.sitegroups import assign_groups
from btqc.infer.record import save_record
from btqc.infer.stub import stub_record
from btqc.train.splits import make_folds

CHROMIUM_ARGS = ["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]
PLANTED = (5, 30, 11)  # original (file) voxel index of the marker in planted_t1.nii.gz


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


@pytest.fixture(scope="session")
def ui_data(tmp_path_factory) -> dict:
    tmp = tmp_path_factory.mktemp("ui")
    raw = tmp / "raw"
    make_dataset(raw, n_cases=6, shape=(40, 44, 32))
    proc = tmp / "processed"
    convert_all(discover(raw), ConvertOptions(out_root=proc, raw_root=raw, montage=False), workers=1)
    inst = load_institution_table(raw / "partitioning_synthetic.csv")
    ci = dict(zip(inst.case_id, inst.institution, strict=True))
    rules = yaml.safe_load((REPO_ROOT / "configs" / "sitegroups.yaml").read_text())["rules"]
    folds = make_folds(ci, assign_groups(ci, rules))
    preds = tmp / "predictions"
    can = proc / "canonical"
    for g, f in folds.items():
        for cid in f["heldout"]:
            seg = np.asarray(nib.load(str(can / cid / f"{cid}_seg.nii.gz")).dataobj).astype(np.uint8)
            brain = np.asarray(nib.load(str(can / cid / f"{cid}_flair.nii.gz")).dataobj) != 0
            save_record(stub_record(cid, seg, brain, (1.0, 1.0, 1.0), 0.6, g), preds / "stub" / g)
    # a local NIfTI file with a planted marker (LPS affine like the real data)
    c = make_case("planted", shape=(36, 40, 28))
    arr = c.images["t1"].copy()
    arr[PLANTED] = 30000
    files = tmp / "local"
    files.mkdir()
    nib.save(nib.Nifti1Image(arr, LPS_AFFINE), str(files / "planted_t1.nii.gz"))
    (files / "notes.txt").write_text("this is not an image")
    return {"proc": proc, "preds": preds, "files": files, "results": tmp / "results", "tmp": tmp}


@pytest.fixture(scope="session")
def server(ui_data) -> str:
    import uvicorn

    from btqc.serve.api import create_app
    from btqc.serve.review_log import ReviewLog
    from btqc.serve.store import Store

    # a synthetic eval summary so the explorer can show its labeled demo
    synth = REPO_ROOT / "results" / "eval_summary_synthetic.json"
    res = Path(ui_data["results"])
    res.mkdir(exist_ok=True)
    if synth.exists():
        (res / "eval_summary_synthetic.json").write_text(synth.read_text(encoding="utf-8"), encoding="utf-8")
    store = Store(ui_data["proc"], ui_data["preds"], res, None, ["stub"])
    app = create_app({"web_dir": str(REPO_ROOT / "web")}, store, ReviewLog(ui_data["tmp"] / "review.db"))
    port = _free_port()
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    th = threading.Thread(target=srv.run, daemon=True)
    th.start()
    for _ in range(100):
        if srv.started:
            break
        time.sleep(0.1)
    yield f"http://127.0.0.1:{port}"
    srv.should_exit = True


@pytest.fixture(scope="session")
def browser():
    pw = pytest.importorskip("playwright.sync_api")
    with pw.sync_playwright() as p:
        try:
            b = p.chromium.launch(headless=True, args=CHROMIUM_ARGS)
        except Exception as e:
            pytest.skip(f"chromium not installed: {e}")
        yield b
        b.close()


@pytest.fixture()
def page(browser):
    ctx = browser.new_context(viewport={"width": 1280, "height": 900})
    pg = ctx.new_page()
    pg.errors = []  # type: ignore[attr-defined]
    pg.on("console", lambda m: pg.errors.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    yield pg
    ctx.close()
