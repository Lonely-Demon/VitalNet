from jose import jwt, JWTError
from fastapi import Header, HTTPException, status, Depends
from config import settings

ALGORITHM = 'HS256'
AUDIENCE = 'authenticated'


async def get_current_user(authorization: str = Header(None)) -> dict:
    """
    Extracts and locally validates the Supabase JWT from the
    Authorization: Bearer <token> header.
    Returns the decoded payload (user_id, role, facility_id, expiry).
    Raises HTTP 401 on any failure.
    No network call to Supabase is made. Offline-compatible.
    """
    if not authorization or not authorization.startswith('Bearer '):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Missing or malformed Authorization header',
            headers={'WWW-Authenticate': 'Bearer'},
        )

    token = authorization.split(' ', 1)[1]

    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=[ALGORITHM],
            audience=AUDIENCE,
        )
        return payload

    except JWTError as e:
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
