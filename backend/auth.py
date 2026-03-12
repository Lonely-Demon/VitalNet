from jose import jwt, JWTError
from fastapi import Header, HTTPException, status, Depends
from config import settings

ALGORITHM = 'HS256'
AUDIENCE = 'authenticated'

from database import supabase_anon
import base64
import json


async def get_current_user(authorization: str = Header(None)) -> dict:
    """
    Extracts and validates the Supabase JWT from the
    Authorization: Bearer <token> header.
    Returns the full JWT payload dictionary.
    Raises HTTP 401 on any failure.
    Uses Supabase's get_user() to support ES256 signatures and instant revocation.
    """
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Missing or malformed Authorization header',
            headers={'WWW-Authenticate': 'Bearer'},
        )

    token = authorization.split(' ', 1)[1]

    try:
        # 1. Validate the token cryptographically and check revocation
        supabase_anon.auth.get_user(token)
        
        # 2. Extract the payload manually (since get_user() omits custom JWT claims)
        payload_b64 = token.split('.')[1]
        payload_b64 += '=' * (-len(payload_b64) % 4)
        payload_json = base64.urlsafe_b64decode(payload_b64).decode('utf-8')
        
        return json.loads(payload_json)

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f'Invalid or expired token: {str(e)}',
            headers={'WWW-Authenticate': 'Bearer'},
        )


def require_role(*roles: str):
    """
    Returns a dependency that enforces the caller has one of the given roles.
    Usage: Depends(require_role('doctor', 'admin'))
    """
    async def role_guard(user: dict = Depends(get_current_user)) -> dict:
        user_role = (
            user.get('user_metadata', {}).get('role', '')
        )
        if user_role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f'Role {user_role!r} is not permitted for this endpoint.',
            )
        return user
    return role_guard
