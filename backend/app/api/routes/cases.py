"""
VitalNet Cases Router — all patient case endpoints.
Extracted from main.py as part of Phase 12 architectural modularisation.
"""
import logging
import re
import uuid as uuid_lib
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from slowapi import Limiter

from app.core.auth import require_role, verify_sub_for_rate_limit
from app.core.audit import AuditEventType, get_client_ip, log_phi_access
from app.core.config import settings
from app.core.database import get_supabase_for_user
from app.models.schemas import IntakeForm, TriageOverride, CaseOutcomeInput
from app.ml.classifier import run_triage
from app.services.llm import generate_briefing

logger = logging.getLogger("vitalnet")

router = APIRouter()


def _get_user_id(request: Request) -> str:
    """
    Rate-limit key: the caller's VERIFIED Supabase user id (sub), so a clinic's
    workers sharing one NATed IP each get their own budget. Uses signature-
    verified extraction — an attacker cannot forge a token carrying a victim's
    sub to burn the victim's budget. Falls back to client IP when the token is
    absent or its signature can't be verified locally (e.g. asymmetric-key
    projects), which also stops unauthenticated callers from bypassing the limiter.
    """
    auth_header = request.headers.get("authorization", "")
    token = auth_header.split(" ", 1)[-1] if auth_header else ""
    sub = verify_sub_for_rate_limit(token) if token else None
    return sub or (request.client.host if request.client else "unknown")


# storage_uri empty -> slowapi's default in-memory store. Set
# RATE_LIMIT_STORAGE_URI (e.g. redis://...) in multi-instance production so the
# limit is shared across workers/instances rather than per-process.
_limiter_kwargs = {"key_func": _get_user_id}
if settings.rate_limit_storage_uri:
    _limiter_kwargs["storage_uri"] = settings.rate_limit_storage_uri
limiter = Limiter(**_limiter_kwargs)


def _sanitize_medical_text(value: str | None, max_length: int = 500) -> str | None:
    """
    Defense-in-depth on top of the schema-level control-char stripping
    (app/models/schemas.py): also strips embedded HTML/markup tags before the
    text reaches the DB, the LLM prompt, or a doctor's browser.
    """
    if value is None:
        return None
    cleaned = re.sub(r"<[^>]+>", "", value)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:max_length] if cleaned else None


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
    return user.get("resolved_role") or ""


def _resolved_facility(user: dict) -> str | None:
    return user.get("resolved_facility_id")


def _authorize_case_row_access(user: dict, row: dict) -> None:
    """
    Fine-grained, row-level authorization for a single case, on top of the
    endpoint's require_role() gate: 'admin' is global; 'doctor' is scoped to
    their own facility_id; 'asha_worker' is scoped to cases they submitted.
    """
    role = _resolved_role(user)
    user_id = user.get("sub")
    facility_id = _resolved_facility(user)

    if role == "admin":
        return
    if role == "doctor" and facility_id and facility_id == row.get("facility_id"):
        return
    if role == "asha_worker" and row.get("submitted_by") == user_id:
        return
    raise HTTPException(status_code=403, detail="Not authorized for this case")


# ── Submit Case ────────────────────────────────────────────────────────────────


