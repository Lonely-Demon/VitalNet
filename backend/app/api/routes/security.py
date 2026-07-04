"""
Case soft-delete. Kept as its own router (rather than folded into cases.py)
since it's the one write path scoped to `require_role` across all three
roles plus a mandatory device-binding header, distinct from cases.py's
per-role endpoints.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app.core.auth import require_role
from app.core.audit import AuditEventType, get_client_ip, log_phi_access
from app.core.database import get_supabase_for_user
from app.api.routes.cases import _authorize_case_row_access, _parse_uuid, _resolved_role, limiter

router = APIRouter(prefix="/api/security", tags=["security"])


@router.delete("/cases/{case_id}")
@limiter.limit("30/minute")
async def soft_delete_case(
    request: Request,
    case_id: str,
    authorization: str = Header(None),
    x_device_id: str | None = Header(default=None, alias="X-Device-Id"),
    user: dict = Depends(require_role("admin", "doctor", "asha_worker")),
):
    if not x_device_id:
        raise HTTPException(status_code=400, detail="Missing device binding header")

    case_uuid = _parse_uuid(case_id, "case_id")
    raw_token = (authorization or "").split(" ", 1)[-1]
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

    _authorize_case_row_access(user, row)

    update_result = (
        db.table("case_records")
        .update({"deleted_at": datetime.now(timezone.utc).isoformat()})
        .eq("id", case_uuid)
        .is_("deleted_at", "null")
        .execute()
    )
    if not update_result.data:
        raise HTTPException(status_code=409, detail="Case could not be deleted or already deleted")

    log_phi_access(
        event_type=AuditEventType.PHI_DELETE,
        user_id=user.get("sub", "unknown"),
        user_role=_resolved_role(user),
        resource_type="case_records",
        resource_id=case_uuid,
        facility_id=row.get("facility_id"),
        ip_address=get_client_ip(request),
        details={"device_id": x_device_id},
    )

    return {"status": "deleted", "case_id": case_uuid}
