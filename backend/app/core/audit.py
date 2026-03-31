"""
VitalNet PHI Audit Logging Module

Security Fix: ROOT-COMPLY-002 - Audit logging for PHI access

All PHI access events are logged with:
- Timestamp (UTC)
- User ID (from JWT)
- Action type (create, read, update, delete)
- Resource type (case_records, profiles, etc.)
- Resource ID
- Facility ID (for scope verification)
- IP address (for forensics)
- Additional context (e.g., fields accessed)

In production, these logs should be shipped to a SIEM or immutable audit storage.
"""
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from fastapi import Request
from functools import wraps

# Configure dedicated audit logger
audit_logger = logging.getLogger("vitalnet.audit")
audit_logger.setLevel(logging.INFO)

# Ensure audit logs are formatted consistently
if not audit_logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s | AUDIT | %(message)s',
        datefmt='%Y-%m-%dT%H:%M:%S%z'
    )
    handler.setFormatter(formatter)
    audit_logger.addHandler(handler)


class AuditEventType:
    """Audit event type constants for PHI access logging."""
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
    details: Optional[Dict[str, Any]] = None,
):
    """
    Log a PHI access event for compliance auditing.
    
    ROOT-COMPLY-002: All PHI access must be logged with sufficient detail
    for forensic investigation and compliance reporting.
    """
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
    
    # Format as structured log line
    audit_logger.info(
        f"event={event_type} user={user_id} role={user_role} "
        f"resource={resource_type}:{resource_id} facility={facility_id} "
        f"ip={ip_address} details={details}"
    )
    
    return log_entry


def get_client_ip(request: Request) -> str:
    """
    Extract client IP from request, handling proxy headers.
    """
    # Check X-Forwarded-For for proxied requests
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    
    # Check X-Real-IP
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip
    
    # Fallback to direct client
    if request.client:
        return request.client.host
    
    return "unknown"


def audit_phi_endpoint(resource_type: str, event_type: str = AuditEventType.PHI_READ):
    """
    Decorator to automatically audit PHI access on endpoints.
    
    Usage:
        @router.get("/api/cases/{case_id}")
        @audit_phi_endpoint("case_records", AuditEventType.PHI_READ)
        async def get_case(case_id: str, user: dict = Depends(require_role("doctor"))):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Extract request and user from kwargs
            request = kwargs.get("request")
            user = kwargs.get("user", {})
            
            # Get resource ID from path params
            resource_id = None
            for key in ["case_id", "user_id", "facility_id", "id"]:
                if key in kwargs:
                    resource_id = kwargs[key]
                    break
            
            # Log the PHI access
            log_phi_access(
                event_type=event_type,
                user_id=user.get("sub", "unknown"),
                user_role=user.get("user_metadata", {}).get("role", "unknown"),
                resource_type=resource_type,
                resource_id=resource_id,
                facility_id=user.get("user_metadata", {}).get("facility_id"),
                ip_address=get_client_ip(request) if request else "unknown",
                details={"endpoint": func.__name__},
            )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator


# Convenience functions for common audit events
def audit_case_create(user: dict, case_id: str, facility_id: str, request: Request = None):
    """Log case creation (PHI write)."""
    log_phi_access(
        event_type=AuditEventType.PHI_CREATE,
        user_id=user.get("sub", "unknown"),
        user_role=user.get("user_metadata", {}).get("role"),
        resource_type="case_records",
        resource_id=case_id,
        facility_id=facility_id,
        ip_address=get_client_ip(request) if request else None,
    )


def audit_case_read(user: dict, case_id: str, request: Request = None):
    """Log case read (PHI access)."""
    log_phi_access(
        event_type=AuditEventType.PHI_READ,
        user_id=user.get("sub", "unknown"),
        user_role=user.get("user_metadata", {}).get("role"),
        resource_type="case_records",
        resource_id=case_id,
        facility_id=user.get("user_metadata", {}).get("facility_id"),
        ip_address=get_client_ip(request) if request else None,
    )


def audit_case_update(user: dict, case_id: str, fields_updated: list, request: Request = None):
    """Log case update (PHI modification)."""
    log_phi_access(
        event_type=AuditEventType.PHI_UPDATE,
        user_id=user.get("sub", "unknown"),
        user_role=user.get("user_metadata", {}).get("role"),
        resource_type="case_records",
        resource_id=case_id,
        facility_id=user.get("user_metadata", {}).get("facility_id"),
        ip_address=get_client_ip(request) if request else None,
        details={"fields_updated": fields_updated},
    )


def audit_bulk_access(user: dict, resource_type: str, count: int, request: Request = None):
    """Log bulk PHI access (e.g., listing cases)."""
    log_phi_access(
        event_type=AuditEventType.PHI_READ,
        user_id=user.get("sub", "unknown"),
        user_role=user.get("user_metadata", {}).get("role"),
        resource_type=resource_type,
        resource_id=f"bulk:{count}",
        facility_id=user.get("user_metadata", {}).get("facility_id"),
        ip_address=get_client_ip(request) if request else None,
        details={"bulk_access": True, "record_count": count},
    )
