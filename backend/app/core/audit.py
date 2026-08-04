"""
PHI audit logging — every create/read/update/delete of patient case data is
logged with who, what, when, and from where, for compliance and forensics
(FEATURES_ROADMAP §2.4).

Every call writes to two places: a dedicated 'vitalnet.audit' logger
(structured, same pipeline as app logs — always available even if the DB
write below fails) and the `phi_audit_log` Postgres table (see
supabase/migrations), which is what GET /api/admin/audit-log reads for the
admin-facing audit UI. The DB write is best-effort — a failure there is
itself logged but never raises, so a transient DB blip can't break the
request the audit call is attached to.

Never log patient free-text or vitals here — only identifiers (user/resource
IDs, facility, role, IP) and coarse action metadata.
"""
import logging
import uuid as uuid_lib
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import Request

audit_logger = logging.getLogger("vitalnet.audit")
logger = logging.getLogger("vitalnet")


def _as_uuid_or_none(value: Optional[str]) -> Optional[str]:
    """phi_audit_log.user_id/facility_id are uuid columns — some call sites
    pass placeholder strings like "unknown" when a real id isn't available
    (e.g. an auth failure before a user id was resolved). Insert NULL rather
    than let a non-UUID string fail the whole insert."""
    if not value:
        return None
    try:
        return str(uuid_lib.UUID(str(value)))
    except (ValueError, AttributeError):
        return None


class AuditEventType:
    PHI_CREATE = "PHI_CREATE"
    PHI_READ = "PHI_READ"
    PHI_UPDATE = "PHI_UPDATE"
    PHI_DELETE = "PHI_DELETE"
    PHI_EXPORT = "PHI_EXPORT"
    PHI_ERASURE = "PHI_ERASURE"
    AUTH_LOGIN = "AUTH_LOGIN"
    AUTH_LOGOUT = "AUTH_LOGOUT"
    AUTH_FAILED = "AUTH_FAILED"
    CONSENT_CAPTURED = "CONSENT_CAPTURED"


def log_phi_access(
    event_type: str,
    user_id: str,
    resource_type: str,
    resource_id: Optional[str] = None,
    facility_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_role: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
) -> dict:
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        "user_id": user_id,
        "user_role": user_role,
        "resource_type": resource_type,
        "resource_id": resource_id,
        "facility_id": facility_id,
        "ip_address": ip_address,
        "details": details or {},
    }
    # Intentional: this IS the PHI access audit trail (ROOT-COMPLY-002).
    # Recording who/what/when/where in plain, greppable text is the entire
    # point of an audit log; only coarse identifiers are logged here (never
    # patient free-text/vitals — see the module docstring), which is the
    # accepted shape for compliance logging. Suppression uses the current
    # CodeQL inline syntax (codeql[query-id], not the legacy lgtm.com
    # lgtm[query-id] syntax, which GitHub's default CodeQL setup does not honor).
    audit_logger.info(
        "event=%s user=%s role=%s resource=%s:%s facility=%s ip=%s details=%s",
        event_type, user_id, user_role, resource_type, resource_id, facility_id, ip_address, details,  # codeql[py/clear-text-logging-sensitive-data]
    )

    try:
        from app.core.database import supabase_admin
        supabase_admin.table("phi_audit_log").insert({
            "event_type": event_type,
            "user_id": _as_uuid_or_none(user_id),
            "user_role": user_role,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "facility_id": _as_uuid_or_none(facility_id),
            "ip_address": ip_address,
            "details": details or {},
        }).execute()
    except Exception as e:
        # Never let an audit-log write failure break the request it's attached
        # to — the structured logger line above already recorded the event.
        logger.warning("Failed to persist audit log entry to phi_audit_log: %s", e)

    return log_entry


def get_client_ip(request: Request) -> str:
    """Extract the client IP, preferring proxy headers (Railway/most PaaS sit behind a proxy)."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip
    if request.client:
        return request.client.host
    return "unknown"
