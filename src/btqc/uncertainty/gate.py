"""Trust gate (requirement R4).

The flag depends ONLY on the case uncertainty score and a configurable review
limit. No other input (no web search, no language model, no external service,
no metadata) can change it. Keep this module free of imports beyond the
standard library so that this is easy to verify by code review.

    flag = score > review_limit        (NaN or missing score -> flag, fail-safe)
"""

from __future__ import annotations

import math
from dataclasses import dataclass

NEEDS_REVIEW = "needs review"
LOOKS_RELIABLE = "looks reliable"


@dataclass(frozen=True)
class GateDecision:
    flag: bool
    label: str
    reason: str


def _as_float(x: object) -> float:
    if x is None or isinstance(x, bool):
        return math.nan
    try:
        return float(x)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return math.nan


def flag(score: float | None, review_limit: float) -> bool:
    """True means "needs review". A score equal to the limit is not flagged."""
    limit = _as_float(review_limit)
    if math.isnan(limit):
        raise ValueError("review_limit must be a number")
    s = _as_float(score)
    if math.isnan(s):
        return True
    return s > limit


def decide(score: float | None, review_limit: float) -> GateDecision:
    f = flag(score, review_limit)
    s = _as_float(score)
    if math.isnan(s):
        reason = "No uncertainty score could be computed (for example an empty prediction), so the case needs review."
    elif f:
        reason = f"Boundary uncertainty {s:.3f} is above the review limit {float(review_limit):.3f}."
    else:
        reason = f"Boundary uncertainty {s:.3f} is at or below the review limit {float(review_limit):.3f}."
    return GateDecision(flag=f, label=NEEDS_REVIEW if f else LOOKS_RELIABLE, reason=reason)
