"""
VitalNet Cases Router — all patient case endpoints.
Extracted from main.py as part of Phase 12 architectural modularisation.
"""
import logging
import uuid as uuid_lib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from slowapi import Limiter

from app.core.auth import require_role, verify_sub_for_rate_limit
from app.core.config import settings
from app.core.database import get_supabase_for_user
from app.models.schemas import IntakeForm
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

    # Step 1: Classifier + SHAP (always runs — LLM-independent)
    try:
        triage_result = run_triage(form_data)
        briefing = await generate_briefing(form_data, triage_result)
        raw_token = (authorization or "").split(" ", 1)[-1]
        db = get_supabase_for_user(raw_token)

        record = {
            "client_id": str(form.client_id or uuid_lib.uuid4()),
            "submitted_by": user["sub"],
            "facility_id": user.get("user_metadata", {}).get("facility_id") or None,
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
            "triage_level": triage_result["triage_level"],
            "triage_confidence": triage_result["confidence_score"],
            "risk_driver": triage_result["risk_driver"],
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
            existing = db.table("case_records").select("*").eq("client_id", record["client_id"]).execute()
            return existing.data[0] if existing.data else record
        return result.data[0]
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
    before_time: str = None,       # ISO timestamp of the last seen case
    before_priority: int = None,   # triage_priority of the last seen case (0/1/2)
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

    Scoping: 'admin' sees all facilities (global). 'doctor' accounts with a
    facility_id are scoped to that facility only — this matches the
    real-time subscription filter in useRealtimeCases (frontend), which was
    already facility-scoped, and the analytics scoping model in
    analytics_routes.py. Doctors without a facility_id assigned see all
    cases (unscoped), same as before this endpoint had scoping.
    """
    raw_token = (authorization or "").split(" ", 1)[-1]
    db = get_supabase_for_user(raw_token)

    role = user.get("user_metadata", {}).get("role") or user.get("app_metadata", {}).get("role")
    facility_id = user.get("user_metadata", {}).get("facility_id")

    # Safety cap
    limit = max(1, min(limit, 100))

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

    if role != "admin" and facility_id:
        query = query.eq("facility_id", facility_id)

    if before_time is not None and before_priority is not None:
        # Composite keyset cursor — correct two-column keyset pagination.
        query = query.or_(
            f"triage_priority.gt.{before_priority},"
            f"and(triage_priority.eq.{before_priority},created_at.lt.{before_time})"
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
    raw_token = (authorization or "").split(" ", 1)[-1]
    db = get_supabase_for_user(raw_token)

    role = user.get("user_metadata", {}).get("role") or user.get("app_metadata", {}).get("role")
    facility_id = user.get("user_metadata", {}).get("facility_id")

    query = db.table("case_records").update(
        {
            "reviewed_by": user["sub"],
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        }
    ).eq("id", case_id)

    if role != "admin" and facility_id:
        query = query.eq("facility_id", facility_id)

    result = query.execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Case not found")
    return {"status": "reviewed"}


# ── ASHA: My Submissions ───────────────────────────────────────────────────────


@router.get("/api/cases/mine")
@limiter.limit("60/minute")
async def get_my_cases(
    request: Request,
    authorization: str = Header(None),
    user: dict = Depends(require_role("asha_worker", "admin")),
    before: str = None,   # created_at ISO cursor
    limit: int = 25,
):
    """
    Returns the calling user's own submitted cases with cursor pagination.
    Sorted by created_at DESC only (chronological — no priority sort for personal history).
    RLS enforces ownership at DB level; the explicit filter is for clarity.
    Returns a limited column set — full briefing JSONB is doctor-facing only.
    """
    raw_token = (authorization or "").split(" ", 1)[-1]
    db = get_supabase_for_user(raw_token)
    limit = max(1, min(limit, 100))

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

    if before:
        query = query.lt("created_at", before)

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
@limiter.limit("60/minute")
async def get_case_detail(
    request: Request,
    case_id: str,
    authorization: str = Header(None),
    user: dict = Depends(require_role("doctor", "admin")),
):
    """
    Returns the full record including briefing JSONB for one case.
    Scoped the same way as GET /api/cases — see review_case() docstring.
    """
    raw_token = (authorization or "").split(" ", 1)[-1]
    db = get_supabase_for_user(raw_token)

    role = user.get("user_metadata", {}).get("role") or user.get("app_metadata", {}).get("role")
    facility_id = user.get("user_metadata", {}).get("facility_id")

    query = (
        db.table("case_records")
        .select("*")
        .eq("id", case_id)
        .is_("deleted_at", "null")
    )
    if role != "admin" and facility_id:
        query = query.eq("facility_id", facility_id)

    result = query.execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Case not found")
    return result.data[0]
