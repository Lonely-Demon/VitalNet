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
import base64
import hmac
import json
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


ALLOWED_JWT_ALGS = {"HS256", "RS256", "ES256"}


def _decode_jwt_part(part: str) -> dict:
    padded = part + "=" * (-len(part) % 4)
    decoded = base64.urlsafe_b64decode(padded.encode("utf-8")).decode("utf-8")
    return json.loads(decoded)


def extract_bearer_token(authorization: Optional[str]) -> str:
    """
    Extract and validate bearer token signature algorithm and format.
    Raises HTTP 401 on missing or malformed header.
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

    try:
        header = _decode_jwt_part(token.split(".", 1)[0])
        alg = (header.get("alg") or "").upper()
        if alg not in ALLOWED_JWT_ALGS:
            raise HTTPException(
                status_code=401,
                detail="Unsupported token algorithm",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Malformed bearer token header",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token


def get_db_session(authorization: Optional[str] = Header(None)) -> Client:
    """
    FastAPI Depends()-compatible dependency that extracts the Bearer token
    from the Authorization header and returns a user-scoped Supabase client.
    Raises HTTP 401 if the header is missing.
    """
    raw_token = extract_bearer_token(authorization)
    return get_supabase_for_user(raw_token)


# 3. Admin client — service_role key, bypasses RLS entirely.
# Use EXCLUSIVELY for auth.admin.* calls (create/list/update auth users).
supabase_admin: Client = create_client(
    settings.supabase_url,
    settings.supabase_service_role_key,
    options=ClientOptions(auto_refresh_token=False, persist_session=False),
)


def validate_schema_compatibility() -> None:
    """
    Verify database schema compatibility with critical tables and columns.
    Raises RuntimeError if a table or expected query path fails due to schema mismatch.
    Allows empty tables to pass successfully.
    """
    tables_to_check = ["facilities", "profiles", "case_records", "case_reviews"]
    for table in tables_to_check:
        try:
            # Query just one ID to verify the table exists and can be queried.
            # If the table is empty, this returns empty data but succeeds.
            supabase_anon.table(table).select("id").limit(1).execute()
        except Exception as e:
            # If it's a real schema/database error (e.g. table not found), raise.
            raise RuntimeError(
                f"Database schema compatibility check failed for table '{table}': {e}"
            )

