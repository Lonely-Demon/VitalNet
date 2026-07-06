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

Authorization fields: role and facility_id are NEVER trusted from the JWT's
user_metadata — that's client-settable at signup and can go stale for the
life of the token after an admin changes it. Every request resolves fresh
values from the profiles table (same short-TTL cache as is_active, one
combined query) into resolved_role / resolved_facility_id. require_role()
and every route's authorization checks must read those, not user_metadata.
"""
import time
from typing import Dict, Optional, Tuple

from fastapi import Depends, Header, HTTPException, status
from jose import jwt, JWTError

from app.core.config import settings
from app.core.database import supabase_anon, get_supabase_for_user, extract_bearer_token

ALGORITHM = "HS256"
AUDIENCE = "authenticated"

# In-process cache: user_id -> (checked_at_epoch_seconds, is_active, role, facility_id).
# Per-worker; each uvicorn worker maintains its own and re-checks within the TTL.
_ProfileCacheEntry = Tuple[float, bool, str, Optional[str]]
_profile_cache: Dict[str, _ProfileCacheEntry] = {}


def _decode_local(token: str) -> Optional[dict]:
    """Locally verify signature/exp/aud (HS256, supabase_jwt_secret). Returns
    None if verification fails — a bad token, or an asymmetric-key project
    this shared secret cannot verify."""
    try:
        return jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=[ALGORITHM],
            audience=AUDIENCE,
            options={"verify_aud": True, "verify_exp": True},
        )
    except JWTError:
        return None


def _verify_token(token: str) -> dict:
    """
    Return the validated JWT payload, or raise JWTError / Exception on failure.
    Tries local HS256 verification first (fast), falls back to network.
    """
    if settings.jwt_local_verification:
        payload = _decode_local(token)
        if payload is not None:
            return payload
        # Could be an asymmetric-key project, or a genuinely bad token.
        # Fall through to the network check, which is authoritative for any
        # signing algorithm and also catches revocation immediately.

    # Network fallback: get_user() raises if the token is invalid/expired/revoked.
    supabase_anon.auth.get_user(token)
    # Signature already validated above (network call) — read claims get_user()
    # omits without re-verifying.
    return jwt.get_unverified_claims(token)


def _resolve_profile(user_id: str, token: str) -> Tuple[bool, str, Optional[str]]:
    """
    Return (is_active, role, facility_id) for the user, cached per user for
    revocation_recheck_seconds. On a cache miss/expiry, re-reads a single row
    from `profiles` via the caller's own RLS-scoped client.

    Fails CLOSED when the query succeeds but no profile row exists (a real,
    confirmed state — the account is not provisioned) — previously `.single()`
    raised on zero rows and was silently treated as "active", which let an
    authenticated-but-unprovisioned Supabase user through with no role at all.

    Fails OPEN to the last cached state (or unresolved/inactive) only on a
    transient error (network/DB blip) so an outage does not lock out every
    authenticated user; the miss is not cached, so it re-checks next request.
    """
    now = time.time()
    cached = _profile_cache.get(user_id)
    if cached and (now - cached[0]) < settings.revocation_recheck_seconds:
        return cached[1], cached[2], cached[3]

    try:
        db = get_supabase_for_user(token)
        res = (
            db.table("profiles")
            .select("role, facility_id, is_active")
            .eq("id", user_id)
            .maybe_single()
            .execute()
        )
        profile = res.data if res else None
    except Exception:
        # Transient failure — do not cache; fall back to last known state.
        if cached:
            return cached[1], cached[2], cached[3]
        return True, "", None

    if profile is None:
        # Confirmed: no profile row for this authenticated user. Fail closed.
        _profile_cache[user_id] = (now, False, "", None)
        return False, "", None

    is_active = bool(profile.get("is_active", True))
    role = profile.get("role") or ""
    facility_id = profile.get("facility_id")
    _profile_cache[user_id] = (now, is_active, role, facility_id)
    return is_active, role, facility_id


async def get_current_user(authorization: str = Header(None)) -> dict:
    """
    Extract and validate the Supabase JWT from the Authorization: Bearer <token>
    header. Returns the full JWT payload dict. Raises HTTP 401 on any auth
    failure, HTTP 403 if the account has been deactivated.
    """
    token = extract_bearer_token(authorization)

    try:
        payload = _verify_token(token)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    role, facility_id = "", None
    if user_id:
        is_active, role, facility_id = _resolve_profile(user_id, token)
        if not is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated or not provisioned. Contact your administrator.",
            )

    payload["resolved_role"] = role
    payload["resolved_facility_id"] = facility_id
    return payload


def require_role(*roles: str):
    """
    Returns a dependency that enforces the caller has one of the given roles.
    Usage: Depends(require_role('doctor', 'admin'))
    """
    async def role_guard(user: dict = Depends(get_current_user)) -> dict:
        # resolved_role comes from the profiles table (see get_current_user),
        # never from JWT user_metadata — that value is client-settable and
        # can go stale for the life of the token after an admin changes it.
        user_role = user.get("resolved_role") or ""
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
    payload = _decode_local(token)
    return payload.get("sub") if payload else None
