"""End-to-end on synthetic fixtures: convert -> folds -> stub predictor records ->
harness -> gap table, failure detection, risk-coverage, calibration -> API."""

import json

import nibabel as nib
import numpy as np
import pytest
import yaml
from fastapi.testclient import TestClient

from btqc.config import REPO_ROOT, load_config
from btqc.data.convert import ConvertOptions, convert_all
from btqc.data.discover import discover
from btqc.data.manifest import load_institution_table
from btqc.data.sitegroups import assign_groups
from btqc.eval.loso import CalibrationSet, LeakageError, evaluate_fold
from btqc.eval.summary import build_summary
from btqc.infer.record import save_record
from btqc.infer.stub import stub_record
from btqc.serve.api import create_app
from btqc.serve.review_log import ReviewLog
from btqc.serve.store import Store
from btqc.train.splits import check_folds, make_folds


@pytest.fixture(scope="module")
def pipeline(synthetic_root, tmp_path_factory):
    tmp = tmp_path_factory.mktemp("e2e")
    proc = tmp / "processed"
    convert_all(discover(synthetic_root), ConvertOptions(out_root=proc, raw_root=synthetic_root, montage=False),
                workers=1)
    inst = load_institution_table(synthetic_root / "partitioning_synthetic.csv")
    ci = dict(zip(inst.case_id, inst.institution, strict=True))
    rules = yaml.safe_load((REPO_ROOT / "configs" / "sitegroups.yaml").read_text())["rules"]
    cg = assign_groups(ci, rules)
    folds = make_folds(ci, cg, seed=3)
    assert check_folds(folds, cg) == []
    preds = tmp / "predictions"
    can = proc / "canonical"
    for g, f in folds.items():
        for split in ("val", "insite_test", "heldout"):
            for k, cid in enumerate(f[split]):
                img = nib.load(str(can / cid / f"{cid}_seg.nii.gz"))
                seg = np.asarray(img.dataobj).astype(np.uint8)
                brain = np.asarray(nib.load(str(can / cid / f"{cid}_flair.nii.gz")).dataobj) != 0
                diff = 0.8 if split == "heldout" else 0.1
                save_record(stub_record(cid, seg, brain, (1.0, 1.0, 1.0), diff, g, seed=k), preds / "stub" / g)
    return {"proc": proc, "folds": folds, "ci": ci, "preds": preds, "tmp": tmp}


def test_harness_gap_failure_and_summary(pipeline):
    rows, calib = [], {}
    for g, f in pipeline["folds"].items():
        cs = CalibrationSet()
        rows.append(evaluate_fold("stub", g, f, pipeline["preds"] / "stub" / g, pipeline["proc"] / "canonical",
                                  pipeline["ci"], "brats_124", calib=cs))
        calib[("stub", g)] = cs
    import pandas as pd

    df = pd.concat(rows)
    assert (df.status == "ok").all()
    summ = build_summary(df, calib, load_config("uncertainty"), load_config("eval"), "synthetic", "test")
    gaps = [r for r in summ["gaps"] if r["metric"] == "dice" and r["region"] == "WT"]
    assert gaps and all(r["gap"] > 0 for r in gaps if r["n_heldout"] and r["n_insite"])  # harder held-out stub
    assert summ["risk_coverage"] and summ["reliability"]
    json.dumps(summ)  # valid JSON (no NaN)
    assert any(r.get("review_limit") is not None for r in summ["failure"])


def test_leakage_guard(pipeline, tmp_path):
    """A record produced by another fold's models must not be scored for this fold."""
    import shutil

    g, other = sorted(pipeline["folds"])[:2]
    cid = pipeline["folds"][g]["heldout"][0]
    d = tmp_path / g
    d.mkdir()
    shutil.copy(pipeline["preds"] / "stub" / g / f"{cid}.npz", d / f"{cid}.npz")
    meta = json.loads((pipeline["preds"] / "stub" / g / f"{cid}.json").read_text())
    meta["fold"] = other
    (d / f"{cid}.json").write_text(json.dumps(meta))
    with pytest.raises(LeakageError):
        evaluate_fold("stub", g, {"heldout": [cid]}, d, pipeline["proc"] / "canonical", pipeline["ci"], "brats_124",
                      splits=("heldout",))


@pytest.fixture()
def client(pipeline, tmp_path):
    store = Store(pipeline["proc"], pipeline["preds"], tmp_path / "results", None, ["stub"])
    app = create_app({"web_dir": str(tmp_path / "noweb"), "max_upload_mb": 1}, store, ReviewLog(tmp_path / "r.db"))
    return TestClient(app)


