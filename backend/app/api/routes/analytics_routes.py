from fastapi import APIRouter, Header, Depends

from app.core.auth import require_role
from app.core.database import get_supabase_for_user
from datetime import datetime, timedelta, timezone

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/summary")
async def get_summary(
    authorization: str = Header(None),
    user: dict = Depends(require_role("doctor", "facility_admin", "admin", "super_admin")),
):
    """
    Returns aggregate stats scoped to the user's facility.
    super_admin gets system-wide stats.
    """
    raw_token = authorization.split(" ", 1)[1]
    db = get_supabase_for_user(raw_token)

    role = user.get("user_metadata", {}).get("role")
    facility_id = user.get("user_metadata", {}).get("facility_id")

    # Base query — facility-scoped unless super_admin
    def base_query():
        q = db.table("case_records").select("*", count="exact").is_("deleted_at", "null")
        if role not in ("super_admin",) and facility_id:
            q = q.eq("facility_id", facility_id)
        return q

    # Total cases
    total_res = base_query().execute()
    total = total_res.count or 0

    # Triage distribution
    dist = {"ROUTINE": 0, "URGENT": 0, "EMERGENCY": 0}
    dist_res = base_query().select("triage_level").execute()
    for row in (dist_res.data or []):
        level = row.get("triage_level")
        if level in dist:
            dist[level] += 1

    # Cases last 7 days — group by date
    since = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    week_res = (
        base_query()
        .select("created_at")
        .gte("created_at", since)
        .execute()
    )
    daily = {}
    for row in (week_res.data or []):
        day = row["created_at"][:10]  # YYYY-MM-DD
        daily[day] = daily.get(day, 0) + 1

    # Reviewed vs unreviewed
    reviewed_res = base_query().not_.is_("reviewed_at", "null").execute()
    reviewed = reviewed_res.count or 0

    # Top ASHA workers by submission count (last 30 days)
    month_since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    asha_res = (
        base_query()
        .select("submitted_by, profiles!submitted_by(full_name)")
        .gte("created_at", month_since)
        .execute()
    )
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
    raw_token = authorization.split(" ", 1)[1]
    db = get_supabase_for_user(raw_token)

    role = user.get("user_metadata", {}).get("role")
    facility_id = user.get("user_metadata", {}).get("facility_id")

    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()

    q = (
        db.table("case_records")
        .select("triage_level, created_at")
        .is_("deleted_at", "null")
        .gte("created_at", since)
    )
    if role not in ("super_admin",) and facility_id:
        q = q.eq("facility_id", facility_id)

    res = q.execute()
    rows = res.data or []

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
