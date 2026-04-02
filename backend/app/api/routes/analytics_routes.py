"""
Analytics Routes — aggregate statistics and trends for facility dashboards.

Security Fixes Applied:
- R3-DATA-QUERY-R3-002: Explicit column projection (no SELECT *)
- R3-DATA-QUERY-R3-003: Parallel query execution via asyncio.gather

Reliability Fixes (CHAOS-005 to CHAOS-010):
- Graceful degradation: Returns fallback data when queries fail
- Query timeout: Prevents hanging requests from blocking resources
- Error isolation: Individual query failures don't break entire endpoint
"""
from fastapi import APIRouter, Header, Depends
from fastapi.responses import JSONResponse

from app.core.auth import require_role
from app.core.database import get_supabase_for_user
from datetime import datetime, timedelta, timezone
import asyncio
import logging

logger = logging.getLogger("vitalnet")

router = APIRouter(prefix="/api/analytics", tags=["analytics"])

# Query timeout in seconds (prevents hanging requests)
QUERY_TIMEOUT_SECONDS = 10

# Explicit column list for case_records queries (R3-DATA-QUERY-R3-002 fix)
# Only select columns actually needed for analytics — avoids exposing PHI unnecessarily
ANALYTICS_COLUMNS = "id, triage_level, triage_priority, created_at, reviewed_at, submitted_by, facility_id, deleted_at"


