"""
Analytics Routes — aggregate statistics and trends for facility dashboards.

Queries run concurrently (asyncio.gather over asyncio.to_thread, since the
supabase-py client is synchronous) with a per-query timeout and graceful
degradation: one slow/failing query returns partial data with a `_degraded`
flag instead of taking the whole dashboard down.
"""
import asyncio
import logging
import statistics
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Header, Depends, Request

from app.core.auth import require_role
from app.core.database import get_supabase_for_user
from app.api.routes.cases import limiter

logger = logging.getLogger("vitalnet")

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

# VitalNet's actual role model is exactly three roles: asha_worker, doctor,
# admin (see app/api/routes/admin_routes.py and AGENTS.md). 'admin' is the
# global-scope role — it is never restricted to a single facility, matching
# the behaviour of GET /api/admin/stats. 'doctor' accounts are scoped to
# their own facility_id.
GLOBAL_SCOPE_ROLE = "admin"

QUERY_TIMEOUT_SECONDS = 10


async def _run_query(query_fn, label: str, failures: list[str]):
    """Runs a synchronous supabase query off-thread with a timeout. Returns
    None (rather than raising) on timeout/failure, appending to `failures` so
    the caller can degrade gracefully instead of failing the whole endpoint."""
    try:
        return await asyncio.wait_for(asyncio.to_thread(query_fn), timeout=QUERY_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        failures.append(label)
        logger.warning("Analytics: %s query timed out", label)
        return None
    except Exception as e:
        failures.append(label)
        logger.warning("Analytics: %s query failed: %s", label, e)
        return None


@router.get("/summary")
@limiter.limit("60/minute")
async def get_summary(
    request: Request,
    authorization: str = Header(None),
    user: dict = Depends(require_role("doctor", "admin")),
):
    """
    Returns aggregate stats scoped to the user's facility.
    admin accounts get system-wide stats (global scope), matching
    the admin dashboard's other endpoints.
    """
    raw_token = (authorization or "").split(" ", 1)[-1]
    db = get_supabase_for_user(raw_token)

    role = user.get("resolved_role") or ""
    facility_id = user.get("resolved_facility_id")
    scoped = role != GLOBAL_SCOPE_ROLE and facility_id

    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    month_since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    def scope(q):
        return q.eq("facility_id", facility_id) if scoped else q

    failures: list[str] = []
    total_res, dist_res, week_res, reviewed_res, asha_res = await asyncio.gather(
        _run_query(
            lambda: scope(db.table("case_records").select("id", count="exact").is_("deleted_at", "null")).execute(),
            "total", failures,
        ),
        _run_query(
            lambda: scope(db.table("case_records").select("triage_level").is_("deleted_at", "null")).execute(),
            "triage_dist", failures,
        ),
        _run_query(
            lambda: scope(db.table("case_records").select("created_at").is_("deleted_at", "null").gte("created_at", since)).execute(),
            "week_cases", failures,
        ),
        _run_query(
            lambda: scope(db.table("case_records").select("id", count="exact").is_("deleted_at", "null").not_.is_("reviewed_at", "null")).execute(),
            "reviewed", failures,
        ),
        _run_query(
            lambda: scope(
                db.table("case_records")
                .select("submitted_by, profiles!submitted_by(full_name)")
                .is_("deleted_at", "null")
                .gte("created_at", month_since)
            ).execute(),
            "asha_workers", failures,
        ),
    )

    total = total_res.count if total_res else 0

    dist = {"ROUTINE": 0, "URGENT": 0, "EMERGENCY": 0}
    for row in (dist_res.data if dist_res else []) or []:
        level = row.get("triage_level")
        if level in dist:
            dist[level] += 1

    daily = {}
    for row in (week_res.data if week_res else []) or []:
        day = row["created_at"][:10]  # YYYY-MM-DD
        daily[day] = daily.get(day, 0) + 1

    reviewed = reviewed_res.count if reviewed_res else 0

    asha_counts = {}
    for row in (asha_res.data if asha_res else []) or []:
        uid = row.get("submitted_by")
        name = (row.get("profiles") or {}).get("full_name", "Unknown")
        key = f"{uid}::{name}"
        asha_counts[key] = asha_counts.get(key, 0) + 1

    top_asha = sorted(
        [{"name": k.split("::")[1], "count": v} for k, v in asha_counts.items()],
        key=lambda x: x["count"],
        reverse=True,
    )[:5]

    response = {
        "total_cases": total,
        "triage_distribution": dist,
        "daily_volume": daily,
        "reviewed_count": reviewed,
        "unreviewed_count": total - reviewed,
        "top_asha_workers": top_asha,
    }
    if failures:
        response["_degraded"] = True
        response["_failed_queries"] = failures
    return response


@router.get("/emergency-rate")
@limiter.limit("60/minute")
async def get_emergency_rate(
    request: Request,
    authorization: str = Header(None),
    user: dict = Depends(require_role("doctor", "admin")),
):
    """
    Returns EMERGENCY case rate over the last 30 days, grouped by week.
    Used for the trend indicator in the admin analytics view.
    """
    raw_token = (authorization or "").split(" ", 1)[-1]
    db = get_supabase_for_user(raw_token)

    role = user.get("resolved_role") or ""
    facility_id = user.get("resolved_facility_id")
    scoped = role != GLOBAL_SCOPE_ROLE and facility_id

    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    def build_query():
        q = (
            db.table("case_records")
            .select("triage_level, created_at")
            .is_("deleted_at", "null")
            .gte("created_at", since)
        )
        return (q.eq("facility_id", facility_id) if scoped else q).execute()

    failures: list[str] = []
    res = await _run_query(build_query, "emergency_rate", failures)
    rows = (res.data if res else []) or []

    # Group by ISO week
    weeks = {}
    for row in rows:
        dt = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
        week_key = dt.strftime("%Y-W%W")
        if week_key not in weeks:
            weeks[week_key] = {"total": 0, "emergency": 0}
        weeks[week_key]["total"] += 1
        if row["triage_level"] == "EMERGENCY":
            weeks[week_key]["emergency"] += 1

    result = [
        {
            "week": k,
            "total": v["total"],
            "emergency": v["emergency"],
            "rate": round(v["emergency"] / v["total"], 3) if v["total"] else 0,
        }
        for k, v in sorted(weeks.items())
    ]

    response = {"weeks": result}
    if failures:
        response["_degraded"] = True
    return response


# ── Response Times (SLA dashboard, FEATURES_ROADMAP §1.5) ─────────────────────

# EMERGENCY should be reviewed within 15 min, URGENT within 2 hours — cases
# past this threshold and still unreviewed are the "overdue" count.
OVERDUE_THRESHOLDS_MIN = {"EMERGENCY": 15, "URGENT": 120, "ROUTINE": 24 * 60}


def _percentile(sorted_values: list[float], pct: float) -> float:
    """Nearest-rank percentile over an already-sorted list. pct in [0, 100]."""
    if not sorted_values:
        return 0.0
    idx = min(len(sorted_values) - 1, max(0, round(pct / 100 * (len(sorted_values) - 1))))
    return sorted_values[idx]


@router.get("/response-times")
@limiter.limit("60/minute")
async def get_response_times(
    request: Request,
    authorization: str = Header(None),
    user: dict = Depends(require_role("doctor", "admin")),
):
    """
    Per-tier response-time distribution (median/p90) over the last 30 days,
    plus a count of cases still unreviewed past each tier's SLA threshold —
    the number that should visually demand attention on the dashboard.
    """
    raw_token = (authorization or "").split(" ", 1)[-1]
    db = get_supabase_for_user(raw_token)

    role = user.get("resolved_role") or ""
    facility_id = user.get("resolved_facility_id")
    scoped = role != GLOBAL_SCOPE_ROLE and facility_id

    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    def build_query():
        q = (
            db.table("case_records")
            .select("triage_level, created_at, reviewed_at")
            .is_("deleted_at", "null")
            .gte("created_at", since)
        )
        return (q.eq("facility_id", facility_id) if scoped else q).execute()

    failures: list[str] = []
    res = await _run_query(build_query, "response_times", failures)
    rows = (res.data if res else []) or []

    now = datetime.now(timezone.utc)
    minutes_by_tier: dict[str, list[float]] = {"ROUTINE": [], "URGENT": [], "EMERGENCY": []}
    overdue_by_tier = {"ROUTINE": 0, "URGENT": 0, "EMERGENCY": 0}

    for row in rows:
        tier = row.get("triage_level")
        if tier not in minutes_by_tier:
            continue
        created = datetime.fromisoformat(row["created_at"].replace("Z", "+00:00"))
        reviewed_at = row.get("reviewed_at")
        threshold_min = OVERDUE_THRESHOLDS_MIN[tier]

        if reviewed_at:
            reviewed = datetime.fromisoformat(reviewed_at.replace("Z", "+00:00"))
            minutes_by_tier[tier].append((reviewed - created).total_seconds() / 60)
        elif (now - created).total_seconds() / 60 > threshold_min:
            overdue_by_tier[tier] += 1

    result = {}
    for tier, minutes in minutes_by_tier.items():
        sorted_minutes = sorted(minutes)
        result[tier] = {
            "count_reviewed": len(sorted_minutes),
            "median_minutes": round(statistics.median(sorted_minutes), 1) if sorted_minutes else None,
            "p90_minutes": round(_percentile(sorted_minutes, 90), 1) if sorted_minutes else None,
            "overdue_count": overdue_by_tier[tier],
            "overdue_threshold_minutes": OVERDUE_THRESHOLDS_MIN[tier],
        }

    response = {"tiers": result}
    if failures:
        response["_degraded"] = True
    return response


# ── ML Triage Agreement Rate (FEATURES_ROADMAP §1.3 step 5) ───────────────────

@router.get("/ml-agreement")
@limiter.limit("60/minute")
async def get_ml_agreement(
    request: Request,
    authorization: str = Header(None),
    user: dict = Depends(require_role("doctor", "admin")),
):
    """
    % of recorded outcomes where the doctor's actual_severity matches the
    ML's original triage_level, broken out by tier — the metric that tells
    an admin when it's time to retrain (FEATURES_ROADMAP §1.3), and an
    ongoing model-quality monitor even before the first retrain.
    """
    raw_token = (authorization or "").split(" ", 1)[-1]
    db = get_supabase_for_user(raw_token)

    role = user.get("resolved_role") or ""
    facility_id = user.get("resolved_facility_id")
    scoped = role != GLOBAL_SCOPE_ROLE and facility_id

    def build_query():
        q = db.table("case_outcomes").select("actual_severity, case_records!inner(triage_level, facility_id)")
        if scoped:
            q = q.eq("case_records.facility_id", facility_id)
        return q.execute()

    failures: list[str] = []
    res = await _run_query(build_query, "ml_agreement", failures)
    rows = (res.data if res else []) or []

    by_tier = {"ROUTINE": {"total": 0, "agree": 0}, "URGENT": {"total": 0, "agree": 0}, "EMERGENCY": {"total": 0, "agree": 0}}
    overall_total = 0
    overall_agree = 0

    for row in rows:
        case = row.get("case_records") or {}
        original_tier = case.get("triage_level")
        actual = row.get("actual_severity")
        if original_tier not in by_tier:
            continue
        by_tier[original_tier]["total"] += 1
        overall_total += 1
        if actual == original_tier:
            by_tier[original_tier]["agree"] += 1
            overall_agree += 1

    def rate(agree, total):
        return round(agree / total, 3) if total else None

    response = {
        "overall_agreement_rate": rate(overall_agree, overall_total),
        "overall_count": overall_total,
        "by_tier": {
            tier: {"agreement_rate": rate(v["agree"], v["total"]), "count": v["total"]}
            for tier, v in by_tier.items()
        },
    }
    if failures:
        response["_degraded"] = True
    return response
