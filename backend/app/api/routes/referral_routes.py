"""
Inter-facility referral workflow (FEATURES_ROADMAP §2.3). A PHC doctor's
real-world action on a severe case is often "stabilize and refer to a higher
facility" rather than "treat here" — this represents that as a first-class
workflow object distinct from case review, so a referred case has a tracked
status beyond just reviewed/unreviewed.
"""
import logging
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.auth import require_role
from app.core.audit import AuditEventType, get_client_ip, log_phi_access
from app.core.database import get_supabase_for_user
from app.api.routes.cases import limiter

logger = logging.getLogger("vitalnet")

router = APIRouter(tags=["referrals"])

# Forward-only state machine; 'cancelled' is reachable from any active state.
ALLOWED_TRANSITIONS = {
    "pending": {"acknowledged", "cancelled"},
    "acknowledged": {"patient_arrived", "cancelled"},
    "patient_arrived": {"completed", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}

REFERRAL_SELECT_COLUMNS = (
    "id, case_id, referred_by, referring_facility_id, receiving_facility_id, "
    "reason, urgency, status, created_at, updated_at, "
    "case_records(chief_complaint, patient_age, patient_sex, triage_level), "
    "referring_facility:facilities!referring_facility_id(name), "
    "receiving_facility:facilities!receiving_facility_id(name)"
)


class CreateReferralRequest(BaseModel):
    receiving_facility_id: str
    reason: str = Field(min_length=1, max_length=1000)
    urgency: Literal["ROUTINE", "URGENT", "EMERGENCY"]


class UpdateReferralStatusRequest(BaseModel):
    status: Literal["acknowledged", "patient_arrived", "completed", "cancelled"]


def _parse_uuid(value: str, field: str = "id") -> str:
    try:
        return str(UUID(value))
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid {field}")


# ── Facility picker (for the referral target dropdown) ────────────────────────


@router.get("/api/facilities")
@limiter.limit("60/minute")
async def list_active_facilities(
    request: Request,
    authorization: str = Header(None),
    user: dict = Depends(require_role("doctor", "admin")),
):
    """
    Active facilities for the referral target picker (BriefingCard.jsx).
    Unlike /api/admin/facilities this is doctor-accessible, not admin-only —
    a doctor initiating a referral needs to see where they can send a
    patient. Returns every active facility except the caller's own (you
    can't refer to yourself); no tier-based filtering is applied since
    `facilities.type` is free text with no defined ordering yet — enforcing
    one now could incorrectly hide a legitimate destination (e.g. a lateral
    PHC-to-PHC referral for capacity reasons).
    """
    raw_token = (authorization or "").split(" ", 1)[-1]
    db = get_supabase_for_user(raw_token)
    facility_id = user.get("resolved_facility_id")

    query = (
        db.table("facilities")
        .select("id, name, type, district")
        .eq("is_active", True)
        .order("name")
    )
    if facility_id:
        query = query.neq("id", facility_id)

    result = query.execute()
    return result.data or []


# ── Create referral ────────────────────────────────────────────────────────────


@router.post("/api/cases/{case_id}/refer")
@limiter.limit("20/minute")
async def create_referral(
    request: Request,
    case_id: str,
    body: CreateReferralRequest,
    authorization: str = Header(None),
    user: dict = Depends(require_role("doctor", "admin")),
):
    """
    Records a referral of `case_id` to `receiving_facility_id`. Scoped the
    same way as review_case (cases.py): a doctor can only refer a case in
    their own facility; admin is global.
    """
    case_uuid = _parse_uuid(case_id, "case_id")
    receiving_facility_uuid = _parse_uuid(body.receiving_facility_id, "receiving_facility_id")
    raw_token = (authorization or "").split(" ", 1)[-1]
    db = get_supabase_for_user(raw_token)
    role = user.get("resolved_role") or ""
    facility_id = user.get("resolved_facility_id")

    case_result = (
        db.table("case_records")
        .select("id, facility_id, deleted_at")
        .eq("id", case_uuid)
        .maybe_single()
        .execute()
    )
    case_row = (case_result.data if case_result else None) or {}
    if not case_row or case_row.get("deleted_at") is not None:
        raise HTTPException(status_code=404, detail="Case not found")

    if role != "admin" and (not facility_id or facility_id != case_row.get("facility_id")):
        raise HTTPException(status_code=403, detail="Not authorized for this case")

    referring_facility_id = case_row.get("facility_id")
    if not referring_facility_id:
        raise HTTPException(status_code=400, detail="Case has no facility to refer from")
    if receiving_facility_uuid == referring_facility_id:
        raise HTTPException(status_code=400, detail="Cannot refer a case to its own facility")

    result = (
        db.table("referrals")
        .insert(
            {
                "case_id": case_uuid,
                "referred_by": user["sub"],
                "referring_facility_id": referring_facility_id,
                "receiving_facility_id": receiving_facility_uuid,
                "reason": body.reason,
                "urgency": body.urgency,
            }
        )
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create referral")

    log_phi_access(
        event_type=AuditEventType.PHI_CREATE,
        user_id=user.get("sub", "unknown"),
        user_role=role,
        resource_type="referrals",
        resource_id=result.data[0]["id"],
        facility_id=referring_facility_id,
        ip_address=get_client_ip(request),
        details={"case_id": case_uuid, "receiving_facility_id": receiving_facility_uuid, "urgency": body.urgency},
    )

    return result.data[0]


# ── List referrals (outgoing + incoming) ───────────────────────────────────────


@router.get("/api/referrals")
@limiter.limit("60/minute")
async def list_referrals(
    request: Request,
    authorization: str = Header(None),
    user: dict = Depends(require_role("doctor", "admin")),
    direction: Literal["outgoing", "incoming", "all"] = "all",
):
    """
    Referrals visible to the caller: admin sees all; a doctor sees referrals
    where their facility is on the referring or receiving side (direction
    filters which). A doctor with no facility_id sees nothing, matching the
    scoping convention used by get_cases/review_case elsewhere.
    """
    raw_token = (authorization or "").split(" ", 1)[-1]
    db = get_supabase_for_user(raw_token)
    role = user.get("resolved_role") or ""
    facility_id = user.get("resolved_facility_id")

    if role != "admin" and not facility_id:
        return {"referrals": []}

    query = (
        db.table("referrals")
        .select(REFERRAL_SELECT_COLUMNS)
        .order("created_at", desc=True)
        .limit(200)
    )

    if role != "admin":
        if direction == "outgoing":
            query = query.eq("referring_facility_id", facility_id)
        elif direction == "incoming":
            query = query.eq("receiving_facility_id", facility_id)
        else:
            query = query.or_(f"referring_facility_id.eq.{facility_id},receiving_facility_id.eq.{facility_id}")

    result = query.execute()
    return {"referrals": result.data or []}


# ── Advance referral status ────────────────────────────────────────────────────


@router.patch("/api/referrals/{referral_id}/status")
@limiter.limit("30/minute")
async def update_referral_status(
    request: Request,
    referral_id: str,
    body: UpdateReferralStatusRequest,
    authorization: str = Header(None),
    user: dict = Depends(require_role("doctor", "admin")),
):
    """
    Advances a referral's status. Only the RECEIVING facility's doctor (or
    admin) may advance it — the referring side made the referral, the
    receiving side owns what happens to the patient next. Enforces the
    forward-only ALLOWED_TRANSITIONS state machine.
    """
    referral_uuid = _parse_uuid(referral_id, "referral_id")
    raw_token = (authorization or "").split(" ", 1)[-1]
    db = get_supabase_for_user(raw_token)
    role = user.get("resolved_role") or ""
    facility_id = user.get("resolved_facility_id")

    existing = (
        db.table("referrals")
        .select("id, receiving_facility_id, referring_facility_id, status")
        .eq("id", referral_uuid)
        .maybe_single()
        .execute()
    )
    row = (existing.data if existing else None) or {}
    if not row:
        raise HTTPException(status_code=404, detail="Referral not found")

    if role != "admin" and (not facility_id or facility_id != row.get("receiving_facility_id")):
        raise HTTPException(status_code=403, detail="Only the receiving facility can update this referral")

    current_status = row.get("status")
    if body.status not in ALLOWED_TRANSITIONS.get(current_status, set()):
        raise HTTPException(status_code=409, detail=f"Cannot transition from {current_status} to {body.status}")

    update_result = (
        db.table("referrals")
        .update({"status": body.status, "updated_at": datetime.now(timezone.utc).isoformat()})
        .eq("id", referral_uuid)
        .eq("status", current_status)  # optimistic concurrency (matches toggle_facility's pattern)
        .execute()
    )
    if not update_result.data:
        raise HTTPException(status_code=409, detail="Referral was modified concurrently. Please retry.")

    log_phi_access(
        event_type=AuditEventType.PHI_UPDATE,
        user_id=user.get("sub", "unknown"),
        user_role=role,
        resource_type="referrals",
        resource_id=referral_uuid,
        facility_id=facility_id,
        ip_address=get_client_ip(request),
        details={"status": body.status},
    )

    return update_result.data[0]
