"""Pydantic request/response models for the API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

CASE_ID_PATTERN = r"^[A-Za-z0-9_\-]{1,64}$"
SEQUENCE_PATTERN = r"^(t1|t1ce|t2|flair|seg)$"


class RegionVolumes(BaseModel):
    WT: float | None = None
    TC: float | None = None
    ET: float | None = None
    NCR: float | None = None
    ED: float | None = None


class CaseSummary(BaseModel):
    id: str
    group: str | None = None
    sequences: list[str]
    has_reference: bool
    has_prediction: bool
    prediction_source: str | None = Field(default=None, description="'model' or 'example' (rule-based, not a model)")
    score: float | None = None
    flag: bool | None = None
    flag_label: str | None = None
    volumes_ml: RegionVolumes | None = None
    review: str | None = None


class CaseList(BaseModel):
    review_limit: float
    disclaimer: str
    cases: list[CaseSummary]


class PredictionInfo(BaseModel):
    case_id: str
    method: str
    fold: str
    source: str
    is_example: bool
    example_note: str | None = None
    score: float | None
    scores: dict[str, float | None]
    flag: bool
    flag_label: str
    reason: str
    review_limit: float
    volumes_ml: RegionVolumes
    hemisphere: str | None = None
    hot_spot: list[int] | None = Field(default=None, description="canonical RAS voxel index of the most uncertain spot")
    centroid: list[float] | None = None
    labels_url: str
    uncertainty_url: str
    labels_meta_url: str
    metrics: dict[str, float] | None = None


class ReviewIn(BaseModel):
    case_id: str = Field(pattern=CASE_ID_PATTERN)
    decision: Literal["accept", "reject", "note"]
    note: str = Field("", max_length=2000)
    reviewer: str = Field("reviewer", max_length=64, pattern=r"^[A-Za-z0-9_.\- ]{1,64}$")


class ReviewOut(ReviewIn):
    id: int
    created_at: str
    score: float | None = None
    review_limit: float | None = None


class JobOut(BaseModel):
    id: str
    status: Literal["queued", "running", "done", "error"]
    case_id: str | None = None
    message: str | None = None
