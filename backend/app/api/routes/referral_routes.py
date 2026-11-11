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

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.auth import require_role
from app.core.audit import AuditEventType, get_client_ip, log_phi_access
from app.core.database import get_supabase_for_user, extract_bearer_token
from app.api.routes.cases import limiter, _parse_uuid, _resolved_role, _resolved_facility
from app.utils.sbar import SBAR_VERSION, build_sbar

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
    "reason, urgency, sbar_version, sbar_draft, status, created_at, updated_at, "
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


class UpdateFacilityCapacityRequest(BaseModel):
    capacity_status: Literal["available", "limited", "full"]


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

    Each facility also carries `open_case_count` (unreviewed cases right
    now) and is sorted least-loaded first — a suggestion, not an
    enforcement; the doctor can still choose any facility in the list.
    """
    raw_token = extract_bearer_token(authorization)
    db = get_supabase_for_user(raw_token)
    facility_id = _resolved_facility(user)

    query = (
        db.table("facilities")
        .select("id, name, type, district, capacity_status")
        .eq("is_active", True)
        .order("name")
    )
    if facility_id:
        query = query.neq("id", facility_id)

    facilities = query.execute().data or []

    caller_district = None
    if facility_id:
        try:
            caller_fac_res = (
                db.table("facilities")
                .select("district")
                .eq("id", facility_id)
                .maybe_single()
                .execute()
            )
            if caller_fac_res and caller_fac_res.data:
                caller_district = caller_fac_res.data.get("district")
        except Exception as e:
            logger.debug("Could not resolve caller facility district: %s", e)

    # Open (unreviewed) case load per facility — a decision-support ranking
    # signal, not authoritative bed availability (docs/DECISIONS.md §20).
    # A doctor's own RLS-scoped token can only see their OWN facility's
    # case_records (by design — the whole point of RLS here), so this calls
    # fn_open_case_counts (a SECURITY DEFINER Postgres function, backend/
    # supabase/migrations/phase28_security_definer_fns.sql) through `db`
    # instead of supabase_admin. It is deliberately limited to a
    # facility_id count — no patient data, no free text, no individual
    # case rows ever leave the database.
    try:
        open_cases = db.rpc("fn_open_case_counts", {}).execute()
        load_by_facility: dict[str, int] = {}
        for row in (open_cases.data if open_cases else []) or []:
            fid = row.get("facility_id")
            if fid:
                load_by_facility[fid] = row.get("open_count", 0)
    except Exception as e:
        logger.debug("Could not fetch open case counts: %s", e)
        load_by_facility = {}

    for f in facilities:
        f["open_case_count"] = load_by_facility.get(f["id"], 0)

    # Ordering prioritized by:
    # 1. Tier hierarchy: district_hospital (0) < chc (2) < phc (3) (BUG-28)
    # 2. District proximity: same district as caller facility prioritized
    # 3. Capacity status rank: available (0) < limited/null (1) < full (2)
    # 4. Open case load ascending
    # 5. Name alphabetically
    tier_rank = {
        "district_hospital": 0,
        "sdh": 1,
        "sub_district_hospital": 1,
        "chc": 2,
        "phc": 3,
        "sub_centre": 4,
    }
    capacity_rank = {"available": 0, "limited": 1, "full": 2}

    facilities.sort(
        key=lambda f: (
            tier_rank.get((f.get("type") or "").lower(), 99),
            0 if (caller_district and f.get("district") == caller_district) else 1,
            capacity_rank.get(f.get("capacity_status") or "limited", 1),
            f.get("open_case_count", 0),
            f.get("name") or "",
        )
    )

    return facilities


# ── Facility self-reported capacity ────────────────────────────────────────────


@router.patch("/api/facilities/{facility_id}/capacity")
@limiter.limit("30/minute")
async def update_facility_capacity(
    request: Request,
    facility_id: str,
    body: UpdateFacilityCapacityRequest,
    authorization: str = Header(None),
    user: dict = Depends(require_role("doctor", "admin")),
):
    """
    Self-reported capacity status (docs/DECISIONS.md §19) — a doctor can
    only update their OWN facility; admin can update any. Not derived from
    a real bed-management system this project doesn't have; a referring
    doctor sees it as one more signal in the facility picker, not an
    automated capacity check.
    """
    facility_uuid = _parse_uuid(facility_id, "facility_id")
    raw_token = extract_bearer_token(authorization)
    db = get_supabase_for_user(raw_token)
    role = _resolved_role(user)
    own_facility_id = _resolved_facility(user)

    if role != "admin" and (not own_facility_id or own_facility_id != facility_uuid):
        raise HTTPException(status_code=403, detail="Can only update your own facility's capacity")

    update_result = (
        db.table("facilities")
        .update({
            "capacity_status": body.capacity_status,
            "capacity_updated_at": datetime.now(timezone.utc).isoformat(),
        })
        .eq("id", facility_uuid)
        .execute()
    )
    if not update_result.data:
        raise HTTPException(status_code=404, detail="Facility not found")

    log_phi_access(
        event_type=AuditEventType.PHI_UPDATE,
        user_id=user.get("sub", "unknown"),
        user_role=role,
        resource_type="facilities",
        resource_id=facility_uuid,
        facility_id=facility_uuid,
        ip_address=get_client_ip(request),
        details={"capacity_status": body.capacity_status},
    )

    return update_result.data[0]


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
    raw_token = extract_bearer_token(authorization)
    db = get_supabase_for_user(raw_token)
    role = _resolved_role(user)
    facility_id = _resolved_facility(user)

    case_result = (
        db.table("case_records")
        .select(
            "id, facility_id, deleted_at, patient_age, patient_sex, chief_complaint, "
            "complaint_duration, known_conditions, current_medications, symptoms, "
            "bp_systolic, bp_diastolic, spo2, heart_rate, temperature, triage_level, "
            "risk_driver, contraindication_flags, deterioration_alert"
        )
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

    # Check for existing active referral on the same case (BUG-36)
    try:
        existing_active = (
            db.table("referrals")
            .select("id, status")
            .eq("case_id", case_uuid)
            .in_("status", ["pending", "acknowledged", "patient_arrived"])
            .limit(1)
            .execute()
        )
        if existing_active and existing_active.data:
            active_ref = existing_active.data[0]
            raise HTTPException(
                status_code=409,
                detail=f"An active referral already exists for this case (id: {active_ref.get('id')}, status: {active_ref.get('status')})",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Could not query existing active referrals: %s", e)

    sbar_draft = build_sbar(case_row, {"reason": body.reason, "urgency": body.urgency})
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
                "sbar_version": SBAR_VERSION,
                "sbar_draft": sbar_draft,
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
    raw_token = extract_bearer_token(authorization)
    db = get_supabase_for_user(raw_token)
    role = _resolved_role(user)
    facility_id = _resolved_facility(user)

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
    raw_token = extract_bearer_token(authorization)
    db = get_supabase_for_user(raw_token)
    role = _resolved_role(user)
    facility_id = _resolved_facility(user)

    existing = (
        db.table("referrals")
        .select("id, case_id, receiving_facility_id, referring_facility_id, status")
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

    # ADR §53: Automated post-discharge follow-up task generation
    # When receiving hospital doctor marks referral as completed, schedule
    # 48-hour follow-up task for the originating community worker.
    if body.status == "completed" and row.get("case_id"):
        try:
            db.rpc(
                "fn_mark_referral_followup_due",
                {"p_case_id": row["case_id"], "p_referral_id": referral_uuid},
            ).execute()
        except Exception as e:
            logger.warning("Could not execute fn_mark_referral_followup_due RPC: %s", e)

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
