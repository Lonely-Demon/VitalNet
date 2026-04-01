"""
VitalNet Cases Router — all patient case endpoints.
Extracted from main.py as part of Phase 12 architectural modularisation.
"""
import hashlib
import logging
import uuid as uuid_lib
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.auth import require_role
from app.core.audit import AuditEventType, get_client_ip, log_phi_access
from app.core.database import get_supabase_for_user
from app.models.schemas import IntakeForm
from app.ml.classifier import run_triage
from app.services.llm import generate_briefing

import re

logger = logging.getLogger("vitalnet")

router = APIRouter()


def _header_or_401(value: str | None) -> str:
    if value is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    return value


def _sanitize_medical_text(value: str | None, max_length: int = 500) -> str | None:
    if value is None:
        return None
    cleaned = re.sub(r"[\x00-\x1f\x7f]", " ", value)
    cleaned = re.sub(r"<[^>]+>", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:max_length] if cleaned else None


def _get_user_id(request: Request) -> str:
    """
    Extract the Supabase user ID (sub) from the Bearer JWT for rate limiting.
    Falls back to client IP if the token is absent or malformed —
    this prevents unauthenticated callers from bypassing the limiter.
    """
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()
        if token:
            return hashlib.sha256(token.encode("utf-8")).hexdigest()[:24]
    return get_remote_address(request)


def _extract_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    parts = authorization.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(status_code=401, detail="Malformed Authorization header")
    return parts[1].strip()


def _parse_uuid(value: str, field: str = "id") -> str:
    try:
        return str(UUID(value))
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid {field}")


def _normalized_iso_ts(value: str, field: str) -> str:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid {field}")


def _resolved_role(user: dict) -> str:
    return (user.get("resolved_role") or "").strip()


def _resolved_facility(user: dict) -> str | None:
    return user.get("resolved_facility_id")


def _authorize_case_row_access(user: dict, row: dict) -> None:
    role = _resolved_role(user)
    user_id = user.get("sub")
    facility_id = _resolved_facility(user)

    if role in {"admin", "super_admin"}:
        return
    if role in {"doctor", "facility_admin"} and facility_id and facility_id == row.get("facility_id"):
        return
    if role == "asha_worker" and row.get("submitted_by") == user_id:
        return
    raise HTTPException(status_code=403, detail="Not authorized for this case")


limiter = Limiter(key_func=_get_user_id)


# ── Submit Case ────────────────────────────────────────────────────────────────


@router.post("/api/submit")
@limiter.limit("20/minute")   # 20 per authenticated user per minute
async def submit_case(
    request: Request,       # required first positional param for slowapi
    form: IntakeForm,
    authorization: str = Header(None),
    user: dict = Depends(require_role("asha_worker", "facility_admin", "admin", "super_admin")),
):
    form_data = form.model_dump()
    for field in ("patient_name", "chief_complaint", "observations", "known_conditions", "current_medications", "location"):
        if field in form_data:
            form_data[field] = _sanitize_medical_text(form_data[field], 500 if field != "chief_complaint" else 200) or form_data[field]

    role = _resolved_role(user)
    facility_id = _resolved_facility(user)

    if role in {"asha_worker", "doctor", "facility_admin"} and not facility_id:
        raise HTTPException(status_code=403, detail="User is not assigned to a facility")

    if form.human_review_requested and not (form.human_review_reason or "").strip():
        raise HTTPException(status_code=400, detail="human_review_reason is required when review is requested")

    # Step 1: Classifier + SHAP (always runs — LLM-independent)
    try:
        triage_result = run_triage(form_data)
        briefing = await generate_briefing(form_data, triage_result)
        raw_token = _extract_token(_header_or_401(authorization))
        db = get_supabase_for_user(raw_token)

        record = {
            "client_id": str(form.client_id or uuid_lib.uuid4()),
            "submitted_by": user["sub"],
            "facility_id": facility_id,
            "patient_name": form.patient_name,
            "patient_age": form.patient_age,
            "patient_sex": form.patient_sex,
            "patient_location": form.location,
            "bp_systolic": form.bp_systolic,
            "bp_diastolic": form.bp_diastolic,
            "spo2": form.spo2,
            "heart_rate": form.heart_rate,
            "temperature": float(form.temperature)
            if form.temperature is not None
            else None,
            "chief_complaint": form.chief_complaint,
            "complaint_duration": form.complaint_duration,
            "symptoms": form.symptoms or [],
            "observations": form.observations,
            "known_conditions": form.known_conditions,
            "current_medications": form.current_medications,
            "human_review_requested": form.human_review_requested,
            "human_review_reason": form.human_review_reason,
            "triage_level": triage_result["triage_level"],
            "triage_confidence": triage_result["confidence_score"],
            "risk_driver": triage_result["risk_driver"],
            "llm_status": briefing.get("llm_status", "generated"),
            "needs_review": bool(briefing.get("needs_review") or triage_result.get("needs_review")),
            "briefing": briefing,
            "llm_model_used": briefing.get("_model_used", "unknown"),
            "created_offline": form.created_offline,
            "client_submitted_at": form.client_submitted_at.isoformat()
            if form.client_submitted_at
            else None,
        }

        result = (
            db.table("case_records")
            .upsert(record, on_conflict="client_id", ignore_duplicates=True)
            .execute()
        )
        if not result.data:
            # Upsert ignored the duplicate; fetch the existing row to return to client
            existing = (
                db.table("case_records")
                .select(
                    "id, client_id, triage_level, triage_confidence, risk_driver, "
                    "created_at, created_offline, facility_id"
                )
                .eq("client_id", record["client_id"])
                .execute()
            )
            response = existing.data[0] if existing.data else record
        else:
            response = result.data[0]

        log_phi_access(
            event_type=AuditEventType.PHI_CREATE,
            user_id=user.get("sub", "unknown"),
            user_role=role,
            resource_type="case_records",
            resource_id=response.get("id") if isinstance(response, dict) else None,
            facility_id=facility_id,
            ip_address=get_client_ip(request),
            details={"created_offline": bool(form.created_offline), "needs_review": bool(record.get("needs_review"))},
        )

        return response
    except HTTPException:
        raise
    except Exception:
        logger.error(
            "submit_case failed",
            extra={"client_id": str(form.client_id) if form.client_id else None, "user_id": user.get("sub")},
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="An internal server error occurred. The case was not saved. Please retry.",
        )