@router.get("/summary")
async def get_summary(
    authorization: str = Header(None),
    user: dict = Depends(require_role("doctor", "facility_admin", "admin", "super_admin")),
):
    """
    Returns aggregate stats scoped to the user's facility.
    super_admin gets system-wide stats.

    Security: R3-DATA-QUERY-R3-002, R3-DATA-QUERY-R3-003 fixes applied.
    Reliability: Graceful degradation - returns partial data if some queries fail.
    """
    raw_token = authorization.split(" ", 1)[1] if authorization else ""
    db = get_supabase_for_user(raw_token)

    role = user.get("user_metadata", {}).get("role")
    facility_id = user.get("user_metadata", {}).get("facility_id")

    # Prepare time filters
    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    month_since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    # Track which queries failed for observability
    query_failures = []

    # R3-DATA-QUERY-R3-003: Execute all queries in parallel using asyncio.gather
    # R3-DATA-QUERY-R3-002: Use explicit column projection instead of SELECT *
    # Each query has its own try-catch for graceful degradation
    async def query_total():
        try:
            q = db.table("case_records").select("id", count="exact").is_("deleted_at", "null")
            if role not in ("super_admin",) and facility_id:
                q = q.eq("facility_id", facility_id)
            return await asyncio.wait_for(asyncio.to_thread(lambda: q.execute()), timeout=QUERY_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            query_failures.append("total")
            logger.warning("Analytics: total query timeout")
            return type('obj', (object,), {'count': 0, 'data': []})()
        except Exception as e:
            query_failures.append("total")
            logger.warning(f"Analytics: total query failed: {e}")
            return type('obj', (object,), {'count': 0, 'data': []})()

    async def query_triage_dist():
        try:
            q = db.table("case_records").select("triage_level").is_("deleted_at", "null")
            if role not in ("super_admin",) and facility_id:
                q = q.eq("facility_id", facility_id)
            return await asyncio.wait_for(asyncio.to_thread(lambda: q.execute()), timeout=QUERY_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            query_failures.append("triage_dist")
            logger.warning("Analytics: triage_dist query timeout")
            return type('obj', (object,), {'data': []})()
        except Exception as e:
            query_failures.append("triage_dist")
            logger.warning(f"Analytics: triage_dist query failed: {e}")
            return type('obj', (object,), {'data': []})()

    async def query_week_cases():
        try:
            q = db.table("case_records").select("created_at").is_("deleted_at", "null").gte("created_at", since)
            if role not in ("super_admin",) and facility_id:
                q = q.eq("facility_id", facility_id)
            return await asyncio.wait_for(asyncio.to_thread(lambda: q.execute()), timeout=QUERY_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            query_failures.append("week_cases")
            logger.warning("Analytics: week_cases query timeout")
            return type('obj', (object,), {'data': []})()
        except Exception as e:
            query_failures.append("week_cases")
            logger.warning(f"Analytics: week_cases query failed: {e}")
            return type('obj', (object,), {'data': []})()

    async def query_reviewed():
        try:
            q = db.table("case_records").select("id", count="exact").is_("deleted_at", "null").not_.is_("reviewed_at", "null")
            if role not in ("super_admin",) and facility_id:
                q = q.eq("facility_id", facility_id)
            return await asyncio.wait_for(asyncio.to_thread(lambda: q.execute()), timeout=QUERY_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            query_failures.append("reviewed")
            logger.warning("Analytics: reviewed query timeout")
            return type('obj', (object,), {'count': 0, 'data': []})()
        except Exception as e:
            query_failures.append("reviewed")
            logger.warning(f"Analytics: reviewed query failed: {e}")
            return type('obj', (object,), {'count': 0, 'data': []})()

    async def query_asha_workers():
        try:
            q = db.table("case_records").select("submitted_by, profiles!submitted_by(full_name)").is_("deleted_at", "null").gte("created_at", month_since)
            if role not in ("super_admin",) and facility_id:
                q = q.eq("facility_id", facility_id)
            return await asyncio.wait_for(asyncio.to_thread(lambda: q.execute()), timeout=QUERY_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            query_failures.append("asha_workers")
            logger.warning("Analytics: asha_workers query timeout")
            return type('obj', (object,), {'data': []})()
        except Exception as e:
            query_failures.append("asha_workers")
            logger.warning(f"Analytics: asha_workers query failed: {e}")
            return type('obj', (object,), {'data': []})()

    # Execute all queries in parallel — significant latency improvement
    # Individual query failures don't break the entire endpoint
    total_res, dist_res, week_res, reviewed_res, asha_res = await asyncio.gather(
        query_total(),
        query_triage_dist(),
        query_week_cases(),
        query_reviewed(),
        query_asha_workers(),
    )

    # Process total cases
    total = total_res.count or 0

    # Process triage distribution
    dist = {"ROUTINE": 0, "URGENT": 0, "EMERGENCY": 0}
    for row in (dist_res.data or []):
        level = row.get("triage_level")
        if level in dist:
            dist[level] += 1

    # Process daily volume
    daily = {}
    for row in (week_res.data or []):
        day = row["created_at"][:10]  # YYYY-MM-DD
        daily[day] = daily.get(day, 0) + 1

    # Process reviewed count
    reviewed = reviewed_res.count or 0

    # Process ASHA worker counts
    asha_counts = {}
    for row in (asha_res.data or []):
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

    # Add degradation indicator if any queries failed
    if query_failures:
        response["_degraded"] = True
        response["_failed_queries"] = query_failures
        logger.info(f"Analytics summary returned degraded data. Failed queries: {query_failures}")

    return response


@router.get("/emergency-rate")
async def get_emergency_rate(
    authorization: str = Header(None),
    user: dict = Depends(require_role("doctor", "facility_admin", "admin", "super_admin")),
):
    """
    Returns EMERGENCY case rate over the last 30 days, grouped by week.
    Used for the trend indicator in the admin analytics view.

    Reliability: Graceful degradation - returns empty weeks if query fails.
    """
    raw_token = authorization.split(" ", 1)[1]
    db = get_supabase_for_user(raw_token)

    role = user.get("user_metadata", {}).get("role")
    facility_id = user.get("user_metadata", {}).get("facility_id")

    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    try:
        q = (
            db.table("case_records")
            .select("triage_level, created_at")
            .is_("deleted_at", "null")
            .gte("created_at", since)
        )
        if role not in ("super_admin",) and facility_id:
            q = q.eq("facility_id", facility_id)

        # Add query timeout to prevent hanging
        res = await asyncio.wait_for(
            asyncio.to_thread(lambda: q.execute()),
            timeout=QUERY_TIMEOUT_SECONDS
        )
        rows = res.data or []
    except asyncio.TimeoutError:
        logger.warning("Analytics: emergency_rate query timeout")
        rows = []
    except Exception as e:
        logger.warning(f"Analytics: emergency_rate query failed: {e}")
        rows = []

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

    return {"weeks": result}
