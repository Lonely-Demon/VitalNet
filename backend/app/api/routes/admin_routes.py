import re
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app.core.auth import require_role
from app.core.correlation import get_correlation_id
from app.core.audit import AuditEventType, get_client_ip, log_phi_access
from app.core.database import get_supabase_for_user, supabase_admin
from pydantic import BaseModel, EmailStr

logger = logging.getLogger("vitalnet")

router = APIRouter(prefix='/api/admin', tags=['admin'])

# ── Role and Security Matrix Constraints ──────────────────────────────────────
ALLOWED_ROLES = {"asha_worker", "doctor", "facility_admin", "admin", "super_admin"}
ADMIN_ASSIGNABLE_ROLES = {"asha_worker", "doctor", "facility_admin"}
SUPER_ADMIN_ASSIGNABLE_ROLES = ALLOWED_ROLES
PASSWORD_POLICY_RE = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z\d]).{12,128}$")


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


def _effective_role(user: dict) -> str:
    return (user.get("resolved_role") or "").strip()


def _ensure_role_assignable(actor_role: str, target_role: str) -> None:
    assignable = SUPER_ADMIN_ASSIGNABLE_ROLES if actor_role == "super_admin" else ADMIN_ASSIGNABLE_ROLES
    if target_role not in assignable:
        raise HTTPException(status_code=403, detail="Role assignment not permitted")


def _validate_password(password: str) -> None:
    if not PASSWORD_POLICY_RE.match(password or ""):
        raise HTTPException(
            status_code=400,
            detail=(
                "Password must be 12-128 characters and include uppercase, lowercase, "
                "number, and symbol"
            ),
        )


def _mask_csv_value(value: str | None) -> str | None:
    if value is None:
        return None
    text = str(value)
    if text and text[0] in {"=", "+", "-", "@", "\t", "\r", "\n"}:
        return "'" + text
    return text


def _safe_role_error_detail() -> str:
    return "Invalid role selection"


# ── Pydantic models ───────────────────────────────────────────────────────────

class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: str                           # 'asha_worker' | 'doctor' | 'admin'
    facility_id: Optional[str] = None
    asha_id: Optional[str] = None
    is_active: Optional[bool] = None


class UpdateUserRequest(BaseModel):
    role: Optional[str] = None
    facility_id: Optional[str] = None
    asha_id: Optional[str] = None
    is_active: Optional[bool] = None


class CreateFacilityRequest(BaseModel):
    name: str
    type: str = 'PHC'
    address: Optional[str] = None
    district: Optional[str] = None
    state: str = 'Tamil Nadu'
    pincode: Optional[str] = None
    phone: Optional[str] = None


# ── User management ───────────────────────────────────────────────────────────

