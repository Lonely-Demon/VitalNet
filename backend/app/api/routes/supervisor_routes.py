"""
Supervisor Routes — aggregate, non-PHI, per-ASHA-worker team metrics.

Grounded in NHM's real ASHA Facilitator role (docs/DECISIONS.md §25): a
facility-scoped, workforce-quality-oversight role, structurally separate from
clinical case authority (doctor) and organisation-wide administration (admin).

Uses supabase_admin — a deliberate, narrow RLS bypass following the same
pattern already established in §20 (referral load-balancing) and §22
(deterioration alert): what crosses the RLS boundary is always an aggregate,
grouped by submitting worker, never an individual case row or any patient
field (chief complaint, vitals, name — none of it is selected here).
supervisor is never added to case_records' row-level SELECT policy; this
endpoint is the only sanctioned path by which a supervisor account reasons
about case data at all.
"""
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app.core.auth import require_role
from app.core.database import supabase_admin
from app.core.scoping import resolve_facility_scope
from app.api.routes.cases import limiter, _resolved_role, _resolved_facility

logger = logging.getLogger("vitalnet")

router = APIRouter(prefix="/api/supervisor", tags=["supervisor"])

DEFAULT_WINDOW_DAYS = 30
MAX_WINDOW_DAYS = 366


def _aggregate_team_metrics(rows: list[dict]) -> list[dict]:
    """
    Groups case_records rows by submitted_by into per-worker aggregates:
    submission count, needs_review/contraindication/deterioration rates, and
    triage-tier distribution. Pure function over already-fetched rows so it's
    testable without a live Supabase connection.
    """
    workers: dict[str, dict] = {}
    for row in rows:
        uid = row.get("submitted_by")
        if not uid:
            continue
        w = workers.get(uid)
        if w is None:
            w = {
                "user_id": uid,
                "full_name": (row.get("profiles") or {}).get("full_name") or "Unknown",
                "submission_count": 0,
                "needs_review_count": 0,
                "contraindication_flag_count": 0,
                "deterioration_alert_count": 0,
                "tier_distribution": {"ROUTINE": 0, "URGENT": 0, "EMERGENCY": 0},
            }
            workers[uid] = w
        w["submission_count"] += 1
        if row.get("needs_review"):
            w["needs_review_count"] += 1
        if row.get("contraindication_flags"):
            w["contraindication_flag_count"] += 1
        if row.get("deterioration_alert"):
            w["deterioration_alert_count"] += 1
        tier = row.get("triage_level")
        if tier in w["tier_distribution"]:
            w["tier_distribution"][tier] += 1

    def rate(count: int, total: int):
        return round(count / total, 3) if total else None

    result = []
    for w in workers.values():
        total = w["submission_count"]
        result.append({
            **w,
            "needs_review_rate": rate(w["needs_review_count"], total),
            "contraindication_flag_rate": rate(w["contraindication_flag_count"], total),
            "deterioration_alert_rate": rate(w["deterioration_alert_count"], total),
        })

    result.sort(key=lambda w: w["submission_count"], reverse=True)
    return result


@router.get("/team-metrics")
@limiter.limit("60/minute")
async def get_team_metrics(
    request: Request,
    days: int = DEFAULT_WINDOW_DAYS,
    facility_id: str | None = None,
    authorization: str = Header(None),
    user: dict = Depends(require_role("supervisor", "admin")),
):
    """
    Per-ASHA-worker aggregate metrics over a trailing window: submission
    count, needs_review rate, contraindication-flag rate, deterioration-alert
    rate, and triage-tier distribution — the signal real supportive
    supervision needs (which workers need more training/support), with
    structurally no visibility into any individual case's content.

    Scope: supervisor is always restricted to their own facility (the
    `facility_id` query param is ignored for that role — a supervisor cannot
    widen their own scope by passing a different id). admin defaults to
    system-wide but may pass `facility_id` to narrow to one facility.
    """
    if not (1 <= days <= MAX_WINDOW_DAYS):
        raise HTTPException(status_code=400, detail=f"days must be between 1 and {MAX_WINDOW_DAYS}")

    role = _resolved_role(user)
    scoped_facility_id = resolve_facility_scope(role, _resolved_facility(user), facility_id)

    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    query = (
        supabase_admin.table("case_records")
        .select(
            "submitted_by, triage_level, needs_review, contraindication_flags, "
            "deterioration_alert, profiles!submitted_by(full_name)"
        )
        .is_("deleted_at", "null")
        .gte("created_at", since)
    )
    if scoped_facility_id:
        query = query.eq("facility_id", scoped_facility_id)

    try:
        res = query.execute()
    except Exception as e:
        logger.warning("Supervisor team-metrics query failed: %s", e)
        raise HTTPException(status_code=502, detail="Team metrics query failed — try again")

    result = _aggregate_team_metrics(res.data or [])

    return {
        "facility_id": scoped_facility_id,
        "window_days": days,
        "worker_count": len(result),
        "workers": result,
    }
