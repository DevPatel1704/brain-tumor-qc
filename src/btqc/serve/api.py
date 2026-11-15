"""FastAPI backend (local-first). Run: ``uvicorn btqc.serve.api:create_app --factory`` or ``make app``.

Privacy (R6): no third-party calls are made; logs contain request method,
route template and status only (no query strings, file names or headers);
uploaded files are validated, size-limited, and their names are discarded.
"""

from __future__ import annotations

import gzip
import json
import logging
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Any

import numpy as np
from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from btqc import DISCLAIMER, __version__
from btqc.config import load_config, resolve
from btqc.serve.review_log import ReviewLog
from btqc.serve.schemas import (
    CaseList,
    CaseSummary,
    JobOut,
    PredictionInfo,
    RegionVolumes,
    ReviewIn,
    ReviewOut,
)
from btqc.serve.store import EXAMPLE_NOTE, NotFound, Store, safe_id
from btqc.serve.thumbs import case_thumbnail
from btqc.uncertainty.gate import decide

log = logging.getLogger("btqc.api")


def _default_limit() -> float:
    try:
        return float(load_config("uncertainty")["gate"]["default_review_limit"])
    except (OSError, KeyError):
        return 0.25


def create_app(cfg: dict[str, Any] | None = None, store: Store | None = None,
               reviews: ReviewLog | None = None) -> FastAPI:
    cfg = cfg or load_config("serve")
    store = store or Store(
        resolve(cfg["processed_root"]), resolve(cfg["predictions_root"]), resolve(cfg["results_dir"]),
        resolve(cfg["sitegroups"]) if cfg.get("sitegroups") else None, list(cfg.get("methods", ["baseline"])),
    )
    reviews = reviews or ReviewLog(resolve(cfg["review_db"]))
    default_limit = float(cfg.get("default_review_limit", _default_limit()))
    max_upload = int(cfg.get("max_upload_mb", 64)) * 2**20
    jobs: dict[str, dict[str, Any]] = {}

    app = FastAPI(title="btqc", version=__version__, description=DISCLAIMER)
    app.state.store = store
    app.state.reviews = reviews

    @app.middleware("http")
    async def privacy_log(request: Request, call_next):  # type: ignore[no-untyped-def]
        resp = await call_next(request)
        route = request.scope.get("route")
        log.info("%s %s -> %s", request.method, getattr(route, "path", "<static>"), resp.status_code)
        resp.headers["X-Research-Prototype"] = "not a medical device"
        resp.headers["Cache-Control"] = "no-store"
        return resp

    def limit_or_default(v: float | None) -> float:
        if v is None:
            return default_limit
        if not 0.0 <= v <= 1.0:
            raise HTTPException(422, "review_limit must be between 0 and 1")
        return v

    def summary(cid: str, limit: float, latest: dict[str, str]) -> CaseSummary:
        meta = store.prediction_meta(cid)
        s = CaseSummary(id=cid, group=store.groups.get(cid), sequences=store.sequences(cid),
                        has_reference=store.has_reference(cid), has_prediction=meta is not None,
                        review=latest.get(cid))
        if meta:
            score = meta.get("scores", {}).get("boundary_band")
            d = decide(score, limit)
            s.prediction_source = meta.get("source")
            s.score = None if score is None or (isinstance(score, float) and np.isnan(score)) else float(score)
            s.flag, s.flag_label = d.flag, d.label
            s.volumes_ml = RegionVolumes(**meta.get("volumes_ml", {}))
        return s

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "version": __version__, "disclaimer": DISCLAIMER}

    @app.get("/api/cases", response_model=CaseList)
    def cases(review_limit: float | None = Query(None)) -> CaseList:
        lim = limit_or_default(review_limit)
        latest = reviews.latest_by_case()
        return CaseList(review_limit=lim, disclaimer=DISCLAIMER,
                        cases=[summary(c, lim, latest) for c in store.case_ids()])

    def _gz_response(data: bytes, meta: dict[str, Any]) -> Response:
        return Response(content=data, media_type="application/gzip",
                        headers={"X-Btqc-Meta": json.dumps(meta, separators=(",", ":"))})

    @app.get("/api/cases/{case_id}/volume/{sequence}")
    def volume(case_id: str, sequence: str) -> Response:
        try:
            p, meta = store.bundle(case_id, sequence)
        except NotFound:
            raise HTTPException(404, "unknown case or sequence") from None
        return _gz_response(p.read_bytes(), meta)

    @app.get("/api/cases/{case_id}/volume/{sequence}/meta")
    def volume_meta(case_id: str, sequence: str) -> dict[str, Any]:
        try:
            return store.bundle(case_id, sequence)[1]
        except NotFound:
            raise HTTPException(404, "unknown case or sequence") from None

    @app.get("/api/cases/{case_id}/thumbnail")
    def thumbnail(case_id: str) -> Response:
        try:
            data = case_thumbnail(store, case_id)
        except NotFound:
            raise HTTPException(404, "unknown case") from None
        return Response(content=data, media_type="image/png")

    @app.get("/api/cases/{case_id}/prediction", response_model=PredictionInfo)
    def prediction(case_id: str, review_limit: float | None = Query(None)) -> PredictionInfo:
        try:
            safe_id(case_id)
        except NotFound:
            raise HTTPException(404, "unknown case") from None
        meta = store.prediction_meta(case_id)
        if meta is None:
            raise HTTPException(404, "no prediction for this case")
        lim = limit_or_default(review_limit)
        scores = {k: (None if v is None or np.isnan(v) else float(v)) for k, v in meta.get("scores", {}).items()}
        d = decide(scores.get("boundary_band"), lim)
        is_example = meta.get("source") != "model"
        base = f"/api/cases/{case_id}/prediction"
        return PredictionInfo(
            case_id=case_id, method=meta["method"], fold=str(meta["fold"]), source=meta.get("source", "unknown"),
            is_example=is_example, example_note=EXAMPLE_NOTE if is_example else None,
            score=scores.get("boundary_band"), scores=scores, flag=d.flag, flag_label=d.label, reason=d.reason,
            review_limit=lim, volumes_ml=RegionVolumes(**meta.get("volumes_ml", {})),
            hemisphere=meta.get("hemisphere"), hot_spot=meta.get("hot_spot"), centroid=meta.get("centroid"),
            labels_url=f"{base}/labels", uncertainty_url=f"{base}/uncertainty", labels_meta_url=f"{base}/labels/meta",
            metrics=meta.get("metrics"),
        )

    @app.get("/api/cases/{case_id}/prediction/{kind}")
    def prediction_volume(case_id: str, kind: str) -> Response:
        try:
            data, meta = store.prediction_bundle(case_id, kind)
        except NotFound:
            raise HTTPException(404, "no prediction volume") from None
        return _gz_response(data, meta)

    @app.get("/api/cases/{case_id}/prediction/{kind}/meta")
    def prediction_volume_meta(case_id: str, kind: str) -> dict[str, Any]:
        try:
            return store.prediction_bundle(case_id, kind)[1]
        except NotFound:
            raise HTTPException(404, "no prediction volume") from None

    @app.get("/api/eval/summary")
    def eval_summary() -> dict[str, Any]:
        return store.eval_summary()

    @app.get("/api/site-risk")
    def site_risk() -> dict[str, Any]:
        r = store.json_result("site_risk.json")
        if r is None:
            return {"status": "not run", "message": "Run `make site-risk` to compute shift metrics for a batch."}
        return r

    @app.get("/api/model-card")
    def model_card() -> dict[str, Any]:
        r = store.json_result("model_card.json")
        return r or {"status": "not run", "disclaimer": DISCLAIMER}

    @app.post("/api/review", response_model=ReviewOut)
    def add_review(item: ReviewIn) -> ReviewOut:
        if item.case_id not in store.case_ids():
            raise HTTPException(404, "unknown case")
        meta = store.prediction_meta(item.case_id) or {}
        score = meta.get("scores", {}).get("boundary_band")
        row = reviews.add(item.case_id, item.decision, item.note, item.reviewer,
                          None if score is None or np.isnan(score) else float(score), default_limit)
        return ReviewOut(**row)

    @app.get("/api/review", response_model=list[ReviewOut])
    def list_reviews(case_id: str | None = Query(None, pattern=r"^[A-Za-z0-9_\-]{1,64}$")) -> list[ReviewOut]:
        return [ReviewOut(**r) for r in reviews.list(case_id)]

    def _gpu_ready() -> tuple[bool, str]:
        if not cfg.get("model_folder"):
            return False, "no trained model is configured (serve.yaml: model_folder)"
        try:
            import torch
        except ImportError:
            return False, "torch is not installed"
        if not torch.cuda.is_available() and not cfg.get("allow_cpu_inference"):
            return False, "no CUDA GPU available"
        return True, ""

    @app.post("/api/predict", response_model=JobOut)
    async def predict(t1: UploadFile = File(...), t1ce: UploadFile = File(...), t2: UploadFile = File(...),
                      flair: UploadFile = File(...)) -> JobOut:
        ok, why = _gpu_ready()
        if not ok:
            raise HTTPException(503, f"live inference is disabled: {why}")
        tmp = Path(tempfile.mkdtemp(prefix="btqc_upload_"))
        for seq, f in (("t1", t1), ("t1ce", t1ce), ("t2", t2), ("flair", flair)):
            data = await f.read(max_upload + 1)
            if len(data) > max_upload:
                raise HTTPException(413, f"{seq}: file larger than {max_upload // 2**20} MB")
            validate_nifti_bytes(data, seq)
            (tmp / f"upload_{seq}.nii.gz").write_bytes(data if data[:2] == b"\x1f\x8b" else gzip.compress(data))
        jid = uuid.uuid4().hex[:12]
        jobs[jid] = {"id": jid, "status": "queued", "case_id": None, "message": None}
        threading.Thread(target=_run_job, args=(jid, tmp, jobs, cfg), daemon=True).start()
        return JobOut(**jobs[jid])

    @app.get("/api/jobs/{job_id}", response_model=JobOut)
    def job(job_id: str) -> JobOut:
        if job_id not in jobs:
            raise HTTPException(404, "unknown job")
        return JobOut(**jobs[job_id])

    @app.exception_handler(NotFound)
    async def not_found(_: Request, exc: NotFound) -> JSONResponse:
        return JSONResponse({"detail": "not found"}, status_code=404)

    web = resolve(cfg.get("web_dir", "web"))
    if web.exists():
        app.mount("/", StaticFiles(directory=str(web), html=True), name="web")
    return app