@router.get('/users')
async def list_users(
    request: Request,
    authorization: str = Header(None),
    user: dict = Depends(require_role('admin', 'super_admin')),
    page: int = 1,
    limit: int = 100,
):
    """
    Returns all users joined with their profiles.
    Uses admin client for auth.admin.list_users(), then enriches
    with profiles data for role/facility info.
    """
    actor_role = _effective_role(user)
    actor_facility_id = user.get("resolved_facility_id")
    limit = max(1, min(limit, 200))
    page = max(1, page)
    start = (page - 1) * limit
    end = start + limit - 1

    # Fetch profiles with pagination to avoid mass user enumeration
    profile_query = supabase_admin.table('profiles').select(
        'id, full_name, role, facility_id, asha_id, is_active, created_at, '
        'facilities(name, district)'
    )

    if actor_role != "super_admin" and actor_facility_id:
        profile_query = profile_query.eq("facility_id", actor_facility_id)

    profiles_result = profile_query.range(start, end).execute()
    profile_rows = profiles_result.data if profiles_result else []

    profiles_by_id = {p['id']: p for p in profile_rows}

    # Fetch auth users only for profile ids on current page
    auth_users = supabase_admin.auth.admin.list_users(page=page, per_page=limit)
    auth_users = [au for au in auth_users if str(au.id) in profiles_by_id]

    result = []
    for au in auth_users:
        profile = profiles_by_id.get(str(au.id), {})
        if actor_role != "super_admin" and actor_facility_id and profile.get("facility_id") != actor_facility_id:
            continue

        role_value = profile.get('role', 'asha_worker')
        result.append({
            'id':            str(au.id),
            'email':         _mask_csv_value(au.email),
            'full_name':     profile.get('full_name', ''),
            'role':          role_value,
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
        user_role=actor_role,
        resource_type="profiles",
        resource_id=f"page:{page}",
        facility_id=actor_facility_id,
        ip_address=get_client_ip(request),
        details={"count": len(result), "pagination": {"page": page, "limit": limit}},
    )

    return {
        "data": result,
        "page": page,
        "limit": limit,
        "total": len(profile_rows),
    }


@router.post('/users')
async def create_user(
    body: CreateUserRequest,
    request: Request,
    authorization: str = Header(None),
    user: dict = Depends(require_role('admin', 'super_admin')),
):
    """
    Creates a new auth user and their profile row.
    email_confirm=True so new users can log in immediately without
    going through email verification flow.
    """
    actor_role = _effective_role(user)
    requested_role = (body.role or "").strip()

    if requested_role not in ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail=_safe_role_error_detail())

    _ensure_role_assignable(actor_role, requested_role)
    _validate_password(body.password)

    if requested_role in {"doctor", "facility_admin", "asha_worker"} and not body.facility_id:
        raise HTTPException(status_code=400, detail="facility_id is required for non-admin users")

    if actor_role != "super_admin" and requested_role in {"admin", "super_admin"}:
        raise HTTPException(status_code=403, detail="Only super_admin can create admin-level users")

    if actor_role != "super_admin" and user.get("resolved_facility_id") and body.facility_id:
        if body.facility_id != user.get("resolved_facility_id"):
            raise HTTPException(status_code=403, detail="Cannot create users outside your facility")

    response = supabase_admin.auth.admin.create_user({
        'email':         body.email,
        'password':      body.password,
        'email_confirm': True,
        'user_metadata': {
            'full_name':   body.full_name,
            'role':        requested_role,
            'facility_id': body.facility_id or '',
        },
    })

    new_user_id = str(response.user.id)

    # Patch the profile row created by the DB trigger with extra fields
    profile_fields = {
        'role':        requested_role,
        'facility_id': body.facility_id,
        'asha_id':     body.asha_id,
    }
    if body.is_active is not None:
        profile_fields['is_active'] = body.is_active

    supabase_admin.table('profiles').update(profile_fields).eq('id', new_user_id).execute()

    log_phi_access(
        event_type=AuditEventType.PHI_CREATE,
        user_id=user.get("sub", "unknown"),
        user_role=actor_role,
        resource_type="profiles",
        resource_id=new_user_id,
        facility_id=body.facility_id,
        ip_address=get_client_ip(request),
        details={"created_role": requested_role},
    )

    return {'id': new_user_id, 'email': body.email}