# ── Get Cases ──────────────────────────────────────────────────────────────────


@router.get("/api/cases")
async def get_cases(
    authorization: str = Header(None),
    user: dict = Depends(require_role("doctor", "facility_admin", "admin", "super_admin")),
    before_time: str | None = None,       # ISO timestamp of the last seen case
    before_priority: int | None = None,   # triage_priority of the last seen case (0/1/2)
    limit: int = 25,
):
    """
    Cursor-based pagination with composite keyset for the Doctor Dashboard.

    Sort order: EMERGENCY (0) → URGENT (1) → ROUTINE (2) first,
    then by created_at DESC within each tier.

    Use before_time + before_priority from the previous page's
    nextCursor / nextTriagePriority to fetch the next page.
    The composite cursor correctly handles cases at tier boundaries
    without silent data loss.
    """
    raw_token = _extract_token(_header_or_401(authorization))
    db = get_supabase_for_user(raw_token)
    role = _resolved_role(user)
    facility_id = _resolved_facility(user)

    # Safety cap
    limit = max(1, min(limit, 100))
    if before_priority is not None and before_priority not in {0, 1, 2}:
        raise HTTPException(status_code=400, detail="Invalid before_priority")

    normalized_before_time = None
    if before_time is not None:
        normalized_before_time = _normalized_iso_ts(before_time, "before_time")

    query = (
        db.table("case_records")
        .select(
            "id, patient_name, patient_age, patient_sex, "
            "triage_level, triage_priority, triage_confidence, risk_driver, "
            "created_at, reviewed_at, reviewed_by, facility_id, created_offline"
        )
        .is_("deleted_at", "null")
        .order("triage_priority", desc=False)   # EMERGENCY (0) first
        .order("created_at", desc=True)          # Newest within each tier
        .limit(limit + 1)                        # Fetch one extra to determine hasMore
    )

    if role in {"doctor", "facility_admin"}:
        if not facility_id:
            raise HTTPException(status_code=403, detail="User is not assigned to a facility")
        query = query.eq("facility_id", facility_id)

    if normalized_before_time is not None and before_priority is not None:
        # Composite keyset cursor — correct two-column keyset pagination.
        query = query.or_(
            f"triage_priority.gt.{before_priority},"
            f"and(triage_priority.eq.{before_priority},created_at.lt.{normalized_before_time})"
        )

    result = query.execute()
    rows = result.data

    has_more = len(rows) > limit
    cases = rows[:limit]

    return {
        "cases": cases,
        "hasMore": has_more,
        "nextCursor": cases[-1]["created_at"] if has_more and cases else None,
        "nextTriagePriority": cases[-1]["triage_priority"] if has_more and cases else None,
    }


# ── Review Case ────────────────────────────────────────────────────────────────


