import logging
import re
from typing import Optional, Literal

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field

from app.core.auth import require_role
from app.core.audit import AuditEventType, get_client_ip, log_phi_access
from app.core.database import supabase_admin
from app.api.routes.cases import limiter

logger = logging.getLogger("vitalnet")

router = APIRouter(prefix='/api/admin', tags=['admin'])

# Uppercase + lowercase + digit + symbol, 12-128 chars.
PASSWORD_POLICY_RE = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z\d]).{12,128}$")


def _validate_password(password: str) -> None:
    if not PASSWORD_POLICY_RE.match(password or ""):
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
    Returns all users joined with their profiles, paginated so a large
    deployment can't force one unbounded query across the whole user table.
    Uses admin client for auth.admin.list_users(), then enriches
    with profiles data for role/facility info.
    """
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
        resource_id=f"page:{page}",
        ip_address=get_client_ip(request),
        details={"count": len(result)},
    )

    return {"data": result, "page": page, "limit": limit}


def _provision_user(body: CreateUserRequest) -> dict:
    """
    Core create-user logic shared by create_user (single) and
    bulk_create_users (§1b.4). email_confirm=True so new users can log in
    immediately without going through the email verification flow.
    Raises HTTPException exactly as the single-user endpoint always has —
    bulk creation catches it per-row so one bad row can't fail the batch.
    """
    _validate_password(body.password)

    if body.role in {"asha_worker", "doctor", "supervisor"} and not body.facility_id:
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

    # Patch the profile row created by the DB trigger with extra fields. If
    # this fails, roll back the auth user rather than leave an orphaned
    # account with no usable profile (which would silently fail every
    # subsequent request via auth.py's "Profile not provisioned" check).
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
    Bulk ASHA/doctor onboarding via CSV import (FEATURES_ROADMAP §1b.4).
    Reuses _provision_user per row so each row gets the same password-policy
    enforcement and profile-provisioning rollback as the single-user
    endpoint; one bad row (duplicate email, weak password, etc.) is reported
    per-row rather than failing the whole batch. Passwords are never echoed
    back in the report.
    """
    results = []
    for i, row in enumerate(body.users):
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
    Updates profile fields (role, facility, asha_id, is_active).
    Also updates user_metadata in auth so the JWT hook re-embeds
    the new role on next login.
    """
    target_profile_response = (
        supabase_admin.table("profiles")
        .select("id, role, facility_id, asha_id, is_active")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    target_profile = (target_profile_response.data if target_profile_response else None) or {}
    if not target_profile:
        raise HTTPException(status_code=404, detail="User not found")

    profile_update = {}
    meta_update = {}

    if body.role is not None:
        profile_update['role'] = body.role
        meta_update['role'] = body.role
    if body.facility_id is not None:
        profile_update['facility_id'] = body.facility_id
        meta_update['facility_id'] = body.facility_id
    if body.asha_id is not None:
        profile_update['asha_id'] = body.asha_id
    if body.is_active is not None:
        profile_update['is_active'] = body.is_active

    if profile_update:
        supabase_admin.table('profiles').update(profile_update).eq('id', user_id).execute()

    if meta_update:
        try:
            supabase_admin.auth.admin.update_user_by_id(user_id, {'user_metadata': meta_update})
        except Exception as e:
            logger.error("Auth metadata update failed for user_id=%s: %s", user_id, e)
            if profile_update:
                # Keep the profile row and the JWT's cached metadata in sync —
                # revert the profile fields we just changed rather than leave
                # them ahead of what the token's claims (and next-login refresh) will show.
                rollback_values = {k: target_profile.get(k) for k in profile_update}
                supabase_admin.table('profiles').update(rollback_values).eq('id', user_id).execute()
            raise HTTPException(status_code=500, detail="Failed to update user metadata. Profile update was rolled back.")

    log_phi_access(
        event_type=AuditEventType.PHI_UPDATE,
        user_id=user.get("sub", "unknown"),
        user_role=user.get("resolved_role"),
        resource_type="profiles",
        resource_id=user_id,
        facility_id=profile_update.get("facility_id") or target_profile.get("facility_id"),
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
    """
    Soft-deactivates: sets profiles.is_active = false.
    Does NOT delete the auth user or their case records.
    Hard deletion is intentionally not exposed via API.
    """
    result = supabase_admin.table('profiles').update({'is_active': False}).eq('id', user_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="User not found")

    log_phi_access(
        event_type=AuditEventType.PHI_UPDATE,
        user_id=user.get("sub", "unknown"),
        user_role=user.get("resolved_role"),
        resource_type="profiles",
        resource_id=user_id,
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
    result = supabase_admin.table('profiles').update({'is_active': True}).eq('id', user_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="User not found")

    log_phi_access(
        event_type=AuditEventType.PHI_UPDATE,
        user_id=user.get("sub", "unknown"),
        user_role=user.get("resolved_role"),
        resource_type="profiles",
        resource_id=user_id,
        ip_address=get_client_ip(request),
        details={"is_active": True},
    )
    return {'status': 'reactivated'}


# ── Facilities management ─────────────────────────────────────────────────────

@router.get('/facilities')
@limiter.limit("60/minute")
async def list_facilities(
    request: Request,
    authorization: str = Header(None),
    user: dict = Depends(require_role('admin')),
):
    result = supabase_admin.table('facilities').select('*').order('name').execute()
    return result.data


@router.post('/facilities')
@limiter.limit("10/minute")
async def create_facility(
    request: Request,
    body: CreateFacilityRequest,
    authorization: str = Header(None),
    user: dict = Depends(require_role('admin')),
):
    result = supabase_admin.table('facilities').insert(body.model_dump()).execute()

    log_phi_access(
        event_type=AuditEventType.PHI_CREATE,
        user_id=user.get("sub", "unknown"),
        user_role=user.get("resolved_role"),
        resource_type="facilities",
        resource_id=result.data[0]['id'] if result.data else None,
        ip_address=get_client_ip(request),
        details={"name": body.name},
    )
    return result.data[0]


@router.patch('/facilities/{facility_id}/toggle')
@limiter.limit("30/minute")
async def toggle_facility(
    request: Request,
    facility_id: str,
    authorization: str = Header(None),
    user: dict = Depends(require_role('admin')),
):
    current = supabase_admin.table('facilities').select('is_active').eq('id', facility_id).maybe_single().execute()
    if not current or not current.data:
        raise HTTPException(status_code=404, detail="Facility not found")

    current_state = current.data['is_active']
    new_state = not current_state

    # Optimistic concurrency: only flip if the state hasn't changed since we
    # read it, so two concurrent toggles can't race into an inconsistent result.
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


# ── System stats ──────────────────────────────────────────────────────────────

@router.get('/stats')
@limiter.limit("60/minute")
async def get_stats(
    request: Request,
    authorization: str = Header(None),
    user: dict = Depends(require_role('admin')),
):
    cases = supabase_admin.table('case_records').select('triage_level').is_('deleted_at', 'null').execute()
    profiles = supabase_admin.table('profiles').select('role, is_active').execute()

    triage_counts = {'EMERGENCY': 0, 'URGENT': 0, 'ROUTINE': 0}
    for c in cases.data:
        level = c.get('triage_level', 'ROUTINE')
        triage_counts[level] = triage_counts.get(level, 0) + 1

    role_counts = {}
    active_count = 0
    for p in profiles.data:
        role_counts[p['role']] = role_counts.get(p['role'], 0) + 1
        if p['is_active']:
            active_count += 1

    return {
        'total_cases':   len(cases.data),
        'triage_counts': triage_counts,
        'total_users':   len(profiles.data),
        'active_users':  active_count,
        'role_counts':   role_counts,
    }


# ── Audit Log ──────────────────────────────────────────────────────────────────

@router.get('/audit-log')
@limiter.limit("60/minute")
async def get_audit_log(
    request: Request,
    authorization: str = Header(None),
    user: dict = Depends(require_role('admin')),
    before: Optional[str] = None,  # created_at ISO cursor
    limit: int = 50,
):
    """
    Paginated, chronological view of phi_audit_log (FEATURES_ROADMAP §2.4) —
    every PHI access and admin mutation is logged there via log_phi_access().
    admin-only; RLS on phi_audit_log independently restricts SELECT to admins
    too, so this is defense in depth, not the only access boundary.
    """
    limit = max(1, min(limit, 200))

    query = (
        supabase_admin.table('phi_audit_log')
        .select('id, event_type, user_id, user_role, resource_type, resource_id, facility_id, ip_address, details, created_at')
        .order('created_at', desc=True)
        .limit(limit + 1)
    )
    if before:
        query = query.lt('created_at', before)

    result = query.execute()
    rows = result.data or []
    has_more = len(rows) > limit
    rows = rows[:limit]

    return {
        'entries': rows,
        'hasMore': has_more,
        'nextCursor': rows[-1]['created_at'] if has_more and rows else None,
    }
