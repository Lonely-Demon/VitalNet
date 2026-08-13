import logging
from typing import Optional, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel, EmailStr, Field

from app.core.auth import require_role
from app.core.audit import AuditEventType, get_client_ip, log_phi_access
from app.core.database import supabase_admin
from app.api.routes.cases import limiter

logger = logging.getLogger("vitalnet")

router = APIRouter(prefix='/api/admin', tags=['admin'])

def _validate_password(password: str) -> None:
    p = password or ""
    if not (12 <= len(p) <= 128):
        raise HTTPException(
            status_code=400,
            detail="Password must be 12-128 characters and include an uppercase letter, "
                   "a lowercase letter, a number, and a symbol",
        )
    has_lower = any(c.islower() for c in p)
    has_upper = any(c.isupper() for c in p)
    has_digit = any(c.isdigit() for c in p)
    has_symbol = any(not c.isalnum() for c in p)
    if not (has_lower and has_upper and has_digit and has_symbol):
        raise HTTPException(
            status_code=400,
            detail="Password must be 12-128 characters and include an uppercase letter, "
                   "a lowercase letter, a number, and a symbol",
        )


def _mask_csv_value(value: Optional[str]) -> Optional[str]:
    """
    Neutralise CSV/spreadsheet formula injection: if this admin data is ever
    exported and opened in Excel/Sheets, a value starting with =, +, -, @ or a
    control character can execute as a formula. Prefixing with a quote forces
    it to be read as literal text.
    """
    if value is None:
        return None
    text = str(value)
    if text and text[0] in {"=", "+", "-", "@", "\t", "\r", "\n"}:
        return "'" + text
    return text


def _get_caller_facility_id(user: dict) -> str:
    facility_id = user.get("resolved_facility_id")
    if not facility_id:
        raise HTTPException(status_code=400, detail="Account has no facility assigned.")
    return facility_id


# ── Pydantic models ───────────────────────────────────────────────────────────

class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=128)
    full_name: str = Field(min_length=1, max_length=100)
    role: Literal['asha_worker', 'doctor', 'admin', 'supervisor']
    facility_id: Optional[str] = None
    asha_id: Optional[str] = Field(None, max_length=50)


class BulkCreateUsersRequest(BaseModel):
    users: list[CreateUserRequest] = Field(min_length=1, max_length=100)


class UpdateUserRequest(BaseModel):
    role: Optional[Literal['asha_worker', 'doctor', 'admin', 'supervisor']] = None
    facility_id: Optional[str] = None
    full_name: Optional[str] = Field(None, min_length=1, max_length=100)
    asha_id: Optional[str] = Field(None, max_length=50)
    is_active: Optional[bool] = None


class CreateFacilityRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    type: str = Field(default='PHC', max_length=50)
    address: Optional[str] = Field(None, max_length=300)
    district: Optional[str] = Field(None, max_length=100)
    state: str = Field(default='Tamil Nadu', max_length=100)
    pincode: Optional[str] = Field(None, max_length=10)
    phone: Optional[str] = Field(None, max_length=20)


# ── User management ───────────────────────────────────────────────────────────

@router.get('/users')
@limiter.limit("60/minute")
async def list_users(
    request: Request,
    authorization: str = Header(None),
    user: dict = Depends(require_role('admin')),
    page: int = 1,
    limit: int = 100,
):
    """
    Returns local staff (Doctors and ASHA Workers) belonging to the caller's resolved facility_id.
    PHC Administrators cannot view users outside their PHC or view Admin/Supervisor accounts.
    """
    caller_fac_id = _get_caller_facility_id(user)

    limit = max(1, min(limit, 200))
    page = max(1, page)
    start = (page - 1) * limit
    end = start + limit - 1

    profiles_result = (
        supabase_admin.table('profiles')
        .select(
            'id, full_name, role, facility_id, asha_id, is_active, created_at, '
            'facilities(name, district)'
        )
        .eq('facility_id', caller_fac_id)
        .in_('role', ['asha_worker', 'doctor'])
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
            'role':          profile.get('role', 'asha_worker'),
            'facility_id':   profile.get('facility_id'),
            'facility_name': (profile.get('facilities') or {}).get('name'),
            'asha_id':       _mask_csv_value(profile.get('asha_id')),
            'is_active':     profile.get('is_active', True),
            'created_at':    str(au.created_at),
            'last_sign_in':  str(au.last_sign_in_at) if au.last_sign_in_at else None,
        })

    log_phi_access(
        event_type=AuditEventType.PHI_READ,
        user_id=user.get("sub", "unknown"),
        user_role=user.get("resolved_role"),
        resource_type="profiles",
        resource_id=f"facility:{caller_fac_id}:page:{page}",
        ip_address=get_client_ip(request),
        details={"count": len(result)},
    )

    return {"data": result, "page": page, "limit": limit}


