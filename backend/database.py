"""
Supabase database client — Phase 6 replacement for SQLAlchemy/SQLite.

Module-level anon client: for unauthenticated / public queries (health check, facilities).
Per-request JWT client: for all RLS-protected tables (case_records, profiles).
"""
from supabase import create_client, Client
from config import settings

# Module-level client — anon key, no user context.
# Use ONLY for public tables (facilities) and health checks.
supabase: Client = create_client(
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
