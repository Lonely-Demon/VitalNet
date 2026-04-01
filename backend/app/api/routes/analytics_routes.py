from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException

from app.core.auth import require_role
from app.core.database import get_supabase_for_user

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


def _extract_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    parts = authorization.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(status_code=401, detail="Malformed Authorization header")
    return parts[1].strip()


def _header_or_401(value: str | None) -> str:
    if value is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    return value


def _resolved_role(user: dict) -> str:
    return (user.get("resolved_role") or "").strip()


def _resolved_facility(user: dict) -> str | None:
    return user.get("resolved_facility_id")


@router.get("/summary")
async def get_summary(
    authorization: str = Header(None),
    user: dict = Depends(require_role("doctor", "facility_admin", "admin", "super_admin")),
):
    """
    Returns aggregate stats scoped to the user's facility.
    super_admin gets system-wide stats.
    """
    raw_token = _extract_token(_header_or_401(authorization))
    db = get_supabase_for_user(raw_token)

    role = _resolved_role(user)
    facility_id = _resolved_facility(user)

    if role in {"doctor", "facility_admin"} and not facility_id:
        raise HTTPException(status_code=403, detail="User is not assigned to a facility")

    query = (
        db.table("case_records")
        .select("id, triage_level, created_at, reviewed_at, submitted_by, facility_id")
        .is_("deleted_at", "null")
    )
    if role != "super_admin" and facility_id:
        query = query.eq("facility_id", facility_id)

    rows = (query.execute().data or [])
    total = len(rows)

    dist = {"ROUTINE": 0, "URGENT": 0, "EMERGENCY": 0}
    for row in rows:
        level = row.get("triage_level")
        if level in dist:
            dist[level] += 1

    since = datetime.now(timezone.utc) - timedelta(days=7)
    daily = {}
    for row in rows:
        created_at = row.get("created_at")
        if not created_at:
            continue
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        if dt >= since:
            day = dt.strftime("%Y-%m-%d")
            daily[day] = daily.get(day, 0) + 1

    reviewed = sum(1 for row in rows if row.get("reviewed_at") is not None)

    month_since = datetime.now(timezone.utc) - timedelta(days=30)
    asha_counts = {}
    for row in rows:
        created_at = row.get("created_at")
        if not created_at:
            continue
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        if dt < month_since:
            continue
        uid = row.get("submitted_by")
        key = str(uid) if uid else "unknown"
        asha_counts[key] = asha_counts.get(key, 0) + 1

    top_asha = sorted(
        [{"name": k, "count": v} for k, v in asha_counts.items()],
        key=lambda x: x["count"],
        reverse=True,
    )[:5]

    return {
        "total_cases": total,
        "triage_distribution": dist,
        "daily_volume": daily,
        "reviewed_count": reviewed,
        "unreviewed_count": total - reviewed,
        "top_asha_workers": top_asha,
    }


@router.get("/emergency-rate")
async def get_emergency_rate(
    authorization: str = Header(None),
    user: dict = Depends(require_role("doctor", "facility_admin", "admin", "super_admin")),
):
    """
    Returns EMERGENCY case rate over the last 30 days, grouped by week.
    Used for the trend indicator in the admin analytics view.
    """
    raw_token = _extract_token(_header_or_401(authorization))
    db = get_supabase_for_user(raw_token)

    role = _resolved_role(user)
    facility_id = _resolved_facility(user)

    if role in {"doctor", "facility_admin"} and not facility_id:
        raise HTTPException(status_code=403, detail="User is not assigned to a facility")

    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    q = (
        db.table("case_records")
        .select("triage_level, created_at")
        .is_("deleted_at", "null")
        .gte("created_at", since)
    )
    if role != "super_admin" and facility_id:
        q = q.eq("facility_id", facility_id)

    rows = q.execute().data or []

    weeks = {}
    for row in rows:
        created_at = row.get("created_at")
        if not created_at:
            continue
        dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        week_key = dt.strftime("%Y-W%W")
        if week_key not in weeks:
            weeks[week_key] = {"total": 0, "emergency": 0}
        weeks[week_key]["total"] += 1
        if row.get("triage_level") == "EMERGENCY":
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
