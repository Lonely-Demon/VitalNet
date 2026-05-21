import base64
import json
from typing import Any

from fastapi import Depends, Header, HTTPException, status

from app.core.database import extract_bearer_token, get_supabase_for_user, supabase_anon

AUDIENCE = "authenticated"


def _decode_jwt_part(part: str) -> dict[str, Any]:
    padded = part + "=" * (-len(part) % 4)
    decoded = base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")
    return json.loads(decoded)


async def get_current_user(authorization: str = Header(default=None)) -> dict[str, Any]:
    """
    Validate bearer token with Supabase and resolve authorization fields from DB profile.
    Never trusts role/facility_id from JWT metadata for backend authorization decisions.
    """
    token = extract_bearer_token(authorization)

    try:
        user_response = supabase_anon.auth.get_user(token)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_obj = getattr(user_response, "user", None)
    user_id = str(getattr(user_obj, "id", "") or "")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication context",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = _decode_jwt_part(token.split(".")[1])
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token payload",
            headers={"WWW-Authenticate": "Bearer"},
        )

    audience = payload.get("aud")
    if audience not in {AUDIENCE, [AUDIENCE]}:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token audience",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_db = get_supabase_for_user(token)
    profile_result = (
        user_db.table("profiles")
        .select("id, role, facility_id, is_active")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    profile = profile_result.data or {}

    if not profile:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Profile not provisioned")

    if profile.get("is_active") is False:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account deactivated")

    return {
        "sub": user_id,
        "email": getattr(user_obj, "email", None),
        "app_metadata": getattr(user_obj, "app_metadata", {}) or {},
        "user_metadata": getattr(user_obj, "user_metadata", {}) or {},
        "resolved_role": profile.get("role") or "",
        "resolved_facility_id": profile.get("facility_id"),
        "is_active": bool(profile.get("is_active", True)),
        "profile": profile,
    }


def require_role(*roles: str):
    """Returns a dependency that enforces one of the provided server-resolved roles."""

    allowed_roles = {r for r in roles if r}

    async def role_guard(user: dict = Depends(get_current_user)) -> dict:
        user_role = user.get("resolved_role") or ""
        if user_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for this endpoint",
            )
        return user

    return role_guard