def _provision_user(body: CreateUserRequest) -> dict:
    """
    Core create-user logic shared by create_user (single) and
    bulk_create_users. email_confirm=True so new users can log in
    immediately.
    """
    _validate_password(body.password)

    if body.role in {"asha_worker", "doctor", "supervisor", "admin"} and not body.facility_id:
        raise HTTPException(status_code=400, detail="facility_id is required for this role")

    response = supabase_admin.auth.admin.create_user({
        'email':         body.email,
        'password':      body.password,
        'email_confirm': True,
        'user_metadata': {
            'full_name':   body.full_name,
            'role':        body.role,
            'facility_id': body.facility_id or '',
        },
    })

    new_user_id = str(response.user.id)

    try:
        profile_res = (
            supabase_admin.table('profiles')
            .update({'facility_id': body.facility_id, 'asha_id': body.asha_id})
            .eq('id', new_user_id)
            .execute()
        )
        if not profile_res or not profile_res.data:
            raise RuntimeError("Profile update returned no data")
    except Exception as e:
        logger.error("Failed to provision profile for new user %s: %s", new_user_id, e)
        try:
            supabase_admin.auth.admin.delete_user(new_user_id)
        except Exception as rollback_err:
            logger.error("Failed to roll back orphaned auth user %s: %s", new_user_id, rollback_err)
        raise HTTPException(
            status_code=500,
            detail="Failed to initialize user profile. The created account was rolled back.",
        )

    return {'id': new_user_id, 'email': body.email}


@router.post('/users')
@limiter.limit("10/minute")
async def create_user(
    request: Request,
    body: CreateUserRequest,
    authorization: str = Header(None),
    user: dict = Depends(require_role('admin')),
):
    """
    PHC Administrator creates a local Doctor or ASHA Worker account for their own PHC.
    Cannot create Admin or Supervisor roles (403). Force-sets facility_id to caller's facility.
    """
    caller_fac_id = _get_caller_facility_id(user)

    if body.role not in {'asha_worker', 'doctor'}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PHC Administrators can only create Doctor and ASHA Worker accounts.",
        )

    if body.facility_id and body.facility_id != caller_fac_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PHC Administrators can only manage staff within their own facility.",
        )

    body.facility_id = caller_fac_id

    # Verify caller's facility exists and is active
    fac_res = (
        supabase_admin.table('facilities')
        .select('is_active')
        .eq('id', caller_fac_id)
        .maybe_single()
        .execute()
    )
    if not fac_res or not fac_res.data:
        raise HTTPException(status_code=404, detail="Caller facility not found.")
    if not fac_res.data.get('is_active', True):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot create staff for an inactive facility.",
        )

    result = _provision_user(body)

    log_phi_access(
        event_type=AuditEventType.PHI_CREATE,
        user_id=user.get("sub", "unknown"),
        user_role=user.get("resolved_role"),
        resource_type="profiles",
        resource_id=result['id'],
        facility_id=body.facility_id,
        ip_address=get_client_ip(request),
        details={"created_role": body.role},
    )

    return result


