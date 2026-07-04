import os
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    supabase_url: str
    supabase_anon_key: str
    supabase_jwt_secret: str                 # HS256 secret — used for local JWT verification
    supabase_service_role_key: str           # Used ONLY for admin/global operations (bypasses RLS)
    groq_api_key: str
    gemini_api_key: str = ""   # Optional — fallback tier 3 and 4; app starts without it
    frontend_url: str = ""
    # Comma-separated extra CORS origins (e.g. additional staging domains),
    # combined with frontend_url and — in development — localhost. Lets ops
    # add an allowed origin via env without a code change.
    cors_allowed_origins: str = ""

    environment: Literal["development", "staging", "production"] = "development"

    # ── Auth (hybrid verification) ────────────────────────────────────────────
    # When True, verify the JWT signature/exp/aud LOCALLY (HS256) on the request
    # hot path instead of a Supabase network round-trip per request. If local
    # verification fails (e.g. an ES256/asymmetric-key project whose token this
    # secret can't verify), the code falls back to a network get_user() check,
    # so this is safe to leave on regardless of the project's signing algorithm.
    jwt_local_verification: bool = True
    # How often (seconds) to re-check a user's is_active / role / facility_id
    # against the database, per user. Bounds how long a deactivated user's
    # still-valid token keeps working, or a changed role/facility assignment
    # stays stale: at most this many seconds, instead of the full token TTL
    # (~1h). Set low for tighter revocation, higher for less DB load.
    revocation_recheck_seconds: int = 300

    # ── Rate limiting ─────────────────────────────────────────────────────────
    # slowapi storage backend. Empty = in-memory (per-process, resets on restart,
    # NOT shared across horizontally-scaled instances). Set to a shared store
    # (e.g. "redis://host:6379") in production multi-instance deployments so the
    # limit is enforced globally. See CODEBASE_MAP.md.
    rate_limit_storage_uri: str = ""

    # ── API docs ───────────────────────────────────────────────────────────────
    # Swagger/ReDoc/OpenAPI JSON expose the full request/response schema and
    # every route. Off by default; enable only in dev/staging.
    api_docs_enabled: bool = False

    # ── CSRF / device guard ────────────────────────────────────────────────────
    # State-changing requests must carry this header plus X-Device-Id. Neither
    # value is a secret — the protection comes from the CORS preflight that a
    # custom header forces, which only an allowed origin can pass, not from the
    # token being unguessable.
    csrf_token: str = "vitalnet-spa"

    # ── Web Push (FEATURES_ROADMAP §1.4) ──────────────────────────────────────
    # Generate a keypair once with `vapid --gen` (from the py-vapid package,
    # a pywebpush dependency) or `npx web-push generate-vapid-keys`. Empty
    # values disable push entirely — submit_case's push fan-out no-ops and
    # /api/push/subscribe returns 503, so this is safe to leave unset.
    vapid_public_key: str = ""
    vapid_private_key: str = ""
    vapid_subject: str = "mailto:admin@example.com"

    # ── Data retention (docs/COMPLIANCE_DPDP.md) ──────────────────────────────
    # POST /api/admin/cases/purge-expired anonymises (not hard-deletes)
    # case_records older than this window, applying the same redaction as
    # POST /api/admin/cases/{id}/erase. Not wired to an automatic cron here —
    # an operator or external scheduler hits the endpoint, same pattern as
    # the existing re-alert job (push_routes.py). 0 disables the endpoint.
    data_retention_days: int = 0

    @property
    def allowed_origins(self) -> list[str]:
        origins: list[str] = []
        if self.environment == "development":
            origins.extend([
                "http://localhost:5173", "http://127.0.0.1:5173",
                "http://localhost:4173", "http://127.0.0.1:4173",
            ])
        if self.frontend_url:
            origins.append(self.frontend_url.rstrip("/"))
        if self.cors_allowed_origins:
            origins.extend(
                origin.strip().rstrip("/")
                for origin in self.cors_allowed_origins.split(",")
                if origin.strip()
            )
        return list(dict.fromkeys(origins))

    model_config = SettingsConfigDict(
        env_file=None if os.environ.get("ENVIRONMENT", "development").lower() == "production" else ".env.local",
        extra="ignore",
    )


settings = Settings()