@router.post("/api/submit")
@limiter.limit("20/minute")   # 20 per authenticated user per minute
async def submit_case(
    request: Request,       # required first positional param for slowapi
    form: IntakeForm,
    authorization: str = Header(None),
    user: dict = Depends(require_role("asha_worker", "admin")),
):
    form_data = form.model_dump()
    for field in ("patient_name", "chief_complaint", "observations", "known_conditions", "current_medications", "location"):
        if field in form_data:
            form_data[field] = _sanitize_medical_text(form_data[field], 500 if field != "chief_complaint" else 200) or form_data[field]

    role = _resolved_role(user)
    facility_id = _resolved_facility(user)

    if role == "asha_worker" and not facility_id:
        raise HTTPException(status_code=403, detail="User is not assigned to a facility")

    if form.human_review_requested and not (form.human_review_reason or "").strip():
        raise HTTPException(status_code=400, detail="human_review_reason is required when review is requested")

    # Step 1: Classifier + SHAP (always runs — LLM-independent)
    try:
        triage_result = run_triage(form_data)
        briefing = await generate_briefing(form_data, triage_result)
        raw_token = (authorization or "").split(" ", 1)[-1]
        db = get_supabase_for_user(raw_token)

        record = {
            "client_id": str(form.client_id or uuid_lib.uuid4()),
            "submitted_by": user["sub"],
            "facility_id": facility_id,
            "patient_name": form_data.get("patient_name", form.patient_name),
            "patient_age": form.patient_age,
            "patient_sex": form.patient_sex,
            "patient_location": form_data.get("location", form.location),
            "bp_systolic": form.bp_systolic,
            "bp_diastolic": form.bp_diastolic,
            "spo2": form.spo2,
            "heart_rate": form.heart_rate,
            "temperature": float(form.temperature)
            if form.temperature is not None
            else None,
            "chief_complaint": form_data.get("chief_complaint", form.chief_complaint),
            "complaint_duration": form.complaint_duration,
            "symptoms": form.symptoms or [],
            "observations": form_data.get("observations", form.observations),
            "known_conditions": form_data.get("known_conditions", form.known_conditions),
            "current_medications": form_data.get("current_medications", form.current_medications),
            "human_review_requested": form.human_review_requested,
            "human_review_reason": form.human_review_reason,
            "consent_captured": form.consent_captured,
            "consent_captured_at": form.consent_captured_at.isoformat()
            if form.consent_captured_at
            else datetime.now(timezone.utc).isoformat(),
            "triage_level": triage_result["triage_level"],
            "triage_confidence": triage_result["confidence_score"],
            "risk_driver": triage_result["risk_driver"],
            "triage_model_version": triage_result.get("model_version"),
            "low_confidence": bool(triage_result.get("low_confidence")),
            "llm_status": briefing.get("llm_status", "generated"),
            "needs_review": bool(briefing.get("needs_review") or form.human_review_requested),
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
    except Exception as e:
        logger.error(
            "submit_case failed for client_id=%s: %s",
            form.client_id, e,
            exc_info=True,   # attaches full traceback to the log record
        )
        raise HTTPException(
            status_code=500,
            detail="An internal server error occurred. The case was not saved. Please retry.",
        )


# ── Get Cases ──────────────────────────────────────────────────────────────────


@router.get("/api/cases")
@limiter.limit("60/minute")
async def get_cases(
    request: Request,
    authorization: str = Header(None),
    user: dict = Depends(require_role("doctor", "admin")),
    before_time: str | None = None,       # ISO timestamp of the last seen case
    before_priority: int | None = None,   # triage_priority of the last seen case (0/1/2)
    before_id: str | None = None,         # id of the last seen case (unique tie-breaker)
    limit: int = 25,
):
    """
    Cursor-based pagination with composite keyset for the Doctor Dashboard.

    Sort order: EMERGENCY (0) → URGENT (1) → ROUTINE (2) first,
    then by created_at DESC within each tier, then by id DESC as a unique
    tie-breaker (handles multiple cases with an identical created_at).

    Use before_time + before_priority + before_id from the previous page's
    nextCursor / nextTriagePriority / nextId to fetch the next page.

    Scoping: 'admin' sees all facilities (global). 'doctor' accounts with a
    facility_id are scoped to that facility only. Doctors without a
    facility_id assigned see all cases (unscoped), same as before this
    endpoint had scoping.
    """
    raw_token = (authorization or "").split(" ", 1)[-1]
    db = get_supabase_for_user(raw_token)
    role = _resolved_role(user)
    facility_id = _resolved_facility(user)

    # Safety cap
    limit = max(1, min(limit, 100))
    if before_priority is not None and before_priority not in {0, 1, 2}:
        raise HTTPException(status_code=400, detail="Invalid before_priority")

    normalized_before_time = _normalized_iso_ts(before_time, "before_time") if before_time is not None else None
    parsed_before_id = _parse_uuid(before_id, "before_id") if before_id else None

    query = (
        db.table("case_records")
        .select(
            "id, patient_name, patient_age, patient_sex, patient_location, chief_complaint, "
            "triage_level, triage_priority, triage_confidence, risk_driver, briefing, "
            "low_confidence, needs_review, human_review_requested, human_review_reason, "
            "triage_model_version, overridden_triage, override_reason, overridden_by, overridden_at, "
            "created_at, reviewed_at, reviewed_by, facility_id, created_offline"
        )
        .is_("deleted_at", "null")
        .order("triage_priority", desc=False)   # EMERGENCY (0) first
        .order("created_at", desc=True)          # Newest within each tier
        .order("id", desc=True)                  # Unique tie-breaker for stable pagination
        .limit(limit + 1)                        # Fetch one extra to determine hasMore
    )

    if role == "doctor" and facility_id:
        query = query.eq("facility_id", facility_id)

    if normalized_before_time is not None and before_priority is not None:
        # Composite keyset cursor with unique tie-breaker.
        if parsed_before_id is not None:
            query = query.or_(
                f"triage_priority.gt.{before_priority},"
                f"and(triage_priority.eq.{before_priority},created_at.lt.{normalized_before_time}),"
                f"and(triage_priority.eq.{before_priority},created_at.eq.{normalized_before_time},id.lt.{parsed_before_id})"
            )
        else:
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
        "nextId": cases[-1]["id"] if has_more and cases else None,
    }


