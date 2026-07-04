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
