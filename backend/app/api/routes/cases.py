"""
VitalNet Cases Router — all patient case endpoints.
Extracted from main.py as part of Phase 12 architectural modularisation.
"""
import asyncio
import logging
import re
import uuid as uuid_lib
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from slowapi import Limiter

from app.core.auth import require_role, verify_sub_for_rate_limit, _verify_token, _resolve_profile
from app.core.audit import AuditEventType, get_client_ip, log_phi_access
from app.core.config import settings
from app.core.database import get_supabase_for_user, extract_bearer_token
from app.core.metrics import record_triage_classification
from app.models.schemas import IntakeForm, TriageOverride, CaseOutcomeInput, PATIENT_KEY_RE
from app.ml.classifier import predict_triage
from app.services.llm import generate_briefing, generate_patient_summary
from app.services.push import push_emergency_alert
from app.utils.case_queue import build_cases_cursor_filter
from app.utils.paediatric import build_paediatric_advisory

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


UUID_REGEX = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.IGNORECASE)
SYSTEM_SUBMITTER_UUID = "00000000-0000-0000-0000-000000000000"
SYSTEM_FACILITY_UUID = "00000000-0000-0000-0000-000000000001"


def _triage_priority_from_tier(tier: str | None) -> int:
    """
    Aligns with PostgreSQL check constraint case_records_triage_priority_map_check:
    EMERGENCY = 0, URGENT = 1, ROUTINE = 2.
    """
    if tier == "EMERGENCY":
        return 0
    elif tier == "URGENT":
        return 1
    return 2


def _normalized_iso_ts(value: str, field: str) -> str:
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid {field}")


def _resolved_role(user: dict) -> str:
    return user.get("resolved_role") or ""


def _resolved_facility(user: dict) -> str | None:
    return user.get("resolved_facility_id")


# Cross-visit deterioration pattern: a repeated URGENT/EMERGENCY presentation
# from the same patient within this trailing window is a signal worth a
# clinician's eyes even if today's reading alone wouldn't trigger review.
_DETERIORATION_WINDOW_DAYS = 7


def _check_deterioration_pattern(db, patient_key: str | None, current_triage_level: str) -> tuple[bool, int | None]:
    """
    Counts prior URGENT/EMERGENCY visits sharing patient_key within the
    trailing window via fn_deterioration_count (a SECURITY DEFINER Postgres
    function, backend/supabase/migrations/phase28_security_definer_fns.sql),
    called through `db` — the CALLING USER's own RLS-scoped client, not
    supabase_admin. A patient_key carries no PII (docs/DECISIONS.md §20,
    §22, §29), and an ASHA worker submitting THIS case is already trusted
    to reason about whether this same patient has recently had repeated
    severe visits, regardless of which worker saw them each time (plain
    RLS would otherwise silently restrict an asha_worker's own query to
    only their own past submissions, undercounting cross-worker visits) —
    fn_deterioration_count re-derives that same narrow exception inside
    the database, next to the table it protects, instead of in Python.
    """
    if not patient_key:
        return False, None

    result = db.rpc(
        "fn_deterioration_count",
        {
            "p_patient_key": patient_key,
            "p_current_triage_level": current_triage_level,
            "p_window_days": _DETERIORATION_WINDOW_DAYS,
        },
    ).execute()
    row = (result.data or [{}])[0]
    return bool(row.get("has_pattern")), row.get("visit_count")


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


def _fetch_authorized_case(db, case_uuid: str, user: dict) -> dict:
    """
    Fetch a non-deleted case row by id (404 if missing/deleted), then apply
    _authorize_case_row_access (403 if not authorized). Shared by every
    endpoint that acts on a single existing case (review, triage-override,
    outcome, soft-delete).
    """
    result = (
        db.table("case_records")
        .select("id, facility_id, submitted_by, deleted_at")
        .eq("id", case_uuid)
        .maybe_single()
        .execute()
    )
    row = (result.data if result else None) or {}
    if not row or row.get("deleted_at") is not None:
        raise HTTPException(status_code=404, detail="Case not found")

    _authorize_case_row_access(user, row)
    return row


# ── Submit Case ────────────────────────────────────────────────────────────────


