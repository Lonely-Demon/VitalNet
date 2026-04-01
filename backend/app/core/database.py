"""
Supabase database clients — three-client setup.

1. supabase_anon  — anon key, public reads (health check, facilities list).
2. get_supabase_for_user() — per-request RLS-scoped client for all case/profile data.
3. supabase_admin — service_role key, used ONLY for auth.admin.* operations.
                    Never use for case_records or profiles data queries.

Also exposes get_db_session() as a FastAPI Depends()-compatible dependency.
"""
import hashlib
from collections import OrderedDict
from threading import Lock
from typing import Optional

from fastapi import Header, HTTPException
from supabase import Client, create_client

from app.core.config import settings

_USER_CLIENT_CACHE_MAX = 128
_user_client_cache: "OrderedDict[str, Client]" = OrderedDict()
_user_client_lock = Lock()

# 1. Anon client — public reads only.
supabase_anon: Client = create_client(
    settings.supabase_url,
    settings.supabase_anon_key,
)


def get_supabase_for_user(raw_token: str) -> Client:
    """
    Creates a Supabase client scoped to the user's JWT so RLS applies.
    Call this in every endpoint that touches RLS-protected tables.
    """
    if not raw_token or raw_token.count(".") != 2:
        raise HTTPException(status_code=401, detail="Missing or malformed bearer token")

    token_fingerprint = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()

    with _user_client_lock:
        cached = _user_client_cache.get(token_fingerprint)
        if cached is not None:
            _user_client_cache.move_to_end(token_fingerprint)
            cached.postgrest.auth(raw_token)
            return cached

    client = create_client(settings.supabase_url, settings.supabase_anon_key)
    client.postgrest.auth(raw_token)

    with _user_client_lock:
        _user_client_cache[token_fingerprint] = client
        _user_client_cache.move_to_end(token_fingerprint)
        while len(_user_client_cache) > _USER_CLIENT_CACHE_MAX:
            _user_client_cache.popitem(last=False)

    return client


def get_db_session(authorization: Optional[str] = Header(None)) -> Client:
    """
    FastAPI Depends()-compatible dependency that extracts the Bearer token
    from the Authorization header and returns a user-scoped Supabase client.
    Raises HTTP 401 if the header is missing.
    """
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    raw_token = authorization.split(" ", 1)[-1]
    return get_supabase_for_user(raw_token)


# 3. Admin client — service_role key, bypasses RLS entirely.
# Use EXCLUSIVELY for auth.admin.* calls (create/list/update auth users).
supabase_admin: Client = create_client(
    settings.supabase_url,
    settings.supabase_service_role_key,
)
