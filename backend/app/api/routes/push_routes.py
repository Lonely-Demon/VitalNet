"""
Web Push subscription management (FEATURES_ROADMAP §1.4) and the
unreviewed-EMERGENCY escalation check (§1b.2). The actual send logic lives
in app/services/push.py (called from cases.py as a background task, and
from the escalation check below) — this module owns the endpoints.
"""
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.auth import require_role
from app.core.config import settings
from app.core.database import get_supabase_for_user, supabase_admin, extract_bearer_token
from app.services.push import push_emergency_alert
from app.api.routes.cases import limiter

logger = logging.getLogger("vitalnet")

router = APIRouter(prefix="/api/push", tags=["push"])

# Re-alert an unreviewed EMERGENCY case once it's sat this long without being
# reviewed, and again on the same interval after each escalation (tracked via
# last_escalated_at) so a case doesn't get re-notified on every scheduler tick.
ESCALATION_THRESHOLD_MINUTES = 15


class PushSubscriptionInput(BaseModel):
    endpoint: str = Field(min_length=1, max_length=2000)
    p256dh_key: str = Field(min_length=1, max_length=500)
    auth_key: str = Field(min_length=1, max_length=500)


@router.post("/subscribe")
@limiter.limit("10/minute")
async def subscribe(
    request: Request,
    body: PushSubscriptionInput,
    authorization: str = Header(None),
    user: dict = Depends(require_role("doctor", "admin")),
):
    if not settings.vapid_public_key or not settings.vapid_private_key:
        raise HTTPException(status_code=503, detail="Push notifications are not configured on this server")

    raw_token = extract_bearer_token(authorization)
    db = get_supabase_for_user(raw_token)

    db.table("push_subscriptions").upsert(
        {
            "user_id": user["sub"],
            "facility_id": user.get("resolved_facility_id"),
            "endpoint": body.endpoint,
            "p256dh_key": body.p256dh_key,
            "auth_key": body.auth_key,
        },
        on_conflict="endpoint",
    ).execute()

    return {"status": "subscribed"}


@router.delete("/subscribe")
@limiter.limit("10/minute")
async def unsubscribe(
    request: Request,
    endpoint: str,
    authorization: str = Header(None),
    user: dict = Depends(require_role("doctor", "admin")),
):
    raw_token = extract_bearer_token(authorization)
    db = get_supabase_for_user(raw_token)
    db.table("push_subscriptions").delete().eq("endpoint", endpoint).eq("user_id", user["sub"]).execute()
    return {"status": "unsubscribed"}


@router.post("/check-emergency-escalations")
@limiter.limit("6/minute")
async def check_emergency_escalations(
    request: Request,
    authorization: str = Header(None),
    user: dict = Depends(require_role("admin")),
):
    """
    Meant to be called on a schedule (e.g. every 5 minutes) by an external
    scheduler — a cron job hitting this endpoint, a Supabase pg_cron job, or
    a Railway cron add-on. Scans for EMERGENCY cases still unreviewed past
    ESCALATION_THRESHOLD_MINUTES and re-alerts the facility's doctors,
    tracking last_escalated_at so a case is escalated at most once per
    threshold interval rather than on every scheduler tick.
    """
    threshold = (datetime.now(timezone.utc) - timedelta(minutes=ESCALATION_THRESHOLD_MINUTES)).isoformat()

    query = (
        supabase_admin.table("case_records")
        .select("id, facility_id, chief_complaint, risk_driver, created_at, last_escalated_at")
        .eq("triage_level", "EMERGENCY")
        .is_("reviewed_at", "null")
        .is_("deleted_at", "null")
        .lt("created_at", threshold)
    )
    candidates = query.execute().data or []

    escalated = []
    for case in candidates:
        last_escalated_at = case.get("last_escalated_at")
        if last_escalated_at and last_escalated_at > threshold:
            continue  # already escalated within this threshold window

        push_emergency_alert(
            case.get("facility_id"),
            "EMERGENCY case still unreviewed",
            f"{case.get('chief_complaint', '')} — {case.get('risk_driver', '')}"[:150],
        )
        supabase_admin.table("case_records").update(
            {"last_escalated_at": datetime.now(timezone.utc).isoformat()}
        ).eq("id", case["id"]).execute()
        escalated.append(case["id"])

    if escalated:
        logger.info("Escalated %d unreviewed EMERGENCY case(s): %s", len(escalated), escalated)

    return {"checked": len(candidates), "escalated": len(escalated)}
