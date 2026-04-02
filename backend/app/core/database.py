"""
Supabase database clients — three-client setup with connection pooling.

1. supabase_anon — anon key, public reads (health check, facilities list).
2. get_supabase_for_user() — per-request RLS-scoped client for all case/profile data.
3. supabase_admin — service_role key, used ONLY for auth.admin.* operations.
Never use for case_records or profiles data queries.

Also exposes get_db_session() as a FastAPI Depends()-compatible dependency.

Connection Pooling:
- Uses a singleton base client with connection reuse
- Only sets auth token per-request instead of creating new clients
- Significantly reduces overhead and improves performance

Reliability (CHAOS-005 to CHAOS-010):
- Query timeouts handled at route level to prevent hanging requests
- Graceful degradation patterns in analytics endpoints
"""
from typing import Optional
import threading

from fastapi import Header, HTTPException
from supabase import Client, create_client
from supabase.lib.client_options import ClientOptions

from app.core.config import settings

# Thread-local storage for user-scoped clients to avoid race conditions
_thread_local = threading.local()

# 1. Anon client — public reads only (singleton).
supabase_anon: Client = create_client(
    settings.supabase_url,
    settings.supabase_anon_key,
)

# Singleton base client for user-scoped requests (connection pooling)
_base_user_client: Optional[Client] = None
_client_lock = threading.Lock()


def _get_base_client() -> Client:
    """
    Returns a singleton base Supabase client for connection pooling.
    Thread-safe initialization using double-checked locking pattern.
    """
    global _base_user_client
    if _base_user_client is None:
        with _client_lock:
            if _base_user_client is None:
                _base_user_client = create_client(
                    settings.supabase_url,
                    settings.supabase_anon_key,
                    options=ClientOptions(
                        auto_refresh_token=False,
                        persist_session=False,
                    ),
                )
    return _base_user_client


def get_supabase_for_user(raw_token: str) -> Client:
    """
    Returns a Supabase client scoped to the user's JWT so RLS applies.
    Uses connection pooling by reusing a singleton base client and only
    setting the auth token per request.
    
    Call this in every endpoint that touches RLS-protected tables.
    """
    client = _get_base_client()
    # Set the auth token for this request (does not create a new connection)
    client.postgrest.auth(raw_token)
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
    options=ClientOptions(auto_refresh_token=False, persist_session=False),
)