def test_api_cases_volume_prediction_and_flag(client, pipeline):
    r = client.get("/api/cases")
    assert r.status_code == 200 and r.headers["X-Research-Prototype"] == "not a medical device"
    cases = r.json()["cases"]
    assert len(cases) == 12 and all(c["has_reference"] for c in cases)
    cid = next(c["id"] for c in cases if c["has_prediction"])
    v = client.get(f"/api/cases/{cid}/volume/flair")
    meta = json.loads(v.headers["X-Btqc-Meta"])
    import gzip

    raw = gzip.decompress(v.content)
    assert len(raw) == int(np.prod(meta["dims"])) and meta["orientation"] == "RAS"
    p = client.get(f"/api/cases/{cid}/prediction").json()
    assert p["source"] == "synthetic" and p["is_example"] is True and p["example_note"]
    s = p["score"]
    hi = client.get(f"/api/cases/{cid}/prediction", params={"review_limit": min(1.0, s + 0.01)}).json()
    lo = client.get(f"/api/cases/{cid}/prediction", params={"review_limit": max(0.0, s - 0.01)}).json()
    assert hi["flag"] is False and lo["flag"] is True
    lab = client.get(p["labels_url"])
    assert len(gzip.decompress(lab.content)) == int(np.prod(meta["dims"]))
    assert client.get(p["uncertainty_url"]).status_code == 200


def test_api_thumbnail_png_and_cache(client, pipeline):
    cid = next(c["id"] for c in client.get("/api/cases").json()["cases"] if c["has_prediction"])
    r = client.get(f"/api/cases/{cid}/thumbnail")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    assert r.content[:8] == b"\x89PNG\r\n\x1a\n"
    w, h = int.from_bytes(r.content[16:20], "big"), int.from_bytes(r.content[20:24], "big")
    assert (w, h) == (96, 96)
    assert (pipeline["proc"] / "thumbs" / f"{cid}_96.png").exists()
    assert client.get(f"/api/cases/{cid}/thumbnail").content == r.content
    assert client.get("/api/cases/nope_case/thumbnail").status_code == 404
    assert client.get("/api/cases/..%2Fetc/thumbnail").status_code == 404


def test_thumbnail_is_radiological_with_outline():
    from btqc.serve.thumbs import render_thumbnail

    img = np.zeros((40, 50, 10), np.uint8)
    img[5:35, 5:45, :] = 100
    img[30:35, 5:10, :] = 250  # patient right (high x), posterior (low y)
    seg = np.zeros_like(img)
    seg[15:25, 20:30, 4:7] = 2
    t = render_thumbnail(img, seg, 32)
    assert t.shape == (32, 32, 3) and t.dtype == np.uint8
    # bright block: screen left (patient right), bottom (posterior)
    bright = np.argwhere(t[:, :, 0].astype(int) > 200)
    assert bright[:, 1].mean() < 16 and bright[:, 0].mean() > 16
    green = (t[:, :, 1] == 189) & (t[:, :, 0] == 46)
    assert green.any()


def test_api_rejects_bad_ids_and_limits(client):
    assert client.get("/api/cases/../etc/volume/t1").status_code == 404
    assert client.get("/api/cases/FeTS2022_00000/volume/t5").status_code == 404
    assert client.get("/api/cases/nope/prediction").status_code == 404
    assert client.get("/api/cases", params={"review_limit": 3}).status_code == 422


def test_api_reviews_persist(client):
    r = client.post("/api/review", json={"case_id": "FeTS2022_00001", "decision": "reject", "note": "edge"})
    assert r.status_code == 200 and r.json()["decision"] == "reject"
    assert client.post("/api/review", json={"case_id": "FeTS2022_00001", "decision": "maybe"}).status_code == 422
    assert client.post("/api/review", json={"case_id": "unknown_case", "decision": "accept"}).status_code == 404
    assert client.post("/api/review", json={"case_id": "FeTS2022_00001", "decision": "note",
                                            "note": "x" * 2001}).status_code == 422
    rows = client.get("/api/review").json()
    assert rows[-1]["case_id"] == "FeTS2022_00001"
    listed = {c["id"]: c["review"] for c in client.get("/api/cases").json()["cases"]}
    assert listed["FeTS2022_00001"] == "reject"


def test_api_eval_not_run_and_predict_disabled(client):
    assert client.get("/api/eval/summary").json()["status"] == "not run"
    files = {k: (f"{k}.nii", b"not a nifti", "application/octet-stream") for k in ("t1", "t1ce", "t2", "flair")}
    assert client.post("/api/predict", files=files).status_code == 503


def test_upload_validation_rejects_non_nifti():
    from fastapi import HTTPException

    from btqc.serve.api import validate_nifti_bytes

    with pytest.raises(HTTPException) as e:
        validate_nifti_bytes(b"hello world" * 100, "t1")
    assert e.value.status_code == 400
    img = nib.Nifti1Image(np.zeros((4, 4, 4), np.int16), np.eye(4))
    validate_nifti_bytes(img.to_bytes(), "t1")
    with pytest.raises(HTTPException):
        validate_nifti_bytes(nib.Nifti1Image(np.zeros((4, 4), np.int16), np.eye(4)).to_bytes(), "t1")


def test_logs_have_no_case_ids(client, caplog):
    import logging

    caplog.set_level(logging.INFO, logger="btqc.api")
    client.get("/api/cases/FeTS2022_00003/volume/t1")
    msgs = " ".join(r.getMessage() for r in caplog.records)
    assert "FeTS2022_00003" not in msgs and "{case_id}" in msgs
