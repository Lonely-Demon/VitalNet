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
only: no patient names, no individual case content, ever. Calls
fn_outbreak_signal_counts — a SECURITY DEFINER Postgres function (backend/
supabase/migrations/phase40_supervisor_global_aggregate_scope.sql) — through the
caller's own RLS-scoped client, the same narrow exception pattern as
§20/§22/§25, now enforced inside the database rather than via supabase_admin.
"""
import logging
import math
import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app.core.auth import require_role
from app.core.database import get_supabase_for_user, extract_bearer_token
from app.core.scoping import resolve_facility_scope
from app.api.routes.cases import limiter, _resolved_role, _resolved_facility

logger = logging.getLogger("vitalnet")

router = APIRouter(prefix="/api/outbreak", tags=["outbreak"])

BASELINE_DAYS = 7
GUARD_BAND_DAYS = 2
MIN_FLOOR = 3           # today's count must reach this before it's even eligible to flag
MIN_STDDEV_FLOOR = 0.5  # Empirical Bayes Poisson variance floor (ADR §54)
Z_MULTIPLIER = 3        # EARS threshold multiplier

IST = timezone(timedelta(hours=5, minutes=30))


def _day_bucket(created_at: str) -> str:
    """YYYY-MM-DD in Indian Standard Time (UTC+05:30).
    Converts ISO timestamp string to IST before extracting the date string,
    preventing early morning visits (00:00–05:29 IST) from shifting to yesterday.
    """
    if not created_at:
        return ""
    try:
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        ist_dt = dt.astimezone(IST)
        return ist_dt.date().isoformat()
    except Exception:
        return created_at[:10]


def _compute_ears_signals(rows: list[dict], today: str, use_guard_band: bool = True) -> list[dict]:
    """
    Groups rows into per-(facility_id, symptom) daily counts and flags any
    pair where today's count meets MIN_FLOOR and exceeds the baseline mean +
    Z_MULTIPLIER * baseline stddev.
    
    ADR §54 EARS C2:
    - 2-day guard band [t-9 .. t-3] skipping t-2 and t-1 when >= 9 days of history exist.
    - Falls back to [t-7 .. t-1] when < 9 days of history are available.
    - Empirical Bayes Poisson-bounded variance floor:
      eff_sigma = max(s_sample, sqrt(max(mean, 0.25)), MIN_STDDEV_FLOOR)
    - Stabilized z_score = round((today_count - mean) / eff_sigma, 2).
    """
    counts: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    all_days: list[str] = []
    for row in rows:
        facility_id = row.get("facility_id")
        created_at = row.get("created_at") or ""
        day = _day_bucket(created_at)
        if not facility_id or not day:
            continue
        all_days.append(day)
        for symptom in row.get("symptoms") or []:
            counts[(facility_id, symptom)][day] += 1

    today_date = datetime.fromisoformat(today).date() if isinstance(today, str) else today

    # Dense contiguous calendar date sequence in IST for EARS baseline calculation (BUG-14)
    # When use_guard_band is enabled (EARS C2), baseline is strictly over the 7 historical
    # calendar days [t-9 .. t-3], skipping the 2-day guard band [t-2, t-1].
    # Days with zero cases are naturally evaluated as 0 via day_counts.get(d, 0).
    if use_guard_band:
        start_offset = 1 + GUARD_BAND_DAYS
        end_offset = BASELINE_DAYS + GUARD_BAND_DAYS
    else:
        start_offset = 1
        end_offset = BASELINE_DAYS

    baseline_days = [(today_date - timedelta(days=i)).isoformat() for i in range(start_offset, end_offset + 1)]

    signals = []
    for (facility_id, symptom), day_counts in counts.items():
        today_count = day_counts.get(today, 0)
        if today_count < MIN_FLOOR:
            continue

        baseline_counts = [day_counts.get(d, 0) for d in baseline_days]
        baseline_mean = statistics.mean(baseline_counts) if baseline_counts else 0.0
        baseline_stddev = statistics.stdev(baseline_counts) if len(baseline_counts) > 1 else 0.0
        
        # Empirical Bayes Poisson-bounded variance floor (ADR §54)
        poisson_stddev = math.sqrt(max(baseline_mean, 0.25))
        eff_sigma = max(baseline_stddev, poisson_stddev, MIN_STDDEV_FLOOR)
        
        threshold = baseline_mean + Z_MULTIPLIER * baseline_stddev

        if today_count > threshold:
            z_score = round((today_count - baseline_mean) / eff_sigma, 2)
            signals.append({
                "facility_id": facility_id,
                "symptom": symptom,
                "today_count": today_count,
                "baseline_mean": round(baseline_mean, 2),
                "baseline_stddev": round(baseline_stddev, 2),
                "effective_sigma": round(eff_sigma, 2),
                "threshold": round(threshold, 2),
                "z_score": z_score,
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
    Today's EARS C2 aberration signals: (facility, symptom) pairs whose case
    count today is statistically elevated versus the trailing baseline with
    a 2-day guard band and Empirical Bayes Poisson variance floor.
    """
    role = _resolved_role(user)
    scoped_facility_id = resolve_facility_scope(role, _resolved_facility(user), facility_id)

    # Convert current time to IST date string
    now_ist = datetime.now(timezone.utc).astimezone(IST)
    today = now_ist.date().isoformat()
    # Query 10 days of history: BASELINE_DAYS + GUARD_BAND_DAYS + 1 = 10 days
    since = (datetime.now(timezone.utc) - timedelta(days=BASELINE_DAYS + GUARD_BAND_DAYS + 1)).isoformat()

    raw_token = extract_bearer_token(authorization)
    db = get_supabase_for_user(raw_token)

    try:
        res = db.rpc(
            "fn_outbreak_signal_counts",
            {"p_facility_id": scoped_facility_id, "p_since": since},
        ).execute()
    except Exception as e:
        logger.warning("Outbreak signals query failed: %s", e)
        raise HTTPException(status_code=502, detail="Outbreak signals query failed — try again")

    signals = _compute_ears_signals(res.data or [], today, use_guard_band=True)

    return {
        "facility_id": scoped_facility_id,
        "date": today,
        "baseline_days": BASELINE_DAYS,
        "guard_band_days": GUARD_BAND_DAYS,
        "signal_count": len(signals),
        "signals": signals,
    }