@router.post("/api/submit")
@limiter.limit("20/minute")   # 20 per authenticated user per minute
async def submit_case(
    request: Request,       # required first positional param for slowapi
    form: IntakeForm,
    background_tasks: BackgroundTasks,
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
        triage_result = await asyncio.to_thread(predict_triage, form_data)
        raw_token = extract_bearer_token(authorization)
        db = get_supabase_for_user(raw_token)

        deterioration_alert, deterioration_visit_count = await asyncio.to_thread(
            _check_deterioration_pattern, db, form.patient_key, triage_result["triage_level"]
        )
        triage_result["deterioration_alert"] = deterioration_alert
        triage_result["deterioration_visit_count"] = deterioration_visit_count

        # Trajectory query via fn_patient_recent_trajectory RPC (BUG-54) with query fallback
        prior_visits = []
        if form.patient_key:
            try:
                traj_res = db.rpc(
                    "fn_patient_recent_trajectory",
                    {"p_patient_key": form.patient_key, "p_limit": 3},
                ).execute()
                prior_visits = traj_res.data or []
            except Exception as e:
                logger.warning("fn_patient_recent_trajectory RPC failed, falling back to query: %s", e)
                try:
                    pv_res = (
                        db.table("case_records")
                        .select(
                            "created_at, triage_level, bp_systolic, bp_diastolic, "
                            "spo2, heart_rate, temperature, chief_complaint"
                        )
                        .eq("patient_key", form.patient_key)
                        .is_("deleted_at", "null")
                        .order("created_at", desc=True)
                        .limit(3)
                        .execute()
                    )
                    prior_visits = pv_res.data or []
                except Exception as e2:
                    logger.warning("Could not pre-fetch longitudinal trajectory: %s", e2)
        triage_result["prior_visits"] = prior_visits

        briefing = await generate_briefing(form_data, triage_result)

        paediatric_advisory = build_paediatric_advisory(
            {"patient_age": form.patient_age, "age_months": form.age_months, "muac_mm": form.muac_mm},
            enabled=settings.paediatric_advisory_enabled,
        )
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
            # Governance-gated paediatric capture. These fields are persisted
            # for review/research only and are intentionally absent from the
            # classifier and briefing inputs above.
            "age_months": form.age_months,
            "muac_mm": form.muac_mm,
            "paediatric_advisory": paediatric_advisory,
            "is_pregnant": form.is_pregnant,
            "chief_complaint": form_data.get("chief_complaint", form.chief_complaint),
            "complaint_duration": form.complaint_duration,
            "symptoms": form.symptoms or [],
            "observations": form_data.get("observations", form.observations),
            "known_conditions": form_data.get("known_conditions", form.known_conditions),
            "current_medications": form_data.get("current_medications", form.current_medications),
            "human_review_requested": form.human_review_requested,
            "human_review_reason": form.human_review_reason,
            "patient_key": form.patient_key,
            "consent_captured": form.consent_captured,
            "consent_captured_at": form.consent_captured_at.isoformat()
            if form.consent_captured_at
            else datetime.now(timezone.utc).isoformat(),
            "triage_level": triage_result["triage_level"],
            "triage_priority": _triage_priority_from_tier(triage_result["triage_level"]),
            "triage_confidence": triage_result["confidence_score"],
            "risk_driver": triage_result["risk_driver"],
            "triage_model_version": triage_result.get("model_version"),
            "low_confidence": bool(triage_result.get("low_confidence")),
            "contraindication_flags": triage_result.get("contraindication_flags") or [],
            "deterioration_alert": deterioration_alert,
            "deterioration_visit_count": deterioration_visit_count,
            "llm_status": briefing.get("llm_status", "generated"),
            "needs_review": bool(
                briefing.get("needs_review")
                or form.human_review_requested
                or triage_result.get("contraindication_flags")
                or deterioration_alert
            ),
            "briefing": briefing,
            "llm_model_used": briefing.get("_model_used", "unknown"),
            "created_offline": form.created_offline,
            "client_submitted_at": form.client_submitted_at.isoformat()
            if form.client_submitted_at
            else None,
            "is_sms_stub": False,
        }

        # ADR §51: Idempotent Cross-Transport State-Promoting Database Upsert.
        # If an earlier emergency SMS alert created an offline stub (is_sms_stub = true),
        # promote the record with the complete HTTPS submission instead of dropping it.
        client_uuid_str = record["client_id"]
        is_new_or_promoted = False
        existing_res = (
            db.table("case_records")
            .select(
                "id, is_sms_stub, submitted_by, facility_id, created_at, "
                "reviewed_at, overridden_triage, triage_level, triage_priority, needs_review"
            )
            .eq("client_id", client_uuid_str)
            .maybe_single()
            .execute()
        )
        existing_row = (existing_res.data if existing_res else None) or {}
        if isinstance(existing_row, list):
            existing_row = existing_row[0] if existing_row else {}

        if existing_row and existing_row.get("is_sms_stub"):
            # Verify submitter authorization before promoting stub (BUG-52)
            if existing_row.get("submitted_by") and existing_row.get("submitted_by") != user["sub"]:
                raise HTTPException(status_code=403, detail="Not authorized to promote this SMS stub")

            # Preserve clinician review if already conducted on the emergency stub (BUG-52)
            if existing_row.get("reviewed_at") is not None or existing_row.get("overridden_triage") is not None:
                record["triage_level"] = existing_row.get("triage_level", record["triage_level"])
                record["triage_priority"] = existing_row.get("triage_priority") if existing_row.get("triage_priority") is not None else record["triage_priority"]
                record["needs_review"] = existing_row.get("needs_review", False)

            # Exclude immutables from update payload
            update_payload = {
                k: v for k, v in record.items()
                if k not in {"id", "client_id", "submitted_by", "facility_id"}
            }
            update_payload["is_sms_stub"] = False
            update_payload["updated_at"] = datetime.now(timezone.utc).isoformat()

            update_res = (
                db.table("case_records")
                .update(update_payload)
                .eq("client_id", client_uuid_str)
                .execute()
            )
            response = update_res.data[0] if (update_res and update_res.data) else record
            is_new_or_promoted = True
        elif existing_row:
            existing_fetch = (
                db.table("case_records")
                .select(
                    "id, client_id, triage_level, triage_confidence, risk_driver, "
                    "created_at, created_offline, facility_id, is_sms_stub"
                )
                .eq("client_id", client_uuid_str)
                .execute()
            )
            response = existing_fetch.data[0] if (existing_fetch and existing_fetch.data) else record
            is_new_or_promoted = False
        else:
            result = (
                db.table("case_records")
                .upsert(record, on_conflict="client_id", ignore_duplicates=True)
                .execute()
            )
            if not result.data:
                existing_fetch = (
                    db.table("case_records")
                    .select(
                        "id, client_id, triage_level, triage_confidence, risk_driver, "
                        "created_at, created_offline, facility_id, is_sms_stub"
                    )
                    .eq("client_id", client_uuid_str)
                    .execute()
                )
                response = existing_fetch.data[0] if (existing_fetch and existing_fetch.data) else record
                is_new_or_promoted = False
            else:
                response = result.data[0]
                is_new_or_promoted = True

        log_phi_access(
            event_type=AuditEventType.PHI_CREATE,
            user_id=user.get("sub", "unknown"),
            user_role=role,
            resource_type="case_records",
            resource_id=response.get("id") if isinstance(response, dict) else None,
            facility_id=facility_id,
            ip_address=get_client_ip(request),
            details={
                "created_offline": bool(form.created_offline),
                "needs_review": bool(record.get("needs_review")),
                "paediatric_capture": bool(form.age_months is not None or form.muac_mm is not None),
                "paediatric_advisory_status": paediatric_advisory.get("status"),
            },
        )

        # Genuinely new submission (not a retried duplicate) — record the
        # business metric once, not on every retry (docs/SLO.md).
        if is_new_or_promoted:
            record_triage_classification(triage_result["triage_level"])

        # Genuinely new EMERGENCY case (not a retried duplicate) — notify the
        # facility's subscribed doctors. Background task: never adds latency
        # to the ASHA worker's submission response, and push_emergency_alert()
        # itself no-ops safely if VAPID isn't configured.
        if is_new_or_promoted and triage_result["triage_level"] == "EMERGENCY":
            background_tasks.add_task(
                push_emergency_alert,
                facility_id,
                "EMERGENCY case submitted",
                f"{form_data.get('chief_complaint', form.chief_complaint)} — {triage_result['risk_driver']}"[:150],
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
    before_needs_review: bool | None = None,  # needs_review of the last seen case
    before_id: str | None = None,         # id of the last seen case (unique tie-breaker)
    limit: int = 25,
):
    """
    Cursor-based pagination with composite keyset for the Doctor Dashboard.

    Sort order: EMERGENCY (0) → URGENT (1) → ROUTINE (2) first,
    flagged cases requiring review before unflagged cases within each tier,
    then by created_at DESC, then by id DESC as a unique tie-breaker.

    Use before_time + before_priority + before_needs_review + before_id from
    the previous page's cursor fields to fetch the next page.

    Scoping: 'admin' sees all facilities (global). 'doctor' accounts with a
    facility_id are scoped to that facility only. Doctors without a
    facility_id assigned see all cases (unscoped), same as before this
    endpoint had scoping.
    """
    raw_token = extract_bearer_token(authorization)
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
            "contraindication_flags, deterioration_alert, deterioration_visit_count, "
            "triage_model_version, overridden_triage, override_reason, overridden_by, overridden_at, "
            "patient_key, created_at, reviewed_at, reviewed_by, facility_id, created_offline"
        )
        .is_("deleted_at", "null")
        .order("triage_priority", desc=False)   # EMERGENCY (0) first
        .order("needs_review", desc=True)        # Flagged cases first within tier
        .order("created_at", desc=True)          # Newest within each routing group
        .order("id", desc=True)                  # Unique tie-breaker for stable pagination
        .limit(limit + 1)                        # Fetch one extra to determine hasMore
    )

    if role == "doctor" and facility_id:
        query = query.eq("facility_id", facility_id)

    if normalized_before_time is not None and before_priority is not None:
        query = query.or_(
            build_cases_cursor_filter(
                before_time=normalized_before_time,
                before_priority=before_priority,
                before_needs_review=before_needs_review,
                before_id=parsed_before_id,
            )
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
        "nextNeedsReview": cases[-1]["needs_review"] if has_more and cases else None,
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
    raw_token = extract_bearer_token(authorization)
    db = get_supabase_for_user(raw_token)
    role = _resolved_role(user)

    case_row = _fetch_authorized_case(db, case_uuid, user)

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
    raw_token = extract_bearer_token(authorization)
    db = get_supabase_for_user(raw_token)
    role = _resolved_role(user)

    case_row = _fetch_authorized_case(db, case_uuid, user)

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
    raw_token = extract_bearer_token(authorization)
    db = get_supabase_for_user(raw_token)
    role = _resolved_role(user)

    case_row = _fetch_authorized_case(db, case_uuid, user)

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
    raw_token = extract_bearer_token(authorization)
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


# ── Get Case History By Patient Key ───────────────────────────────────────────


@router.get("/api/cases/by-patient-key/{patient_key}")
@limiter.limit("60/minute")
async def get_cases_by_patient_key(
    request: Request,
    patient_key: str,
    authorization: str = Header(None),
    user: dict = Depends(require_role("asha_worker", "doctor", "admin")),
):
    """
    Returns a summary of prior visits sharing the given patient continuity
    key, newest first. Purely a lookup for recognizing a returning patient —
    RLS enforces the same visibility boundary as every other case view here:
    'admin' sees all matches, 'doctor' with a facility_id is scoped to their
    facility (via RLS + the explicit filter below, matching GET /api/cases),
    and 'asha_worker' sees only visits they personally submitted (RLS
    enforces ownership, same as GET /api/cases/mine). The key itself carries
    no PII — it is only ever useful joined against case_records.
    """
    key = (patient_key or "").strip().upper()
    if not PATIENT_KEY_RE.match(key):
        raise HTTPException(status_code=400, detail="Invalid patient_key format")

    raw_token = extract_bearer_token(authorization)
    db = get_supabase_for_user(raw_token)
    role = _resolved_role(user)
    facility_id = _resolved_facility(user)

    query = (
        db.table("case_records")
        .select(
            "id, chief_complaint, triage_level, created_at, reviewed_at, "
            "patient_age, patient_sex, facility_id, bp_systolic, bp_diastolic, "
            "spo2, heart_rate, temperature"
        )
        .eq("patient_key", key)
        .is_("deleted_at", "null")
        .order("created_at", desc=True)
        .limit(50)
    )

    if role == "doctor" and facility_id:
        query = query.eq("facility_id", facility_id)

    result = query.execute()
    rows = result.data or []

    log_phi_access(
        event_type=AuditEventType.PHI_READ,
        user_id=user.get("sub", "unknown"),
        user_role=role,
        resource_type="case_records",
        resource_id=None,
        facility_id=facility_id,
        ip_address=get_client_ip(request),
        details={"view": "patient_key_history", "match_count": len(rows), "include": "bounded_vitals"},
    )

    return {"cases": rows}


# ── Due Case Follow-ups (REG-06) ───────────────────────────────────────────────


@router.get("/api/cases/followups/due")
@limiter.limit("60/minute")
async def get_due_followups(
    request: Request,
    authorization: str = Header(None),
    user: dict = Depends(require_role("asha_worker", "doctor", "admin", "supervisor", "super_admin")),
    due_before: str | None = None,
    facility_id: str | None = None,
    limit: int = 50,
):
    """
    R5 (REG-06): Parity endpoint for due follow-up cases.
    Queries cases where follow_up_required is True, deleted_at is null,
    and follow_up_completed_at is null.
    Facility-scoped for doctor and admin; submitter-scoped for asha_worker.
    """
    raw_token = extract_bearer_token(authorization)
    db = get_supabase_for_user(raw_token)
    role = _resolved_role(user)
    user_facility = _resolved_facility(user)

    bounded_limit = max(1, min(limit, 100))

    query = (
        db.table("case_records")
        .select(
            "id, client_id, patient_name, patient_age, patient_sex, patient_location, chief_complaint, "
            "triage_level, follow_up_required, follow_up_due_at, facility_id, submitted_by, created_at"
        )
        .eq("follow_up_required", True)
        .is_("deleted_at", "null")
        .is_("follow_up_completed_at", "null")
        .order("follow_up_due_at", desc=False)
        .limit(bounded_limit)
    )

    if due_before:
        query = query.lte("follow_up_due_at", _normalized_iso_ts(due_before, "due_before"))

    if role == "asha_worker":
        query = query.eq("submitted_by", user.get("sub"))
    elif role in ("doctor", "admin"):
        # Scoped strictly to doctor/admin's assigned facility
        scope_facility = user_facility or facility_id
        if scope_facility:
            query = query.eq("facility_id", scope_facility)
    else:
        # super_admin or supervisor: can optionally filter by facility_id query param
        if facility_id:
            query = query.eq("facility_id", facility_id)

    try:
        res = query.execute()
        rows = res.data or []
    except Exception as e:
        logger.warning("followups/due query failed: %s", e)
        raise HTTPException(status_code=502, detail="Follow-up cases query failed — try again")

    log_phi_access(
        event_type=AuditEventType.PHI_READ,
        user_id=user.get("sub", "unknown"),
        user_role=role,
        resource_type="case_records",
        resource_id=None,
        facility_id=user_facility,
        ip_address=get_client_ip(request),
        details={"view": "followups_due", "count": len(rows)},
    )

    return {"cases": rows, "count": len(rows)}


# ── Complete Case Follow-up (REG-06) ───────────────────────────────────────────


@router.post("/api/cases/{case_id}/followup-complete")
@limiter.limit("30/minute")
async def complete_case_followup(
    request: Request,
    case_id: str,
    authorization: str = Header(None),
    user: dict = Depends(require_role("asha_worker", "doctor", "admin", "super_admin")),
):
    """
    R5 (REG-06): Mark a case follow-up as completed.
    Guards case_id with UUID regex, facility-scopes doctor and admin,
    and updates follow_up_completed_at and follow_up_required = False.
    """
    if not UUID_REGEX.match(case_id):
        raise HTTPException(status_code=400, detail="Invalid case ID format; UUID required")

    raw_token = extract_bearer_token(authorization)
    db = get_supabase_for_user(raw_token)
    role = _resolved_role(user)
    user_facility = _resolved_facility(user)

    res = (
        db.table("case_records")
        .select("id, facility_id, submitted_by, deleted_at")
        .eq("id", case_id)
        .maybe_single()
        .execute()
    )
    case_row = (res.data if res else None) or {}
    if not case_row or case_row.get("deleted_at") is not None:
        raise HTTPException(status_code=404, detail="Case not found or already deleted")

    if role == "asha_worker":
        if case_row.get("submitted_by") != user.get("sub"):
            raise HTTPException(status_code=403, detail="Not authorized for this case")
    elif role in ("doctor", "admin"):
        if not user_facility or user_facility != case_row.get("facility_id"):
            raise HTTPException(status_code=403, detail="Not authorized to access cases outside your facility")
    elif role == "super_admin":
        pass
    else:
        raise HTTPException(status_code=403, detail="Not authorized for this case")

    completed_at = datetime.now(timezone.utc).isoformat()
    update_res = (
        db.table("case_records")
        .update({
            "follow_up_completed_at": completed_at,
            "follow_up_required": False,
        })
        .eq("id", case_id)
        .is_("deleted_at", "null")
        .execute()
    )
    if not update_res or not update_res.data:
        raise HTTPException(status_code=404, detail="Case not found or already deleted")

    log_phi_access(
        event_type=AuditEventType.PHI_UPDATE,
        user_id=user.get("sub", "unknown"),
        user_role=role,
        resource_type="case_records",
        resource_id=case_id,
        facility_id=case_row.get("facility_id"),
        ip_address=get_client_ip(request),
        details={"action": "followup_complete", "follow_up_completed_at": completed_at},
    )

    return {
        "status": "followup_completed",
        "case_id": case_id,
        "follow_up_completed_at": completed_at,
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
    raw_token = extract_bearer_token(authorization)
    db = get_supabase_for_user(raw_token)

    result = (
        db.table("case_records")
        .select(
            "id, created_at, updated_at, patient_name, patient_age, patient_sex, patient_location, patient_key, "
            "chief_complaint, complaint_duration, symptoms, observations, known_conditions, current_medications, "
            "temperature, heart_rate, bp_systolic, bp_diastolic, spo2, respiratory_rate, "
            "triage_level, triage_priority, triage_confidence, triage_model_version, model_version, risk_driver, "
            "briefing, reviewed_at, reviewed_by, doctor_notes, overridden_triage, override_reason, overridden_by, overridden_at, "
            "facility_id, submitted_by, is_pregnant, contraindication_flags, needs_review, "
            "human_review_requested, human_review_reason, deterioration_alert, deterioration_visit_count, low_confidence, "
            "consent_captured, consent_captured_at, client_id, created_offline, synced_at"
        )
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


@router.post("/api/cases/{case_id}/patient-summary")
@limiter.limit("20/minute")
async def case_patient_summary(
    request: Request,
    case_id: str,
    language: str = "en",
    authorization: str = Header(None),
    user: dict = Depends(require_role("asha_worker", "doctor", "admin")),
):
    """
    On-demand, patient-facing plain-language restatement of an already-
    complete case's briefing — for the ASHA worker to read aloud in the
    patient's own language. Never regenerates or re-derives the triage
    itself; purely a restatement (app/services/llm.py::generate_patient_summary).
    Not persisted — computed fresh on each call, since it's a UX nicety
    layered on the case, not part of the clinical record.
    """
    case_uuid = _parse_uuid(case_id, "case_id")
    raw_token = extract_bearer_token(authorization)
    db = get_supabase_for_user(raw_token)

    result = (
        db.table("case_records")
        .select("id, facility_id, submitted_by, triage_level, risk_driver, briefing, deleted_at")
        .eq("id", case_uuid)
        .maybe_single()
        .execute()
    )
    row = (result.data if result else None) or {}
    if not row or row.get("deleted_at") is not None:
        raise HTTPException(status_code=404, detail="Case not found")

    _authorize_case_row_access(user, row)

    triage_result = {"triage_level": row["triage_level"], "risk_driver": row.get("risk_driver") or ""}
    briefing = row.get("briefing") or {}
    summary = await generate_patient_summary(briefing, triage_result, language=language)

    return summary


# ── Offline Consent Revocation Tombstone (ADR §55) ─────────────────────────────


@router.post("/api/security/cases/{client_id}/revoke-consent")
@limiter.limit("30/minute")
async def revoke_case_consent(
    request: Request,
    client_id: str,
    authorization: str = Header(None),
    user: dict = Depends(require_role("admin", "doctor", "asha_worker", "super_admin")),
):
    """
    ADR §55: Offline consent revocation tombstone drain.
    Finds the case by client_id (or id) and idempotently erases identifying
    narratives and associated attachments/events.
    Returns 200 on success, or 404/409 which cleanly dequeue from client outbox.
    """
    if not UUID_REGEX.match(client_id):
        raise HTTPException(status_code=400, detail="Invalid case ID format; UUID required")

    raw_token = extract_bearer_token(authorization)
    db = get_supabase_for_user(raw_token)
    role = _resolved_role(user)
    facility_id = _resolved_facility(user)

    res = (
        db.table("case_records")
        .select("*")
        .eq("client_id", client_id)
        .maybe_single()
        .execute()
    )
    case_row = (res.data if res else None) or {}
    if not case_row:
        res = (
            db.table("case_records")
            .select("*")
            .eq("id", client_id)
            .maybe_single()
            .execute()
        )
        case_row = (res.data if res else None) or {}

    if not case_row:
        raise HTTPException(status_code=404, detail="Case not found for revocation")
    # De Morgan's Law fix (BUG-09):
    # asha_worker may only revoke their own submitted case within their facility
    if role == "asha_worker":
        if case_row.get("submitted_by") != user.get("sub"):
            raise HTTPException(status_code=403, detail="Not authorized to revoke consent for this case")
        if facility_id and case_row.get("facility_id") and case_row.get("facility_id") != facility_id:
            raise HTTPException(status_code=403, detail="Not authorized to access cases outside your facility")
    elif role in ("doctor", "admin"):
        if not facility_id or facility_id != case_row.get("facility_id"):
            raise HTTPException(status_code=403, detail="Not authorized to access cases outside your facility")
    elif role == "super_admin":
        pass
    else:
        raise HTTPException(status_code=403, detail="Not authorized for this case")

    # If already erased, return idempotently
    REDACTED_TEXT = "[REDACTED — DSR ERASURE]"
    if case_row.get("deleted_at") is not None and case_row.get("patient_name") == REDACTED_TEXT:
        return {"status": "already_revoked", "client_id": client_id, "case_id": case_row["id"]}

    # Call atomic stored procedure fn_erase_case_pii directly (BUG-10)
    try:
        rpc_res = db.rpc("fn_erase_case_pii", {"p_case_id": case_row["id"]}).execute()
        if rpc_res and getattr(rpc_res, "data", None) and isinstance(rpc_res.data, dict):
            if rpc_res.data.get("status") == "already_revoked":
                return {"status": "already_revoked", "client_id": client_id, "case_id": case_row["id"]}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("fn_erase_case_pii RPC call in revoke_case_consent failed: %s", e)
        raise HTTPException(status_code=500, detail=f"DSR erasure failed: {str(e)}")

    log_phi_access(
        event_type=AuditEventType.PHI_ERASURE,
        user_id=user.get("sub", "unknown"),
        user_role=role,
        resource_type="case_records",
        resource_id=case_row["id"],
        facility_id=case_row.get("facility_id"),
        ip_address=get_client_ip(request),
        details={"reason": "offline_consent_revocation_tombstone", "client_id": client_id},
    )

    return {"status": "consent_revoked", "client_id": client_id, "case_id": case_row["id"]}


# ── Inbound SMS Gateway Ingest (BUG-23) ───────────────────────────────────────


@router.post("/api/cases/sms-gateway")
@limiter.limit("60/minute")
async def ingest_sms_gateway(
    request: Request,
    authorization: str = Header(None),
):
    """
    Inbound SMS gateway endpoint (BUG-23). Accepts inbound emergency SMS payloads,
    resolves or creates an offline stub in case_records (is_sms_stub = True),
    and queues case for clinician review.
    """
    from app.services.sms import decode_emergency_sms, parse_inbound_sms, SmsParseError, validate_e164_phone_number

    content_type = request.headers.get("content-type", "")
    body_text = ""
    sender = None
    facility_id = None
    if "application/json" in content_type:
        try:
            data = await request.json()
            body_text = data.get("body") or data.get("message") or data.get("text") or ""
            sender = data.get("sender") or data.get("from")
            facility_id = data.get("facility_id")
        except Exception:
            body_text = ""
    else:
        raw_body = await request.body()
        body_text = raw_body.decode("utf-8", errors="ignore").strip()

    if not body_text:
        raise HTTPException(status_code=400, detail="Empty SMS body")

    if sender and not validate_e164_phone_number(sender):
        logger.warning("SMS gateway received message from non-E.164 sender: %s", sender)

    raw_token = extract_bearer_token(authorization)
    user = None
    if raw_token:
        try:
            user = _verify_token(raw_token)
            if user and user.get("sub"):
                _, _, u_fac = _resolve_profile(user["sub"], raw_token)
                if u_fac:
                    user["resolved_facility_id"] = u_fac
        except Exception:
            user = None

    db = get_supabase_for_user(raw_token) if raw_token else None

    decoded = None
    if "VN1:" in body_text:
        try:
            decoded = decode_emergency_sms(body_text)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid VN1 frame: {e}")
    else:
        try:
            parsed = parse_inbound_sms(body_text)
            decoded = {
                "client_id": str(uuid_lib.uuid4()),
                "patient_age": parsed.patient_age,
                "patient_sex": parsed.patient_sex,
                "symptoms": parsed.symptoms,
                "triage_level": "ROUTINE",
                "tier": "ROUTINE",
            }
        except SmsParseError as spe:
            raise HTTPException(status_code=400, detail=spe.reason)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid SMS: {e}")

    client_id = decoded.get("client_id") or str(uuid_lib.uuid4())
    patient_key = f"sms_{client_id}"
    triage_level = decoded.get("triage_level") or decoded.get("tier") or "ROUTINE"
    triage_priority = _triage_priority_from_tier(triage_level)
    submitted_by = (user.get("sub") if user else None) or SYSTEM_SUBMITTER_UUID
    resolved_facility_id = (
        facility_id
        or decoded.get("facility_id")
        or (user.get("resolved_facility_id") if user else None)
        or SYSTEM_FACILITY_UUID
    )

    stub_record = {
        "client_id": client_id,
        "is_sms_stub": True,
        "submitted_by": submitted_by,
        "facility_id": resolved_facility_id,
        "patient_name": "Emergency Patient (SMS)",
        "patient_location": "Community (SMS Intake)",
        "complaint_duration": "acute (<24h)",
        "patient_key": patient_key,
        "patient_age": decoded.get("patient_age"),
        "patient_sex": decoded.get("patient_sex"),
        "symptoms": decoded.get("symptoms") or [],
        "bp_systolic": decoded.get("bp_systolic"),
        "bp_diastolic": decoded.get("bp_diastolic"),
        "spo2": decoded.get("spo2"),
        "heart_rate": decoded.get("heart_rate"),
        "temperature": decoded.get("temperature"),
        "is_pregnant": decoded.get("is_pregnant", False),
        "triage_level": triage_level,
        "triage_priority": triage_priority,
        "triage_confidence": 0.85,
        "risk_driver": "SMS Gateway Emergency Stub Intake",
        "needs_review": True,
        "chief_complaint": "[SMS Emergency Alert Stub — Pending Full Sync]",
        "consent_captured": True,
        "consent_captured_at": datetime.now(timezone.utc).isoformat(),
        "created_offline": True,
        "briefing": {
            "triage_level": triage_level,
            "primary_risk_driver": "Emergency SMS Alert Stub",
            "recommended_immediate_actions": ["[Rule-Mandated] Await complete HTTPS transmission; monitor patient."],
            "llm_status": "sms_stub",
        },
    }

    if db:
        try:
            db.table("case_records").upsert(stub_record, on_conflict="client_id", ignore_duplicates=True).execute()
        except Exception as e:
            logger.warning("Could not persist SMS stub to database: %s", e)

    return {
        "status": "queued",
        "client_id": client_id,
        "patient_key": patient_key,
        "triage_level": stub_record["triage_level"],
        "is_sms_stub": True,
    }