@router.patch('/users/{user_id}')
async def update_user(
    user_id: str,
    body: UpdateUserRequest,
    request: Request,
    authorization: str = Header(None),
    user: dict = Depends(require_role('admin', 'super_admin')),
):
    """
    Updates profile fields (role, facility, asha_id, is_active).
    Also updates user_metadata in auth so the JWT hook re-embeds
    the new role on next login.
    """
    actor_role = _effective_role(user)

    target_profile_response = (
        supabase_admin.table("profiles")
        .select("id, role, facility_id, asha_id, is_active")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    target_profile = getattr(target_profile_response, "data", None) or {}
    if not target_profile:
        raise HTTPException(status_code=404, detail="User not found")

    if actor_role != "super_admin":
        if target_profile.get("role") in {"admin", "super_admin"}:
            raise HTTPException(status_code=403, detail="Cannot modify admin-level users")
        actor_facility = user.get("resolved_facility_id")
        if actor_facility and target_profile.get("facility_id") not in {actor_facility, None}:
            raise HTTPException(status_code=403, detail="Cannot modify users outside your facility")

    profile_update = {}
    meta_update = {}

    if body.role is not None:
        requested_role = body.role.strip()
        if requested_role not in ALLOWED_ROLES:
            raise HTTPException(status_code=400, detail=_safe_role_error_detail())

        _ensure_role_assignable(actor_role, requested_role)

        if actor_role != "super_admin" and requested_role in {"admin", "super_admin"}:
            raise HTTPException(status_code=403, detail="Only super_admin can grant admin roles")

        profile_update['role'] = requested_role
        meta_update['role'] = requested_role
    if body.facility_id is not None:
        if actor_role != "super_admin" and user.get("resolved_facility_id") and body.facility_id:
            if body.facility_id != user.get("resolved_facility_id"):
                raise HTTPException(status_code=403, detail="Cannot move users outside your facility")
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
            supabase_admin.auth.admin.update_user_by_id(
                user_id, {'user_metadata': meta_update}
            )
        except Exception as e:
            logger.error("Auth metadata update failed for user_id=%s: %s", user_id, e)
            if profile_update:
                logger.warning("Rolling back profile update due to auth metadata failure - user_id=%s", user_id)
                rollback_values = {}
                for k in profile_update.keys():
                    rollback_values[k] = target_profile.get(k)
                supabase_admin.table('profiles').update(rollback_values).eq('id', user_id).execute()
            raise HTTPException(status_code=500, detail="Failed to update user metadata. Profile update was rolled back.")

    log_phi_access(
        event_type=AuditEventType.PHI_UPDATE,
        user_id=user.get("sub", "unknown"),
        user_role=actor_role,
        resource_type="profiles",
        resource_id=user_id,
        facility_id=profile_update.get("facility_id") or target_profile.get("facility_id"),
        ip_address=get_client_ip(request),
        details={"fields_updated": sorted(profile_update.keys())},
    )

    return {'status': 'updated'}


@router.delete('/users/{user_id}')
async def deactivate_user(
    user_id: str,
    request: Request,
    authorization: str = Header(None),
    user: dict = Depends(require_role('admin', 'super_admin')),
):
    """
    Soft-deactivates: sets profiles.is_active = false.
    Does NOT delete the auth user or their case records.
    Hard deletion is intentionally not exposed via API.
    """
    actor_role = _effective_role(user)

    target_profile_response = (
        supabase_admin.table("profiles")
        .select("id, role, facility_id")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    target_profile = getattr(target_profile_response, "data", None) or {}
    if not target_profile:
        raise HTTPException(status_code=404, detail="User not found")

    if actor_role != "super_admin" and target_profile.get("role") in {"admin", "super_admin"}:
        raise HTTPException(status_code=403, detail="Cannot deactivate admin-level users")

    actor_facility = user.get("resolved_facility_id")
    if actor_role != "super_admin" and actor_facility and target_profile.get("facility_id") not in {actor_facility, None}:
        raise HTTPException(status_code=403, detail="Cannot deactivate users outside your facility")

    supabase_admin.table('profiles').update({'is_active': False}).eq('id', user_id).execute()

    log_phi_access(
        event_type=AuditEventType.PHI_UPDATE,
        user_id=user.get("sub", "unknown"),
        user_role=actor_role,
        resource_type="profiles",
        resource_id=user_id,
        facility_id=target_profile.get("facility_id"),
        ip_address=get_client_ip(request),
        details={"is_active": False, "changed_at": datetime.now(timezone.utc).isoformat()},
    )

    return {'status': 'deactivated'}


@router.post('/users/{user_id}/reactivate')
async def reactivate_user(
    user_id: str,
    request: Request,
    authorization: str = Header(None),
    user: dict = Depends(require_role('admin', 'super_admin')),
):
    actor_role = _effective_role(user)

    target_profile_response = (
        supabase_admin.table("profiles")
        .select("id, role, facility_id")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    target_profile = getattr(target_profile_response, "data", None) or {}
    if not target_profile:
        raise HTTPException(status_code=404, detail="User not found")

    if actor_role != "super_admin" and target_profile.get("role") in {"admin", "super_admin"}:
        raise HTTPException(status_code=403, detail="Cannot reactivate admin-level users")

    actor_facility = user.get("resolved_facility_id")
    if actor_role != "super_admin" and actor_facility and target_profile.get("facility_id") not in {actor_facility, None}:
        raise HTTPException(status_code=403, detail="Cannot reactivate users outside your facility")

    supabase_admin.table('profiles').update({'is_active': True}).eq('id', user_id).execute()

    log_phi_access(
        event_type=AuditEventType.PHI_UPDATE,
        user_id=user.get("sub", "unknown"),
        user_role=actor_role,
        resource_type="profiles",
        resource_id=user_id,
        facility_id=target_profile.get("facility_id"),
        ip_address=get_client_ip(request),
        details={"is_active": True, "changed_at": datetime.now(timezone.utc).isoformat()},
    )

    return {'status': 'reactivated'}


# ── Facilities management ─────────────────────────────────────────────────────

@router.get('/facilities')
async def list_facilities(
    request: Request,
    authorization: str = Header(None),
    user: dict = Depends(require_role('admin', 'super_admin', 'facility_admin')),
):
    actor_role = _effective_role(user)
    actor_facility = user.get("resolved_facility_id")

    query = supabase_admin.table('facilities').select('*').order('name')
    if actor_role == 'facility_admin' and actor_facility:
        query = query.eq('id', actor_facility)

    result = query.execute()

    log_phi_access(
        event_type=AuditEventType.PHI_READ,
        user_id=user.get("sub", "unknown"),
        user_role=actor_role,
        resource_type="facilities",
        resource_id="list",
        facility_id=actor_facility,
        ip_address=get_client_ip(request),
        details={"count": len(result.data or [])},
    )

    return result.data


@router.post('/facilities')
async def create_facility(
    body: CreateFacilityRequest,
    request: Request,
    authorization: str = Header(None),
    user: dict = Depends(require_role('admin', 'super_admin')),
):
    if _effective_role(user) != 'super_admin':
        raise HTTPException(status_code=403, detail='Only super_admin can create facilities')

    result = supabase_admin.table('facilities').insert(body.model_dump()).execute()

    created_id = result.data[0]['id'] if result.data else None
    log_phi_access(
        event_type=AuditEventType.PHI_CREATE,
        user_id=user.get("sub", "unknown"),
        user_role=_effective_role(user),
        resource_type="facilities",
        resource_id=created_id,
        facility_id=created_id,
        ip_address=get_client_ip(request),
        details={"name": body.name},
    )

    return result.data[0]


@router.patch('/facilities/{facility_id}/toggle')
async def toggle_facility(
    facility_id: str,
    request: Request,
    authorization: str = Header(None),
    user: dict = Depends(require_role('admin', 'super_admin')),
):
    if _effective_role(user) != 'super_admin':
        raise HTTPException(status_code=403, detail='Only super_admin can toggle facility state')

    current = supabase_admin.table('facilities').select('id, is_active').eq('id', facility_id).single().execute()
    if not current.data:
        raise HTTPException(status_code=404, detail="Facility not found")
    
    current_state = current.data['is_active']
    new_state = not current_state
    
    result = (
        supabase_admin.table('facilities')
        .update({'is_active': new_state})
        .eq('id', facility_id)
        .eq('is_active', current_state)
        .execute()
    )
    
    if not result.data:
        logger.warning(
            "Facility toggle race condition detected for facility_id=%s - concurrent modification",
            facility_id
        )
        raise HTTPException(
            status_code=409,
            detail="Facility was modified by another admin. Please retry."
        )

    # Compliance audit trail checks after successful toggle
    profile_count = (
        supabase_admin.table("profiles")
        .select("id")
        .eq("facility_id", facility_id)
        .eq("is_active", True)
        .execute()
    )
    active_profile_rows = profile_count.data or []

    open_case_count = (
        supabase_admin.table("case_records")
        .select("id")
        .eq("facility_id", facility_id)
        .is_("reviewed_at", "null")
        .is_("deleted_at", "null")
        .execute()
    )
    open_case_rows = open_case_count.data or []

    log_phi_access(
        event_type=AuditEventType.PHI_UPDATE,
        user_id=user.get("sub", "unknown"),
        user_role=_effective_role(user),
        resource_type="facilities",
        resource_id=facility_id,
        facility_id=facility_id,
        ip_address=get_client_ip(request),
        details={
            "is_active": new_state,
            "active_profiles": len(active_profile_rows),
            "open_cases": len(open_case_rows),
        },
    )

    return {'is_active': new_state}


# ── System stats ──────────────────────────────────────────────────────────────

@router.get('/stats')
async def get_stats(
    authorization: str = Header(None),
    user: dict = Depends(require_role('admin', 'super_admin', 'facility_admin')),
):
    actor_role = _effective_role(user)
    actor_facility = user.get("resolved_facility_id")

    token = _extract_token(_header_or_401(authorization))
    db = get_supabase_for_user(token)

    # Fetch cases with pagination to avoid unbounded queries and prevent server OOM
    cases_data = []
    page_size = 1000
    page_offset = 0
    has_more = True
    
    while has_more:
        query = db.table('case_records').select('triage_level').is_('deleted_at', 'null')
        if actor_role == 'facility_admin' and actor_facility:
            query = query.eq('facility_id', actor_facility)
        
        cases_page = query.limit(page_size).range(page_offset, page_offset + page_size - 1).execute()
        cases_data.extend(cases_page.data)
        if len(cases_page.data) < page_size:
            has_more = False
        else:
            page_offset += page_size

    # Fetch profiles with pagination to avoid unbounded queries and prevent server OOM
    profiles_data = []
    page_offset = 0
    has_more = True
    
    while has_more:
        query = db.table('profiles').select('role, is_active')
        if actor_role == 'facility_admin' and actor_facility:
            query = query.eq('facility_id', actor_facility)
            
        profiles_page = query.limit(page_size).range(page_offset, page_offset + page_size - 1).execute()
        profiles_data.extend(profiles_page.data)
        if len(profiles_page.data) < page_size:
            has_more = False
        else:
            page_offset += page_size

    triage_counts = {'EMERGENCY': 0, 'URGENT': 0, 'ROUTINE': 0}
    for c in cases_data:
        level = c.get('triage_level', 'ROUTINE')
        triage_counts[level] = triage_counts.get(level, 0) + 1

    role_counts = {}
    active_count = 0
    for p in profiles_data:
        role_counts[p['role']] = role_counts.get(p['role'], 0) + 1
        if p['is_active']:
            active_count += 1

    return {
        'total_cases':   len(cases_data),
        'triage_counts': triage_counts,
        'total_users':   len(profiles_data),
        'active_users':  active_count,
        'role_counts':   role_counts,
    }