def validate_nifti_bytes(data: bytes, label: str) -> None:
    """Reject anything that is not a 3D NIfTI-1 volume. Raises HTTP 400 with a clear message."""
    import nibabel as nib

    raw = data
    if raw[:2] == b"\x1f\x8b":
        try:
            raw = gzip.decompress(raw)
        except (OSError, EOFError):
            raise HTTPException(400, f"{label}: damaged gzip file") from None
    if len(raw) < 352:
        raise HTTPException(400, f"{label}: not a NIfTI file")
    hdr_le = int.from_bytes(raw[:4], "little")
    hdr_be = int.from_bytes(raw[:4], "big")
    if 348 not in (hdr_le, hdr_be):
        raise HTTPException(400, f"{label}: not a NIfTI-1 file (.nii or .nii.gz expected)")
    try:
        img = nib.Nifti1Image.from_bytes(raw)
    except Exception:
        raise HTTPException(400, f"{label}: header could not be read") from None
    if len(img.shape) != 3 or min(img.shape) < 2 or max(img.shape) > 512:
        raise HTTPException(400, f"{label}: expected a 3D volume up to 512 voxels per axis, got {img.shape}")


def _run_job(jid: str, folder: Path, jobs: dict[str, dict[str, Any]], cfg: dict[str, Any]) -> None:
    jobs[jid]["status"] = "running"
    try:
        from btqc.infer.predict import predict_folder_nnunet

        cid = predict_folder_nnunet(folder, resolve(cfg["model_folder"]), resolve(cfg["predictions_root"]), jid)
        jobs[jid].update(status="done", case_id=cid)
    except Exception as e:
        jobs[jid].update(status="error", message=type(e).__name__)

