"""
Supabase database clients.

1. supabase_anon  — anon key, public reads (health check) and the auth-token
                    verification network fallback in app/core/auth.py.
2. get_supabase_for_user() — per-request client scoped to the caller's JWT so
                    Row Level Security applies. Used for all user-facing case /
                    profile / analytics data access.
3. supabase_admin — service_role key. Bypasses RLS entirely. Used for admin
                    GLOBAL operations that legitimately must see across all
                    facilities/users: auth.admin.* (create/list/update auth
                    users) AND cross-tenant reads/writes on profiles, facilities,
                    and case_records behind admin-only endpoints.

   SECURITY NOTE: because supabase_admin bypasses RLS, every route that uses it
   (all of app/api/routes/admin_routes.py) MUST be guarded by
   require_role('admin') — that role check is the ONLY access-control boundary
   on those endpoints; there is no RLS backstop. Do not use supabase_admin in
   any route that isn't admin-gated. tests/test_admin_authz.py enforces this.
"""
import hmac
from typing import Optional

from fastapi import HTTPException
from supabase import Client, create_client
from supabase.lib.client_options import ClientOptions

from app.core.config import settings

# 1. Anon client — public reads and the auth verification fallback.
supabase_anon: Client = create_client(
    settings.supabase_url,
    settings.supabase_anon_key,
)


def get_supabase_for_user(raw_token: str) -> Client:
    """
    Creates a Supabase client scoped to the user's JWT so RLS applies.
    Call this in every endpoint that touches RLS-protected tables.

    Note: constructs a fresh client per call. This is deliberate for
    correctness — a shared client with a mutated per-request auth token would
    race across concurrently-served requests. A shared-connection optimization
    is possible but only safely once the routes are fully async and the
    auth-set/query pair is provably atomic; see CODEBASE_MAP.md.
    """
    client = create_client(settings.supabase_url, settings.supabase_anon_key)
    client.postgrest.auth(raw_token)
    return client


# 3. Admin client — service_role key, bypasses RLS entirely.
# Use ONLY inside require_role('admin')-guarded routes (see the SECURITY NOTE above).
supabase_admin: Client = create_client(
    settings.supabase_url,
    settings.supabase_service_role_key,
    options=ClientOptions(auto_refresh_token=False, persist_session=False),
)


def extract_bearer_token(authorization: Optional[str]) -> str:
    """
    Extract and format-validate a Bearer token from the Authorization header.
    Raises HTTP 401 on a missing/malformed header or a token that isn't a
    well-formed 3-part JWT, before any signature verification is attempted.
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    parts = authorization.strip().split(" ", 1)
    if len(parts) != 2 or not hmac.compare_digest(parts[0].lower(), "bearer"):
        raise HTTPException(
            status_code=401,
            detail="Malformed Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = parts[1].strip()
    if token.count(".") != 2:
        raise HTTPException(
            status_code=401,
            detail="Malformed bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


def validate_schema_compatibility() -> None:
    """
    Startup gate: verify the tables this app depends on actually exist and are
    queryable, so a schema drift or un-run migration fails fast at boot instead
    of surfacing as a confusing 500 on a patient's first request. Queries just
    one row per table (empty tables pass).
    """
    tables_to_check = ["facilities", "profiles", "case_records"]
    for table in tables_to_check:
        try:
            supabase_anon.table(table).select("id").limit(1).execute()
        except Exception as e:
            raise RuntimeError(
                f"Database schema compatibility check failed for table '{table}': {e}"
            )
