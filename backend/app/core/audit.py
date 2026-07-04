"""
PHI audit logging — every create/read/update/delete of patient case data is
logged with who, what, when, and from where, for compliance and forensics.

Logs go to a dedicated 'vitalnet.audit' logger (structured JSON, same pipeline
as app logs). The `phi_audit_log` Postgres table (see supabase/migrations) is
the durable destination for a future log-shipper — this module does not write
to it directly, to keep the request hot path free of an extra DB write.

Never log patient free-text or vitals here — only identifiers (user/resource
IDs, facility, role, IP) and coarse action metadata.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import Request

audit_logger = logging.getLogger("vitalnet.audit")


class AuditEventType:
    PHI_CREATE = "PHI_CREATE"
    PHI_READ = "PHI_READ"
    PHI_UPDATE = "PHI_UPDATE"
    PHI_DELETE = "PHI_DELETE"
    PHI_EXPORT = "PHI_EXPORT"
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
    audit_logger.info(
        "event=%s user=%s role=%s resource=%s:%s facility=%s ip=%s details=%s",
        event_type, user_id, user_role, resource_type, resource_id, facility_id, ip_address, details,
    )
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
