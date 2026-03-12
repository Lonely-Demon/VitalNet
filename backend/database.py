"""
Supabase database clients — Phase 7 three-client setup.

1. supabase_anon  — anon key, public reads (health check, facilities list).
2. get_supabase_for_user() — per-request RLS-scoped client for all case/profile data.
3. supabase_admin — service_role key, used ONLY for auth.admin.* operations.
                    Never use for case_records or profiles data queries.
"""
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions
from config import settings

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


# 3. Admin client — service_role key, bypasses RLS entirely.
# Use EXCLUSIVELY for auth.admin.* calls (create/list/update auth users).
supabase_admin: Client = create_client(
    settings.supabase_url,
    settings.supabase_service_role_key,
    options=ClientOptions(auto_refresh_token=False, persist_session=False),
)
