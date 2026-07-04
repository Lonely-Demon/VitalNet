"""
Authentication — hybrid JWT verification.

Fast path: verify the Supabase JWT signature + exp + aud LOCALLY (HS256 using
supabase_jwt_secret), so the common case costs no network round-trip. This
removes a Supabase auth call from every authenticated request (a large hot-path
latency win, and it means the API keeps serving if Supabase auth has a blip).

Fallback: if local verification fails — e.g. an ES256/asymmetric-key project
whose token this shared secret cannot verify — fall back to Supabase's
get_user(), which validates any signature type. So this is safe regardless of
the project's signing algorithm; HS256 projects get the full speed-up,
asymmetric-key projects transparently degrade to the previous network behaviour.

Revocation / deactivation: a valid-but-revoked token, or a user an admin has
deactivated (profiles.is_active = false), would otherwise keep working until the
token naturally expires (~1h). Previously the backend never checked is_active at
all — a deactivated user's unexpired token could still call the API. We now
re-check is_active per user on a short TTL (revocation_recheck_seconds), cached
in-process so the vast majority of requests still pay no network cost. This
bounds post-deactivation access to at most that TTL instead of the full token
lifetime, while keeping the hot path cheap.
"""
import base64
import json
import time
from typing import Dict, Tuple

from fastapi import Depends, Header, HTTPException, status
from jose import jwt, JWTError

from app.core.config import settings
from app.core.database import supabase_anon, get_supabase_for_user

ALGORITHM = "HS256"
AUDIENCE = "authenticated"

# In-process cache: user_id -> (checked_at_epoch_seconds, is_active_bool).
# Per-worker; each uvicorn worker maintains its own and re-checks within the TTL.
_revocation_cache: Dict[str, Tuple[float, bool]] = {}


def _decode_payload_unverified(token: str) -> dict:
    """Base64-decode the JWT payload segment WITHOUT verifying the signature.
    Only ever used after the signature has already been validated by another
    path (network get_user), to read custom claims get_user() omits."""
    payload_b64 = token.split(".")[1]
    payload_b64 += "=" * (-len(payload_b64) % 4)
    return json.loads(base64.urlsafe_b64decode(payload_b64).decode("utf-8"))


def _verify_token(token: str) -> dict:
    """
    Return the validated JWT payload, or raise JWTError / Exception on failure.
    Tries local HS256 verification first (fast), falls back to network.
    """
    if settings.jwt_local_verification:
        try:
            return jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=[ALGORITHM],
                audience=AUDIENCE,
                options={"verify_aud": True, "verify_exp": True},
            )
        except JWTError:
            # Could be an asymmetric-key project, or a genuinely bad token.
            # Fall through to the network check, which is authoritative for
            # any signing algorithm and also catches revocation immediately.
            pass

    # Network fallback: get_user() raises if the token is invalid/expired/revoked.
    supabase_anon.auth.get_user(token)
    return _decode_payload_unverified(token)


def _is_user_active(user_id: str, token: str) -> bool:
    """
    Return whether the user's profile is active, cached per user for
    revocation_recheck_seconds. On a cache miss/expiry, re-reads
    profiles.is_active via the caller's own RLS-scoped client.
    Fails OPEN to the last known state (or active-unknown) on a DB error, so a
    transient DB blip does not lock out every authenticated user — but the miss
    is not cached, so it re-checks on the next request.
    """
    now = time.time()
    cached = _revocation_cache.get(user_id)
    if cached and (now - cached[0]) < settings.revocation_recheck_seconds:
        return cached[1]

    try:
        db = get_supabase_for_user(token)
        res = db.table("profiles").select("is_active").eq("id", user_id).single().execute()
        active = True if res.data is None else bool(res.data.get("is_active", True))
        _revocation_cache[user_id] = (now, active)
        return active
    except Exception:
        # Do not cache the failure; fall back to last known state or allow.
        return cached[1] if cached else True


async def get_current_user(authorization: str = Header(None)) -> dict:
    """
    Extract and validate the Supabase JWT from the Authorization: Bearer <token>
    header. Returns the full JWT payload dict. Raises HTTP 401 on any auth
    failure, HTTP 403 if the account has been deactivated.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = authorization.split(" ", 1)[1]

    try:
        payload = _verify_token(token)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if user_id and not _is_user_active(user_id, token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated. Contact your administrator.",
        )

    return payload


def require_role(*roles: str):
    """
    Returns a dependency that enforces the caller has one of the given roles.
    Usage: Depends(require_role('doctor', 'admin'))
    """
    async def role_guard(user: dict = Depends(get_current_user)) -> dict:
        # Check both user_metadata (custom data) and app_metadata (auth provider data)
        user_role = (
            user.get("user_metadata", {}).get("role")
            or user.get("app_metadata", {}).get("role")
            or ""
        )
        if user_role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{user_role}' is not permitted for this endpoint.",
            )
        return user

    return role_guard


def verify_sub_for_rate_limit(token: str) -> str | None:
    """
    Best-effort extraction of a VERIFIED user id for rate-limiting keys.
    Returns the sub only if the token signature verifies locally (HS256);
    returns None otherwise so the caller falls back to IP-based limiting.
    This prevents an attacker from forging a token with a victim's sub to
    consume the victim's rate-limit budget.
    """
    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=[ALGORITHM],
            audience=AUDIENCE,
            options={"verify_aud": True, "verify_exp": True},
        )
        return payload.get("sub")
    except JWTError:
        return None