@router.post('/users/bulk')
@limiter.limit("3/minute")
async def bulk_create_users(
    request: Request,
    body: BulkCreateUsersRequest,
    authorization: str = Header(None),
    user: dict = Depends(require_role('admin')),
):
    """
    Bulk Doctor/ASHA onboarding for caller's facility.
    """
    caller_fac_id = _get_caller_facility_id(user)

    fac_res = (
        supabase_admin.table('facilities')
        .select('is_active')
        .eq('id', caller_fac_id)
        .maybe_single()
        .execute()
    )
    if not fac_res or not fac_res.data or not fac_res.data.get('is_active', True):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot bulk import staff for an inactive facility.",
        )

    results = []
    for i, row in enumerate(body.users):
        if row.role not in {'asha_worker', 'doctor'}:
            results.append({
                "row": i, "email": row.email, "status": "error",
                "detail": "PHC Administrators can only create Doctor and ASHA Worker accounts.",
            })
            continue

        if row.facility_id and row.facility_id != caller_fac_id:
            results.append({
                "row": i, "email": row.email, "status": "error",
                "detail": "Cannot create staff for another facility.",
            })
            continue

        row.facility_id = caller_fac_id

        try:
            created = _provision_user(row)
        except HTTPException as e:
            results.append({"row": i, "email": row.email, "status": "error", "detail": e.detail})
            continue
        except Exception as e:
            logger.error("Bulk user creation failed for row %d (%s): %s", i, row.email, e)
            results.append({"row": i, "email": row.email, "status": "error", "detail": "Unexpected error creating this user"})
            continue

        log_phi_access(
            event_type=AuditEventType.PHI_CREATE,
            user_id=user.get("sub", "unknown"),
            user_role=user.get("resolved_role"),
            resource_type="profiles",
            resource_id=created['id'],
            facility_id=row.facility_id,
            ip_address=get_client_ip(request),
            details={"created_role": row.role, "bulk": True},
        )
        results.append({"row": i, "email": row.email, "status": "created", "id": created['id']})

    succeeded = sum(1 for r in results if r["status"] == "created")
    return {"results": results, "succeeded": succeeded, "failed": len(results) - succeeded}


@router.patch('/users/{user_id}')
@limiter.limit("30/minute")
async def update_user(
    request: Request,
    user_id: str,
    body: UpdateUserRequest,
    authorization: str = Header(None),
    user: dict = Depends(require_role('admin')),
):
    """
    Updates local staff profile fields. Prohibits self-management, role changes, or cross-PHC reassignment.
    """
    caller_id = user.get("sub")
    if user_id == caller_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PHC Administrators cannot modify their own account through staff management endpoints.",
        )

    caller_fac_id = _get_caller_facility_id(user)

    target_profile_response = (
        supabase_admin.table("profiles")
        .select("id, role, facility_id, asha_id, is_active, full_name")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    target_profile = (target_profile_response.data if target_profile_response else None) or {}
    if not target_profile:
        raise HTTPException(status_code=404, detail="User not found")

    if target_profile.get("facility_id") != caller_fac_id or target_profile.get("role") not in {'asha_worker', 'doctor'}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PHC Administrators can only manage Doctor and ASHA Worker accounts in their own facility.",
        )

    if body.role is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PHC Administrators cannot modify user roles.",
        )

    if body.facility_id is not None and body.facility_id != caller_fac_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PHC Administrators cannot reassign staff to another facility.",
        )

    profile_update = {}
    meta_update = {}

    if body.full_name is not None:
        profile_update['full_name'] = body.full_name
        meta_update['full_name'] = body.full_name

    if body.asha_id is not None and target_profile.get("role") == "asha_worker":
        profile_update['asha_id'] = body.asha_id

    if body.is_active is not None:
        if body.is_active is True:
            # Check facility is active
            fac_res = (
                supabase_admin.table('facilities')
                .select('is_active')
                .eq('id', caller_fac_id)
                .maybe_single()
                .execute()
            )
            if fac_res and fac_res.data and not fac_res.data.get('is_active', True):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Cannot reactivate staff member whose facility is inactive.",
                )
        profile_update['is_active'] = body.is_active

    if profile_update:
        supabase_admin.table('profiles').update(profile_update).eq('id', user_id).execute()

    if meta_update:
        try:
            supabase_admin.auth.admin.update_user_by_id(user_id, {'user_metadata': meta_update})
        except Exception as e:
            logger.error("Auth metadata update failed for user_id=%s: %s", user_id, e)
            rollback_values = {k: target_profile.get(k) for k in profile_update if k in target_profile}
            if rollback_values:
                supabase_admin.table('profiles').update(rollback_values).eq('id', user_id).execute()
            raise HTTPException(status_code=500, detail="Failed to update user metadata. Profile update was rolled back.")

    log_phi_access(
        event_type=AuditEventType.PHI_UPDATE,
        user_id=user.get("sub", "unknown"),
        user_role=user.get("resolved_role"),
        resource_type="profiles",
        resource_id=user_id,
        facility_id=caller_fac_id,
        ip_address=get_client_ip(request),
        details={"fields_updated": sorted(profile_update.keys())},
    )

    return {'status': 'updated'}


