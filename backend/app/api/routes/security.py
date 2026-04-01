from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException

from app.core.auth import require_role
from app.core.audit import AuditEventType, log_phi_access
from app.core.database import get_supabase_for_user

router = APIRouter(prefix="/api/security", tags=["security"])


def _extract_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    parts = authorization.strip().split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1].strip():
        raise HTTPException(status_code=401, detail="Malformed Authorization header")
    return parts[1].strip()


def _header_or_401(value: str | None) -> str:
    if value is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    return value


def _parse_uuid(value: str, field: str) -> str:
    try:
        return str(UUID(value))
    except Exception:
        raise HTTPException(status_code=400, detail=f"Invalid {field}")


@router.delete("/cases/{case_id}")
async def soft_delete_case(
    case_id: str,
    authorization: str = Header(None),
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
    user: dict = Depends(require_role("admin", "super_admin", "facility_admin", "doctor", "asha_worker")),
):
    if not x_device_id:
        raise HTTPException(status_code=400, detail="Missing device binding header")

    case_uuid = _parse_uuid(case_id, "case_id")
    raw_token = _extract_token(_header_or_401(authorization))
    db = get_supabase_for_user(raw_token)

    case = (
        db.table("case_records")
        .select("id, submitted_by, facility_id, deleted_at")
        .eq("id", case_uuid)
        .maybe_single()
        .execute()
    )
    row = (case.data if case else None) or {}
    if not row or row.get("deleted_at") is not None:
        raise HTTPException(status_code=404, detail="Case not found")

    role = user.get("resolved_role")
    user_id = user.get("sub")
    user_facility = user.get("resolved_facility_id")

    allowed = False
    if role in {"admin", "super_admin"}:
        allowed = True
    elif role in {"doctor", "facility_admin"} and user_facility and user_facility == row.get("facility_id"):
        allowed = True
    elif role == "asha_worker" and row.get("submitted_by") == user_id:
        allowed = True

    if not allowed:
        raise HTTPException(status_code=403, detail="Not authorized for this case")

    db.table("case_records").update(
        {
            "deleted_at": datetime.now(timezone.utc).isoformat(),
        }
    ).eq("id", case_uuid).is_("deleted_at", "null").execute()

    log_phi_access(
        event_type=AuditEventType.PHI_DELETE,
        user_id=user.get("sub", "unknown"),
        user_role=role,
        resource_type="case_records",
        resource_id=case_uuid,
        facility_id=row.get("facility_id"),
        ip_address=None,
        details={"device_id": x_device_id},
    )

    return {"status": "deleted"}