@router.patch("/api/cases/{case_id}/review")
async def review_case(
    request: Request,
    case_id: str,
    authorization: str = Header(None),
    user: dict = Depends(require_role("doctor", "facility_admin", "admin", "super_admin")),
):
    case_uuid = _parse_uuid(case_id, "case_id")
    raw_token = _extract_token(_header_or_401(authorization))
    db = get_supabase_for_user(raw_token)
    role = _resolved_role(user)

    case_result = (
        db.table("case_records")
        .select("id, facility_id, submitted_by, deleted_at")
        .eq("id", case_uuid)
        .maybe_single()
        .execute()
    )
    case_row = (case_result.data if case_result else None) or {}
    if not case_row or case_row.get("deleted_at") is not None:
        raise HTTPException(status_code=404, detail="Case not found")

    _authorize_case_row_access(user, case_row)

    update_result = db.table("case_records").update(
        {
            "reviewed_by": user["sub"],
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        }
    ).eq("id", case_uuid).is_("deleted_at", "null").execute()

    if not update_result.data:
        raise HTTPException(status_code=409, detail="Case could not be reviewed")

    db.table("case_reviews").insert(
        {
            "case_id": case_uuid,
            "reviewer_id": user["sub"],
            "note": "Marked reviewed via API",
        }
    ).execute()

    log_phi_access(
        event_type=AuditEventType.PHI_UPDATE,
        user_id=user.get("sub", "unknown"),
        user_role=role,
        resource_type="case_records",
        resource_id=case_uuid,
        facility_id=case_row.get("facility_id"),
        ip_address=get_client_ip(request),
        details={"action": "review"},
    )

    return {"status": "reviewed"}


# ── ASHA: My Submissions ───────────────────────────────────────────────────────


@router.get("/api/cases/mine")
async def get_my_cases(
    authorization: str = Header(None),
    user: dict = Depends(require_role("asha_worker", "facility_admin", "admin", "super_admin")),
    before: str | None = None,   # created_at ISO cursor
    limit: int = 25,
):
    """
    Returns the calling user's own submitted cases with cursor pagination.
    Sorted by created_at DESC only (chronological — no priority sort for personal history).
    RLS enforces ownership at DB level; the explicit filter is for clarity.
    Returns a limited column set — full briefing JSONB is doctor-facing only.
    """
    raw_token = _extract_token(_header_or_401(authorization))
    db = get_supabase_for_user(raw_token)
    limit = max(1, min(limit, 100))

    normalized_before = _normalized_iso_ts(before, "before") if before else None

    query = (
        db.table("case_records")
        .select(
            "id, patient_name, chief_complaint, triage_level, "
            "created_at, reviewed_at, patient_age, patient_sex"
        )
        .eq("submitted_by", user["sub"])
        .is_("deleted_at", "null")
        .order("created_at", desc=True)
        .limit(limit + 1)
    )

    if normalized_before:
        query = query.lt("created_at", normalized_before)

    result = query.execute()
    rows = result.data
    has_more = len(rows) > limit

    return {
        "cases": rows[:limit],
        "hasMore": has_more,
        "nextCursor": rows[limit - 1]["created_at"] if has_more and rows else None,
    }


# ── Get Case Detail ───────────────────────────────────────────────────────────────


@router.get("/api/cases/{case_id}")
async def get_case_detail(
    request: Request,
    case_id: str,
    authorization: str = Header(None),
    user: dict = Depends(require_role("asha_worker", "doctor", "facility_admin", "admin", "super_admin")),
):
    """Returns one case after explicit ownership/facility authorization checks."""
    case_uuid = _parse_uuid(case_id, "case_id")
    raw_token = _extract_token(_header_or_401(authorization))
    db = get_supabase_for_user(raw_token)
    result = (
        db.table("case_records")
        .select(
            "id, patient_name, patient_age, patient_sex, patient_location, chief_complaint, "
            "complaint_duration, symptoms, observations, known_conditions, current_medications, "
            "triage_level, triage_priority, triage_confidence, risk_driver, briefing, llm_model_used, "
            "reviewed_by, reviewed_at, submitted_by, facility_id, created_at, client_id, created_offline"
        )
        .eq("id", case_uuid)
        .maybe_single()
        .execute()
    )
    row = (result.data if result else None) or {}
    if not row:
        raise HTTPException(status_code=404, detail="Case not found")

    _authorize_case_row_access(user, row)

    log_phi_access(
        event_type=AuditEventType.PHI_READ,
        user_id=user.get("sub", "unknown"),
        user_role=_resolved_role(user),
        resource_type="case_records",
        resource_id=case_uuid,
        facility_id=row.get("facility_id"),
        ip_address=get_client_ip(request),
        details={"view": "detail"},
    )

    return row