@router.delete('/users/{user_id}')
@limiter.limit("30/minute")
async def deactivate_user(
    request: Request,
    user_id: str,
    authorization: str = Header(None),
    user: dict = Depends(require_role('admin')),
):
    """Soft-deactivates a local Doctor or ASHA Worker account."""
    caller_id = user.get("sub")
    if user_id == caller_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PHC Administrators cannot deactivate their own account.",
        )

    caller_fac_id = _get_caller_facility_id(user)

    target_res = (
        supabase_admin.table('profiles')
        .select('id, role, facility_id')
        .eq('id', user_id)
        .maybe_single()
        .execute()
    )
    target = (target_res.data if target_res else None) or {}
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if target.get('facility_id') != caller_fac_id or target.get('role') not in {'asha_worker', 'doctor'}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PHC Administrators can only manage Doctor and ASHA Worker accounts in their own facility.",
        )

    result = supabase_admin.table('profiles').update({'is_active': False}).eq('id', user_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="User not found")

    log_phi_access(
        event_type=AuditEventType.PHI_UPDATE,
        user_id=user.get("sub", "unknown"),
        user_role=user.get("resolved_role"),
        resource_type="profiles",
        resource_id=user_id,
        facility_id=caller_fac_id,
        ip_address=get_client_ip(request),
        details={"is_active": False},
    )
    return {'status': 'deactivated'}


@router.post('/users/{user_id}/reactivate')
@limiter.limit("30/minute")
async def reactivate_user(
    request: Request,
    user_id: str,
    authorization: str = Header(None),
    user: dict = Depends(require_role('admin')),
):
    """Reactivates a local Doctor or ASHA Worker account."""
    caller_id = user.get("sub")
    if user_id == caller_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PHC Administrators cannot reactivate their own account.",
        )

    caller_fac_id = _get_caller_facility_id(user)

    fac_res = (
        supabase_admin.table('facilities')
        .select('is_active')
        .eq('id', caller_fac_id)
        .maybe_single()
        .execute()
    )
    if fac_res and fac_res.data and not fac_res.data.get('is_active', True):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot reactivate staff member whose facility is inactive.",
        )

    target_res = (
        supabase_admin.table('profiles')
        .select('id, role, facility_id')
        .eq('id', user_id)
        .maybe_single()
        .execute()
    )
    target = (target_res.data if target_res else None) or {}
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if target.get('facility_id') != caller_fac_id or target.get('role') not in {'asha_worker', 'doctor'}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PHC Administrators can only manage Doctor and ASHA Worker accounts in their own facility.",
        )

    result = supabase_admin.table('profiles').update({'is_active': True}).eq('id', user_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="User not found")

    log_phi_access(
        event_type=AuditEventType.PHI_UPDATE,
        user_id=user.get("sub", "unknown"),
        user_role=user.get("resolved_role"),
        resource_type="profiles",
        resource_id=user_id,
        facility_id=caller_fac_id,
        ip_address=get_client_ip(request),
        details={"is_active": True},
    )
    return {'status': 'reactivated'}


# ── Facilities management (Local Read-Only Context) ───────────────────────────

@router.get('/facilities')
@limiter.limit("60/minute")
async def list_facilities(
    request: Request,
    authorization: str = Header(None),
    user: dict = Depends(require_role('admin')),
):
    """
    Returns only caller's own PHC record as read-only reference data.
    """
    caller_fac_id = _get_caller_facility_id(user)
    result = supabase_admin.table('facilities').select('*').eq('id', caller_fac_id).execute()
    return result.data or []


@router.post('/facilities')
@limiter.limit("10/minute")
async def create_facility(
    request: Request,
    body: CreateFacilityRequest,
    authorization: str = Header(None),
    user: dict = Depends(require_role('admin')),
):
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Facility creation and toggling are managed by Supervisor Governance.",
    )


@router.patch('/facilities/{facility_id}/toggle')
@limiter.limit("30/minute")
async def toggle_facility(
    request: Request,
    facility_id: str,
    authorization: str = Header(None),
    user: dict = Depends(require_role('admin')),
):
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Facility creation and toggling are managed by Supervisor Governance.",
    )


# ── System stats & Audit Log ──────────────────────────────────────────────────

@router.get('/stats')
@limiter.limit("60/minute")
async def get_stats(
    request: Request,
    authorization: str = Header(None),
    user: dict = Depends(require_role('admin')),
):
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="System statistics are restricted to Supervisor Governance.",
    )


@router.get('/audit-log')
@limiter.limit("60/minute")
async def get_audit_log(
    request: Request,
    authorization: str = Header(None),
    user: dict = Depends(require_role('admin')),
    before: Optional[str] = None,
    limit: int = 50,
):
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="System audit logs are restricted to Supervisor Governance.",
    )