# ── Review Case ────────────────────────────────────────────────────────────────


@router.patch("/api/cases/{case_id}/review")
@limiter.limit("60/minute")
async def review_case(
    request: Request,
    case_id: str,
    authorization: str = Header(None),
    user: dict = Depends(require_role("doctor", "admin")),
):
    """
    Marks a case reviewed. Scoped the same way as GET /api/cases: 'admin'
    is global, 'doctor' with a facility_id can only review cases in their
    own facility (matches the visibility scoping — a doctor should not be
    able to act on a case they cannot see in their normal case list, even
    if they somehow obtained its id).
    """
    case_uuid = _parse_uuid(case_id, "case_id")
    raw_token = (authorization or "").split(" ", 1)[-1]
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

    # Confirm persistence (not just that the row was found) before reporting success
    if not update_result.data:
        raise HTTPException(status_code=409, detail="Case could not be reviewed or already deleted")

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

    return {"status": "reviewed", "case_id": case_uuid, "reviewed_by": user["sub"]}


# ── Triage Override ──────────────────────────────────────────────────────────────


@router.patch("/api/cases/{case_id}/triage-override")
@limiter.limit("30/minute")
async def override_triage(
    request: Request,
    case_id: str,
    body: TriageOverride,
    authorization: str = Header(None),
    user: dict = Depends(require_role("doctor", "admin")),
):
    """
    Lets a reviewing doctor correct the ML triage tier with a required reason.
    This is the primary real-label source for the outcome-retraining loop
    (FEATURES_ROADMAP §1.3) — the override is never hidden, always shown with
    its provenance (who, when, why) alongside the original ML tier.
    Scoped the same way as review_case.
    """
    case_uuid = _parse_uuid(case_id, "case_id")
    raw_token = (authorization or "").split(" ", 1)[-1]
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
            "overridden_triage": body.overridden_triage,
            "override_reason": body.override_reason,
            "overridden_by": user["sub"],
            "overridden_at": datetime.now(timezone.utc).isoformat(),
        }
    ).eq("id", case_uuid).is_("deleted_at", "null").execute()

    if not update_result.data:
        raise HTTPException(status_code=409, detail="Case could not be updated or already deleted")

    log_phi_access(
        event_type=AuditEventType.PHI_UPDATE,
        user_id=user.get("sub", "unknown"),
        user_role=role,
        resource_type="case_records",
        resource_id=case_uuid,
        facility_id=case_row.get("facility_id"),
        ip_address=get_client_ip(request),
        details={"action": "triage_override", "overridden_triage": body.overridden_triage},
    )

    return {
        "status": "overridden",
        "case_id": case_uuid,
        "overridden_triage": body.overridden_triage,
        "overridden_by": user["sub"],
    }


# ── Case Outcome ─────────────────────────────────────────────────────────────────


