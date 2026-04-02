import logging

from fastapi import APIRouter, Depends, Header, HTTPException

from app.core.auth import require_role
from app.core.correlation import get_correlation_id
from app.core.database import supabase_admin
from pydantic import BaseModel, EmailStr
from typing import Optional

logger = logging.getLogger("vitalnet")

router = APIRouter(prefix='/api/admin', tags=['admin'])


# ── Pydantic models ───────────────────────────────────────────────────────────

class CreateUserRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str
    role: str                           # 'asha_worker' | 'doctor' | 'admin'
    facility_id: Optional[str] = None
    asha_id: Optional[str] = None


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
    authorization: str = Header(None),
    user: dict = Depends(require_role('admin')),
):
    """
    Returns all users joined with their profiles.
    Uses admin client for auth.admin.list_users(), then enriches
    with profiles data for role/facility info.
    """
    # Fetch all profiles (admin SELECT policy covers this)
    profiles_result = supabase_admin.table('profiles').select(
        'id, full_name, role, facility_id, asha_id, is_active, created_at, '
        'facilities(name, district)'
    ).execute()

    profiles_by_id = {p['id']: p for p in profiles_result.data}

    # Fetch auth users for email + last_sign_in — per_page=1000 avoids pagination gap
    auth_users = supabase_admin.auth.admin.list_users(page=1, per_page=1000)

    result = []
    for au in auth_users:
        profile = profiles_by_id.get(str(au.id), {})
        result.append({
            'id':            str(au.id),
            'email':         au.email,
            'full_name':     profile.get('full_name', ''),
            'role':          profile.get('role', 'asha_worker'),
            'facility_id':   profile.get('facility_id'),
            'facility_name': (profile.get('facilities') or {}).get('name'),
            'asha_id':       profile.get('asha_id'),
            'is_active':     profile.get('is_active', True),
            'created_at':    str(au.created_at),
            'last_sign_in':  str(au.last_sign_in_at) if au.last_sign_in_at else None,
        })

    return result


@router.post('/users')
async def create_user(
    body: CreateUserRequest,
    authorization: str = Header(None),
    user: dict = Depends(require_role('admin')),
):
    """
    Creates a new auth user and their profile row.
    email_confirm=True so new users can log in immediately without
    going through email verification flow.
    """
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

    # Patch the profile row created by the DB trigger with extra fields
    supabase_admin.table('profiles').update({
        'facility_id': body.facility_id,
        'asha_id':     body.asha_id,
    }).eq('id', new_user_id).execute()

    return {'id': new_user_id, 'email': body.email}


@router.patch('/users/{user_id}')
async def update_user(
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
        profile_result = supabase_admin.table('profiles').update(profile_update).eq('id', user_id).execute()

        if not profile_result.data:
            logger.warning("Profile update failed - user_id=%s not found", user_id)
            raise HTTPException(status_code=404, detail="User profile not found")

    if meta_update:
        try:
            supabase_admin.auth.admin.update_user_by_id(
                user_id, {'user_metadata': meta_update}
            )
        except Exception as e:
            logger.error("Auth metadata update failed for user_id=%s: %s", user_id, e)
            if profile_update:
                logger.warning("Rolling back profile update due to auth metadata failure - user_id=%s", user_id)
                supabase_admin.table('profiles').update({k: v for k, v in profile_update.items()}).eq('id', user_id).execute()
            raise HTTPException(status_code=500, detail="Failed to update user metadata. Profile update was rolled back.")

    return {'status': 'updated'}


@router.delete('/users/{user_id}')
async def deactivate_user(
    user_id: str,
    authorization: str = Header(None),
    user: dict = Depends(require_role('admin')),
):
    """
    Soft-deactivates: sets profiles.is_active = false.
    Does NOT delete the auth user or their case records.
    Hard deletion is intentionally not exposed via API.
    """
    supabase_admin.table('profiles').update({'is_active': False}).eq('id', user_id).execute()
    return {'status': 'deactivated'}


@router.post('/users/{user_id}/reactivate')
async def reactivate_user(
    user_id: str,
    authorization: str = Header(None),
    user: dict = Depends(require_role('admin')),
):
    supabase_admin.table('profiles').update({'is_active': True}).eq('id', user_id).execute()
    return {'status': 'reactivated'}


# ── Facilities management ─────────────────────────────────────────────────────

@router.get('/facilities')
async def list_facilities(
    authorization: str = Header(None),
    user: dict = Depends(require_role('admin')),
):
    result = supabase_admin.table('facilities').select('*').order('name').execute()
    return result.data


@router.post('/facilities')
async def create_facility(
    body: CreateFacilityRequest,
    authorization: str = Header(None),
    user: dict = Depends(require_role('admin')),
):
    result = supabase_admin.table('facilities').insert(body.model_dump()).execute()
    return result.data[0]


@router.patch('/facilities/{facility_id}/toggle')
async def toggle_facility(
    facility_id: str,
    authorization: str = Header(None),
    user: dict = Depends(require_role('admin')),
):
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
    
    return {'is_active': new_state}


# ── System stats ──────────────────────────────────────────────────────────────

@router.get('/stats')
async def get_stats(
    authorization: str = Header(None),
    user: dict = Depends(require_role('admin')),
):
    # Fetch cases with pagination to avoid unbounded queries
    cases_data = []
    page_size = 1000
    page_offset = 0
    has_more = True
    
    # Paginate through all case records
    while has_more:
        cases_page = supabase_admin.table('case_records').select('triage_level').is_('deleted_at', 'null').limit(page_size).range(page_offset, page_offset + page_size - 1).execute()
        cases_data.extend(cases_page.data)
        if len(cases_page.data) < page_size:
            has_more = False
        else:
            page_offset += page_size
    
    # Fetch profiles with pagination to avoid unbounded queries
    profiles_data = []
    page_offset = 0
    has_more = True
    
    while has_more:
        profiles_page = supabase_admin.table('profiles').select('role, is_active').limit(page_size).range(page_offset, page_offset + page_size - 1).execute()
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
        'total_cases': len(cases_data),
        'triage_counts': triage_counts,
        'total_users': len(profiles_data),
        'active_users': active_count,
        'role_counts': role_counts,
    }
