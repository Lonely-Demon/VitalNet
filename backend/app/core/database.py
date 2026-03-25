"""
Supabase database clients — three-client setup.

1. supabase_anon  — anon key, public reads (health check, facilities list).
2. get_supabase_for_user() — per-request RLS-scoped client for all case/profile data.
3. supabase_admin — service_role key, used ONLY for auth.admin.* operations.
                    Never use for case_records or profiles data queries.

Also exposes get_db_session() as a FastAPI Depends()-compatible dependency.
"""
from typing import Optional

from fastapi import Header, HTTPException
from supabase import Client, create_client
from supabase.lib.client_options import ClientOptions

from app.core.config import settings

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
    client = create_client(settings.supabase_url, settings.supabase_anon_key)
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
