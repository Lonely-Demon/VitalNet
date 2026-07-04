from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    supabase_url: str
    supabase_anon_key: str
    supabase_jwt_secret: str                 # HS256 secret — used for local JWT verification
    supabase_service_role_key: str           # Used ONLY for admin/global operations (bypasses RLS)
    groq_api_key: str
    gemini_api_key: str = ""   # Optional — fallback tier 3 and 4; app starts without it
    frontend_url: str = ""

    # ── Auth (hybrid verification) ────────────────────────────────────────────
    # When True, verify the JWT signature/exp/aud LOCALLY (HS256) on the request
    # hot path instead of a Supabase network round-trip per request. If local
    # verification fails (e.g. an ES256/asymmetric-key project whose token this
    # secret can't verify), the code falls back to a network get_user() check,
    # so this is safe to leave on regardless of the project's signing algorithm.
    jwt_local_verification: bool = True
    # How often (seconds) to re-check a user's is_active / revocation status
    # against the database, per user. Bounds how long a deactivated user's still
    # -valid token keeps working: at most this many seconds, instead of the full
    # token TTL (~1h). Set low for tighter revocation, higher for less DB load.
    revocation_recheck_seconds: int = 300

    # ── Rate limiting ─────────────────────────────────────────────────────────
    # slowapi storage backend. Empty = in-memory (per-process, resets on restart,
    # NOT shared across horizontally-scaled instances). Set to a shared store
    # (e.g. "redis://host:6379") in production multi-instance deployments so the
    # limit is enforced globally. See CODEBASE_MAP.md.
    rate_limit_storage_uri: str = ""

    # ── Security headers ──────────────────────────────────────────────────────
    # Enable Strict-Transport-Security. Leave off for local HTTP dev; turn on in
    # production (HTTPS) via env so browsers pin HTTPS for this API.
    security_headers_hsts: bool = False

    model_config = SettingsConfigDict(env_file='.env.local', extra='ignore')


settings = Settings()
