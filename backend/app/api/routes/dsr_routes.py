"""
Data-subject-request (DSR) lifecycle — DPDP Act 2023 data-principal rights
(docs/COMPLIANCE_DPDP.md). Admin-mediated because the patient is not a
VitalNet user: there's no login for a patient to request their own export,
so a facility admin acts on a verified in-person/offline request.

Scoped to a single `case_id`, not a cross-visit "patient" identifier —
VitalNet has no patient master index (`docs/DECISIONS.md` §6: `client_id`
is a per-submission idempotency key, not a stable person identifier across
visits). Locating every case for one real-world patient across multiple
visits is a manual admin-search step this module doesn't attempt to
automate.
"""
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app.core.auth import require_role
from app.core.audit import AuditEventType, get_client_ip, log_phi_access
from app.core.config import settings
from app.core.database import supabase_admin
from app.api.routes.cases import _parse_uuid, limiter

logger = logging.getLogger("vitalnet")

router = APIRouter(prefix="/api/admin/cases", tags=["dsr"])

REDACTED = "[REDACTED — see docs/COMPLIANCE_DPDP.md]"

# Direct-identifier / free-text fields on case_records that plausibly carry
# patient-identifying content. Vitals, symptom codes, triage outputs, and
# timestamps are left intact — they're the de-identified clinical signal
# the retraining/aggregate-reporting use case (docs/COMPLIANCE_DPDP.md)
# depends on, and none of them identify the patient on their own.
_ERASABLE_CASE_FIELDS = [
    "patient_name",
    "patient_location",
    "chief_complaint",
    "observations",
    "known_conditions",
    "current_medications",
]


def _fetch_case_or_404(case_id: str) -> dict:
    result = (
        supabase_admin.table("case_records")
        .select("*")
        .eq("id", case_id)
        .maybe_single()
        .execute()
    )
    row = result.data if result else None
    if not row:
        raise HTTPException(status_code=404, detail="Case not found")
    return row


@router.get("/{case_id}/export")
@limiter.limit("10/minute")
async def export_case_data(
    request: Request,
    case_id: str,
    authorization: str = Header(None),
    user: dict = Depends(require_role("admin")),
):
    """
    Right to access (docs/COMPLIANCE_DPDP.md): every row across every table
    tied to this case, as one JSON bundle. Deliberately not filtered on
    `deleted_at` — a data-subject request applies regardless of the
    internal soft-delete/hide-from-queries state.
    """
    case_uuid = _parse_uuid(case_id, "case_id")
    case = _fetch_case_or_404(case_uuid)

    outcomes = (
        supabase_admin.table("case_outcomes").select("*").eq("case_id", case_uuid).execute()
    )
    attachments = (
        supabase_admin.table("case_attachments").select("*").eq("case_id", case_uuid).execute()
    )
    referrals = (
        supabase_admin.table("referrals").select("*").eq("case_id", case_uuid).execute()
    )

    log_phi_access(
        event_type=AuditEventType.PHI_EXPORT,
        user_id=user.get("sub", "unknown"),
        user_role=user.get("resolved_role"),
        resource_type="case_records",
        resource_id=case_uuid,
        facility_id=case.get("facility_id"),
        ip_address=get_client_ip(request),
        details={"reason": "data_subject_request", "tables": ["case_records", "case_outcomes", "case_attachments", "referrals"]},
    )

    return {
        "case_id": case_uuid,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "case": case,
        "outcomes": outcomes.data or [],
        "attachments": attachments.data or [],
        "referrals": referrals.data or [],
    }


def _erase_case_row(case_uuid: str, case: dict) -> None:
    """
    Anonymises rather than hard-deletes: identifying free-text fields on
    `case_records` and the `referrals.reason` free-text field are replaced
    with a redaction marker, and the case is soft-deleted (`deleted_at`) if
    not already. Vitals/symptoms/triage output/timestamps survive so
    aggregate reporting and model retraining keep working on de-identified
    data.

    `case_outcomes` is deliberately left untouched: it's an immutable,
    insert-only table by design (medical-record convention — corrections
    are new rows, not edits) and carries no direct patient identifier, only
    clinical disposition/notes tied to a case_id. Redacting it would break
    that invariant for a table that isn't actually the PII surface.
    """
    update_body = {field: REDACTED for field in _ERASABLE_CASE_FIELDS}
    if case.get("deleted_at") is None:
        update_body["deleted_at"] = datetime.now(timezone.utc).isoformat()

    supabase_admin.table("case_records").update(update_body).eq("id", case_uuid).execute()
    supabase_admin.table("referrals").update({"reason": REDACTED}).eq("case_id", case_uuid).execute()


@router.post("/{case_id}/erase")
@limiter.limit("10/minute")
async def erase_case_data(
    request: Request,
    case_id: str,
    authorization: str = Header(None),
    user: dict = Depends(require_role("admin")),
):
    """Right to erasure (docs/COMPLIANCE_DPDP.md) for a single case."""
    case_uuid = _parse_uuid(case_id, "case_id")
    case = _fetch_case_or_404(case_uuid)

    _erase_case_row(case_uuid, case)

    log_phi_access(
        event_type=AuditEventType.PHI_ERASURE,
        user_id=user.get("sub", "unknown"),
        user_role=user.get("resolved_role"),
        resource_type="case_records",
        resource_id=case_uuid,
        facility_id=case.get("facility_id"),
        ip_address=get_client_ip(request),
        details={"reason": "data_subject_request", "redacted_fields": _ERASABLE_CASE_FIELDS},
    )

    return {"status": "erased", "case_id": case_uuid, "redacted_fields": _ERASABLE_CASE_FIELDS}


@router.post("/purge-expired")
@limiter.limit("6/minute")
async def purge_expired_cases(
    request: Request,
    authorization: str = Header(None),
    user: dict = Depends(require_role("admin")),
):
    """
    Retention-policy sweep (docs/COMPLIANCE_DPDP.md) — meant to be called on
    a schedule by an external scheduler, exactly like
    POST /api/push/check-emergency-escalations. Anonymises every
    not-yet-redacted case older than `settings.data_retention_days`.
    Disabled (no-op) when `data_retention_days` is 0, the default.
    """
    if settings.data_retention_days <= 0:
        return {"enabled": False, "purged": 0}

    threshold = (
        datetime.now(timezone.utc) - timedelta(days=settings.data_retention_days)
    ).isoformat()

    candidates = (
        supabase_admin.table("case_records")
        .select("id, facility_id")
        .lt("created_at", threshold)
        .neq("patient_name", REDACTED)
        .execute()
        .data
        or []
    )

    purged = []
    for row in candidates:
        _erase_case_row(row["id"], row)
        log_phi_access(
            event_type=AuditEventType.PHI_ERASURE,
            user_id=user.get("sub", "unknown"),
            user_role=user.get("resolved_role"),
            resource_type="case_records",
            resource_id=row["id"],
            facility_id=row.get("facility_id"),
            ip_address=get_client_ip(request),
            details={"reason": "retention_policy_purge", "redacted_fields": _ERASABLE_CASE_FIELDS},
        )
        purged.append(row["id"])

    if purged:
        logger.info("Retention purge anonymised %d case(s) older than %d days", len(purged), settings.data_retention_days)

    return {"enabled": True, "checked": len(candidates), "purged": len(purged)}