@router.patch("/api/cases/{case_id}/outcome")
@limiter.limit("30/minute")
async def record_case_outcome(
    request: Request,
    case_id: str,
    body: CaseOutcomeInput,
    authorization: str = Header(None),
    user: dict = Depends(require_role("doctor", "admin")),
):
    """
    Records what actually happened to a patient after triage — the real-world
    outcome that closes the feedback loop for future retraining (FEATURES_ROADMAP
    §1.3). Immutable audit trail: each call inserts a new case_outcomes row;
    corrections are new rows, not edits, matching medical record conventions.
    Scoped the same way as review_case.
    """
    case_uuid = _parse_uuid(case_id, "case_id")
    raw_token = (authorization or "").split(" ", 1)[-1]
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

    result = db.table("case_outcomes").insert(
        {
            "case_id": case_uuid,
            "recorded_by": user["sub"],
            "actual_severity": body.actual_severity,
            "patient_disposition": body.patient_disposition,
            "outcome_notes": body.outcome_notes,
        }
    ).execute()

    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to record outcome")

    log_phi_access(
        event_type=AuditEventType.PHI_CREATE,
        user_id=user.get("sub", "unknown"),
        user_role=role,
        resource_type="case_outcomes",
        resource_id=case_uuid,
        facility_id=case_row.get("facility_id"),
        ip_address=get_client_ip(request),
        details={"actual_severity": body.actual_severity, "patient_disposition": body.patient_disposition},
    )

    return result.data[0]


# ── ASHA: My Submissions ───────────────────────────────────────────────────────


@router.get("/api/cases/mine")
@limiter.limit("60/minute")
async def get_my_cases(
    request: Request,
    authorization: str = Header(None),
    user: dict = Depends(require_role("asha_worker", "admin")),
    before: str | None = None,      # created_at ISO cursor
    before_id: str | None = None,   # id of the last seen case (unique tie-breaker)
    limit: int = 25,
):
    """
    Returns the calling user's own submitted cases with cursor pagination.
    Sorted by created_at DESC, then by id DESC as a unique tie-breaker.
    RLS enforces ownership at DB level; the explicit filter is for clarity.
    Returns a limited column set — full briefing JSONB is doctor-facing only.
    """
    raw_token = (authorization or "").split(" ", 1)[-1]
    db = get_supabase_for_user(raw_token)
    limit = max(1, min(limit, 100))

    normalized_before = _normalized_iso_ts(before, "before") if before else None
    parsed_before_id = _parse_uuid(before_id, "before_id") if before_id else None

    query = (
        db.table("case_records")
        .select(
            "id, patient_name, chief_complaint, triage_level, "
            "created_at, reviewed_at, patient_age, patient_sex"
        )
        .eq("submitted_by", user["sub"])
        .is_("deleted_at", "null")
        .order("created_at", desc=True)
        .order("id", desc=True)
        .limit(limit + 1)
    )

    if normalized_before and parsed_before_id:
        query = query.or_(
            f"created_at.lt.{normalized_before},"
            f"and(created_at.eq.{normalized_before},id.lt.{parsed_before_id})"
        )
    elif normalized_before:
        query = query.lt("created_at", normalized_before)

    result = query.execute()
    rows = result.data
    has_more = len(rows) > limit

    return {
        "cases": rows[:limit],
        "hasMore": has_more,
        "nextCursor": rows[limit - 1]["created_at"] if has_more and rows else None,
        "nextId": rows[limit - 1]["id"] if has_more and rows else None,
    }


# ── Get Case Detail ───────────────────────────────────────────────────────────────


@router.get("/api/cases/{case_id}")
@limiter.limit("60/minute")
async def get_case_detail(
    request: Request,
    case_id: str,
    authorization: str = Header(None),
    user: dict = Depends(require_role("asha_worker", "doctor", "admin")),
):
    """Returns the full record including briefing JSONB for one case after ownership/facility authorization checks."""
    case_uuid = _parse_uuid(case_id, "case_id")
    raw_token = (authorization or "").split(" ", 1)[-1]
    db = get_supabase_for_user(raw_token)

    result = (
        db.table("case_records")
        .select("*")
        .eq("id", case_uuid)
        .is_("deleted_at", "null")
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
