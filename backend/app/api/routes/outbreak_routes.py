"""
Outbreak Routes — lightweight syndromic-surveillance aberration signals.

Implements the CDC Early Aberration Reporting System (EARS) C1 method
(docs/DECISIONS.md §26): a comparative study of small-population
outbreak-detection methods found C1 — a 7-day trailing baseline mean and
standard deviation, flagging today's count when it exceeds
`baseline_mean + 3*baseline_stddev` — had the best validity and timeliness
for small-population settings, which is the right comparison class for a
rural PHC's case volume. A minimum floor (MIN_FLOOR) is also required before
a day is even eligible to be flagged, so a jump from 0 to 1 case in a tiny
population is never treated as "elevated."

Clustered on (facility, symptom, day) using `case_records.symptoms` — the
allow-listed symptom IDs (see ALLOWED_SYMPTOMS in app/models/schemas.py),
not the free-text `chief_complaint`, since a clean fixed vocabulary is what
makes day-over-day counts comparable at all.

This is an informational aid for a human to review, not a validated
public-health surveillance system — the same honesty standard already
applied to fairness_audit.py/drift_monitor.py. Output is aggregate counts
only: no patient names, no individual case content, ever. Uses
supabase_admin for exactly one aggregate query, the same narrow exception
pattern as §20/§22/§25 (see the SECURITY NOTE in app/core/database.py).
"""
import logging
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app.core.auth import require_role
from app.core.database import supabase_admin
from app.core.scoping import resolve_facility_scope
from app.api.routes.cases import limiter, _resolved_role, _resolved_facility

logger = logging.getLogger("vitalnet")

router = APIRouter(prefix="/api/outbreak", tags=["outbreak"])

BASELINE_DAYS = 7
MIN_FLOOR = 3           # today's count must reach this before it's even eligible to flag
Z_MULTIPLIER = 3        # EARS C1 threshold multiplier


def _day_bucket(created_at: str) -> str:
    """YYYY-MM-DD from an ISO timestamp string — same slicing convention
    analytics_routes.py already uses for daily_volume."""
    return created_at[:10]


def _compute_ears_signals(rows: list[dict], today: str) -> list[dict]:
    """
    Groups rows into per-(facility_id, symptom) daily counts and flags any
    pair where today's count meets MIN_FLOOR and exceeds the 7-day trailing
    baseline mean + Z_MULTIPLIER * baseline stddev. Pure function over
    already-fetched rows so it's testable without a live Supabase connection.

    `rows`: [{facility_id, symptoms: [...], created_at}, ...] spanning at
    least BASELINE_DAYS+1 trailing days.
    """
    counts: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in rows:
        facility_id = row.get("facility_id")
        day = _day_bucket(row.get("created_at") or "")
        if not facility_id or not day:
            continue
        for symptom in row.get("symptoms") or []:
            counts[(facility_id, symptom)][day] += 1

    today_date = datetime.fromisoformat(today).date()
    baseline_days = [(today_date - timedelta(days=i)).isoformat() for i in range(1, BASELINE_DAYS + 1)]

    signals = []
    for (facility_id, symptom), day_counts in counts.items():
        today_count = day_counts.get(today, 0)
        if today_count < MIN_FLOOR:
            continue

        baseline_counts = [day_counts.get(d, 0) for d in baseline_days]
        baseline_mean = statistics.mean(baseline_counts)
        baseline_stddev = statistics.stdev(baseline_counts) if len(baseline_counts) > 1 else 0.0
        threshold = baseline_mean + Z_MULTIPLIER * baseline_stddev

        if today_count > threshold:
            signals.append({
                "facility_id": facility_id,
                "symptom": symptom,
                "today_count": today_count,
                "baseline_mean": round(baseline_mean, 2),
                "baseline_stddev": round(baseline_stddev, 2),
                "threshold": round(threshold, 2),
            })

    signals.sort(key=lambda s: s["today_count"], reverse=True)
    return signals


@router.get("/signals")
@limiter.limit("60/minute")
async def get_outbreak_signals(
    request: Request,
    facility_id: str | None = None,
    authorization: str = Header(None),
    user: dict = Depends(require_role("doctor", "supervisor", "admin")),
):
    """
    Today's EARS C1 aberration signals: (facility, symptom) pairs whose case
    count today is statistically elevated versus the trailing 7-day
    baseline. Informational only — surfaced for a human to review, not an
    automated alert or a validated surveillance system.

    Scope: doctor/supervisor are always restricted to their own facility;
    admin defaults to system-wide, or narrows via `facility_id`.
    """
    role = _resolved_role(user)
    scoped_facility_id = resolve_facility_scope(role, _resolved_facility(user), facility_id)

    today = datetime.now(timezone.utc).date().isoformat()
    since = (datetime.now(timezone.utc) - timedelta(days=BASELINE_DAYS + 1)).isoformat()

    query = (
        supabase_admin.table("case_records")
        .select("facility_id, symptoms, created_at")
        .is_("deleted_at", "null")
        .gte("created_at", since)
    )
    if scoped_facility_id:
        query = query.eq("facility_id", scoped_facility_id)

    try:
        res = query.execute()
    except Exception as e:
        logger.warning("Outbreak signals query failed: %s", e)
        raise HTTPException(status_code=502, detail="Outbreak signals query failed — try again")

    signals = _compute_ears_signals(res.data or [], today)

    return {
        "facility_id": scoped_facility_id,
        "date": today,
        "baseline_days": BASELINE_DAYS,
        "signal_count": len(signals),
        "signals": signals,
    }
