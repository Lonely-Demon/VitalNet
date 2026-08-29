"""
Supervisor Management Routes — Organisation-wide PHC and PHC Administrator Governance.

Grounded in the two-tier RBAC authority model:
Supervisors are organisation-wide governance users who create/list/toggle PHCs
and create/manage PHC Administrator accounts (`admin` role).

Target & Field Validation:
- PATCH /admins/{user_id} operates ONLY on targets where target.role == 'admin'.
- Accepts ONLY full_name, facility_id (must be an active PHC), and is_active.
- Never accepts or changes a role field.
- Hard deletion is unsupported (soft deactivation / is_active toggles only).

Lifecycle Invariants:
- Deactivating a PHC fails with 409 Conflict if any active users remain assigned.
- Creating/reactivating an Administrator requires assigned facility_id to be active (409 Conflict if inactive).
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field

from app.core.auth import require_role
from app.core.audit import AuditEventType, get_client_ip, log_phi_access
from app.core.database import supabase_admin
from app.api.routes.cases import limiter
from app.api.routes.admin_routes import (
    CreateFacilityRequest,
    _mask_csv_value,
    _provision_user,
    CreateUserRequest,
)

logger = logging.getLogger("vitalnet")

router = APIRouter(prefix="/api/supervisor/management", tags=["supervisor-management"])


# ── Pydantic Schemas ──────────────────────────────────────────────────────────

class CreateAdminRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    full_name: str = Field(min_length=1, max_length=100)
    facility_id: str = Field(min_length=1, description="Required active facility ID for PHC Administrator")


class UpdateAdminRequest(BaseModel):
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    facility_id: Optional[str] = Field(None, min_length=1)
    is_active: Optional[bool] = None


# ── PHC Facilities Management ──────────────────────────────────────────────────

@router.get('/facilities')
@limiter.limit("60/minute")
async def list_facilities(
    request: Request,
    authorization: str = Header(None),
    user: dict = Depends(require_role('supervisor')),
):
    """List all PHCs, including active status."""
    result = supabase_admin.table('facilities').select('*').order('name').execute()
    return result.data or []


@router.post('/facilities')
@limiter.limit("10/minute")
async def create_facility(
    request: Request,
    body: CreateFacilityRequest,
    authorization: str = Header(None),
    user: dict = Depends(require_role('supervisor')),
):
    """Supervisor creates a new PHC."""
    result = supabase_admin.table('facilities').insert(body.model_dump()).execute()
    if not result.data:
        raise HTTPException(status_code=500, detail="Failed to create facility.")

    created = result.data[0]
    log_phi_access(
        event_type=AuditEventType.PHI_CREATE,
        user_id=user.get("sub", "unknown"),
        user_role=user.get("resolved_role"),
        resource_type="facilities",
        resource_id=created['id'],
        ip_address=get_client_ip(request),
        details={"name": body.name},
    )
    return created


@router.patch('/facilities/{facility_id}/toggle')
@limiter.limit("30/minute")
async def toggle_facility(
    request: Request,
    facility_id: str,
    authorization: str = Header(None),
    user: dict = Depends(require_role('supervisor')),
):
    """
    Activate/deactivate a PHC.
    Lifecycle invariant: Rejects deactivation with 409 Conflict if any active users
    (Admin, Doctor, ASHA Worker, Supervisor) remain assigned to this PHC.
    """
    current = supabase_admin.table('facilities').select('is_active').eq('id', facility_id).maybe_single().execute()
    if not current or not current.data:
        raise HTTPException(status_code=404, detail="Facility not found")

    current_state = bool(current.data['is_active'])
    new_state = not current_state

    # If deactivating, check if active profiles exist for this facility
    if current_state and not new_state:
        active_users = (
            supabase_admin.table('profiles')
            .select('id, full_name, role')
            .eq('facility_id', facility_id)
            .eq('is_active', True)
            .execute()
        )
        if active_users and active_users.data and len(active_users.data) > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Cannot deactivate facility with {len(active_users.data)} active assigned user(s). Reassign or deactivate staff first.",
            )

    result = (
        supabase_admin.table('facilities')
        .update({'is_active': new_state})
        .eq('id', facility_id)
        .eq('is_active', current_state)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=409, detail="Facility was modified concurrently. Please retry.")

    log_phi_access(
        event_type=AuditEventType.PHI_UPDATE,
        user_id=user.get("sub", "unknown"),
        user_role=user.get("resolved_role"),
        resource_type="facilities",
        resource_id=facility_id,
        ip_address=get_client_ip(request),
        details={"is_active": new_state},
    )
    return {'is_active': new_state}


# ── PHC Administrator Management ──────────────────────────────────────────────

@router.get('/admins')
@limiter.limit("60/minute")
async def list_admins(
    request: Request,
    authorization: str = Header(None),
    user: dict = Depends(require_role('supervisor')),
    page: int = 1,
    limit: int = 100,
):
    """
    Lists PHC Administrators (`role == 'admin'`) with facility assignment and active state.
    """
    limit = max(1, min(limit, 200))
    page = max(1, page)
    start = (page - 1) * limit
    end = start + limit - 1

    profiles_result = (
        supabase_admin.table('profiles')
        .select('id, full_name, role, facility_id, asha_id, is_active, created_at, facilities(name, district)')
        .eq('role', 'admin')
        .range(start, end)
        .execute()
    )
    profile_rows = profiles_result.data or []
    profiles_by_id = {p['id']: p for p in profile_rows}

    auth_users = supabase_admin.auth.admin.list_users(page=page, per_page=limit)
    auth_users = [au for au in auth_users if str(au.id) in profiles_by_id]

    result = []
    for au in auth_users:
        profile = profiles_by_id.get(str(au.id), {})
        result.append({
            'id':            str(au.id),
            'email':         _mask_csv_value(au.email),
            'full_name':     profile.get('full_name', ''),
            'role':          'admin',
            'facility_id':   profile.get('facility_id'),
            'facility_name': (profile.get('facilities') or {}).get('name'),
            'is_active':     profile.get('is_active', True),
            'created_at':    str(au.created_at),
            'last_sign_in':  str(au.last_sign_in_at) if au.last_sign_in_at else None,
        })

    log_phi_access(
        event_type=AuditEventType.PHI_READ,
        user_id=user.get("sub", "unknown"),
        user_role=user.get("resolved_role"),
        resource_type="profiles",
        resource_id=f"admins:page:{page}",
        ip_address=get_client_ip(request),
        details={"count": len(result)},
    )
    return {"data": result, "page": page, "limit": limit}


@router.post('/admins')
@limiter.limit("10/minute")
async def create_admin(
    request: Request,
    body: CreateAdminRequest,
    authorization: str = Header(None),
    user: dict = Depends(require_role('supervisor')),
):
    """
    Supervisor creates a PHC Administrator account (`role='admin'`).
    Verifies that the target facility exists and is active.
    """
    facility_res = (
        supabase_admin.table('facilities')
        .select('id, is_active')
        .eq('id', body.facility_id)
        .maybe_single()
        .execute()
    )
    if not facility_res or not facility_res.data:
        raise HTTPException(status_code=404, detail="Assigned facility not found.")

    if not facility_res.data.get('is_active', True):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot assign administrator to an inactive facility.",
        )

    provision_payload = CreateUserRequest(
        email=body.email,
        password=body.password,
        full_name=body.full_name,
        role='admin',
        facility_id=body.facility_id,
        asha_id=None,
    )
    result = _provision_user(provision_payload)

    log_phi_access(
        event_type=AuditEventType.PHI_CREATE,
        user_id=user.get("sub", "unknown"),
        user_role=user.get("resolved_role"),
        resource_type="profiles",
        resource_id=result['id'],
        facility_id=body.facility_id,
        ip_address=get_client_ip(request),
        details={"created_role": "admin"},
    )
    return result


@router.patch('/admins/{user_id}')
@limiter.limit("30/minute")
async def update_admin(
    request: Request,
    user_id: str,
    body: UpdateAdminRequest,
    authorization: str = Header(None),
    user: dict = Depends(require_role('supervisor')),
):
    """
    Updates PHC Administrator lifecycle fields: full_name, facility_id, is_active.
    Must operate ONLY on accounts whose current role is 'admin'.
    Does not accept or modify role.
    Verifies new facility_id is active if provided.
    """
    target_res = (
        supabase_admin.table('profiles')
        .select('id, role, facility_id, is_active, full_name')
        .eq('id', user_id)
        .maybe_single()
        .execute()
    )
    target_profile = (target_res.data if target_res else None) or {}
    if not target_profile:
        raise HTTPException(status_code=404, detail="User not found.")

    if target_profile.get('role') != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Supervisor management endpoints operate only on PHC Administrator accounts.",
        )

    profile_update = {}
    meta_update = {}

    if body.full_name is not None:
        profile_update['full_name'] = body.full_name
        meta_update['full_name'] = body.full_name

    if body.facility_id is not None:
        fac_check = (
            supabase_admin.table('facilities')
            .select('id, is_active')
            .eq('id', body.facility_id)
            .maybe_single()
            .execute()
        )
        if not fac_check or not fac_check.data:
            raise HTTPException(status_code=404, detail="Assigned facility not found.")
        if not fac_check.data.get('is_active', True):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot assign administrator to an inactive facility.",
            )
        profile_update['facility_id'] = body.facility_id
        meta_update['facility_id'] = body.facility_id

    if body.is_active is not None:
        if body.is_active is True:
            # Check current assigned facility is active
            target_fac_id = body.facility_id or target_profile.get('facility_id')
            if target_fac_id:
                fac_check = (
                    supabase_admin.table('facilities')
                    .select('is_active')
                    .eq('id', target_fac_id)
                    .maybe_single()
                    .execute()
                )
                if fac_check and fac_check.data and not fac_check.data.get('is_active', True):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Cannot reactivate administrator whose assigned facility is inactive.",
                    )
        profile_update['is_active'] = body.is_active

    if profile_update:
        supabase_admin.table('profiles').update(profile_update).eq('id', user_id).execute()

    if meta_update:
        try:
            supabase_admin.auth.admin.update_user_by_id(user_id, {'user_metadata': meta_update})
        except Exception as e:
            logger.error("Auth metadata update failed for admin_id=%s: %s", user_id, e)
            rollback_values = {k: target_profile.get(k) for k in profile_update}
            supabase_admin.table('profiles').update(rollback_values).eq('id', user_id).execute()
            raise HTTPException(
                status_code=500,
                detail="Failed to update user metadata. Profile update was rolled back.",
            )

    log_phi_access(
        event_type=AuditEventType.PHI_UPDATE,
        user_id=user.get("sub", "unknown"),
        user_role=user.get("resolved_role"),
        resource_type="profiles",
        resource_id=user_id,
        facility_id=profile_update.get("facility_id") or target_profile.get("facility_id"),
        ip_address=get_client_ip(request),
        details={"fields_updated": sorted(profile_update.keys()), "target_role": "admin"},
    )
    return {'status': 'updated'}


@router.post('/admins/{user_id}/deactivate')
@router.delete('/admins/{user_id}')
@limiter.limit("30/minute")
async def deactivate_admin(
    request: Request,
    user_id: str,
    authorization: str = Header(None),
    user: dict = Depends(require_role('supervisor')),
):
    """Soft-deactivate a PHC Administrator account."""
    target_res = (
        supabase_admin.table('profiles')
        .select('id, role')
        .eq('id', user_id)
        .maybe_single()
        .execute()
    )
    target = (target_res.data if target_res else None) or {}
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")
    if target.get('role') != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Supervisor management endpoints operate only on PHC Administrator accounts.",
        )

    supabase_admin.table('profiles').update({'is_active': False}).eq('id', user_id).execute()
    log_phi_access(
        event_type=AuditEventType.PHI_UPDATE,
        user_id=user.get("sub", "unknown"),
        user_role=user.get("resolved_role"),
        resource_type="profiles",
        resource_id=user_id,
        ip_address=get_client_ip(request),
        details={"is_active": False, "target_role": "admin"},
    )
    return {'status': 'deactivated'}


@router.post('/admins/{user_id}/reactivate')
@limiter.limit("30/minute")
async def reactivate_admin(
    request: Request,
    user_id: str,
    authorization: str = Header(None),
    user: dict = Depends(require_role('supervisor')),
):
    """Reactivate a PHC Administrator account, verifying their assigned facility is active."""
    target_res = (
        supabase_admin.table('profiles')
        .select('id, role, facility_id')
        .eq('id', user_id)
        .maybe_single()
        .execute()
    )
    target = (target_res.data if target_res else None) or {}
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")
    if target.get('role') != 'admin':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Supervisor management endpoints operate only on PHC Administrator accounts.",
        )

    facility_id = target.get('facility_id')
    if facility_id:
        fac_check = (
            supabase_admin.table('facilities')
            .select('is_active')
            .eq('id', facility_id)
            .maybe_single()
            .execute()
        )
        if fac_check and fac_check.data and not fac_check.data.get('is_active', True):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cannot reactivate administrator whose assigned facility is inactive.",
            )

    supabase_admin.table('profiles').update({'is_active': True}).eq('id', user_id).execute()
    log_phi_access(
        event_type=AuditEventType.PHI_UPDATE,
        user_id=user.get("sub", "unknown"),
        user_role=user.get("resolved_role"),
        resource_type="profiles",
        resource_id=user_id,
        ip_address=get_client_ip(request),
        details={"is_active": True, "target_role": "admin"},
    )
    return {'status': 'reactivated'}
