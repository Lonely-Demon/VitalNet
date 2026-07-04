"""
Analytics Routes — aggregate statistics and trends for facility dashboards.

Queries run concurrently (asyncio.gather over asyncio.to_thread, since the
supabase-py client is synchronous) with a per-query timeout and graceful
degradation: one slow/failing query returns partial data with a `_degraded`
flag instead of taking the whole dashboard down.
"""
import asyncio
import logging
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
