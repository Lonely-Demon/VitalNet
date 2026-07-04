"""
pytest bootstrap: ensure valid-FORMAT (but fake) Supabase credentials exist in
the environment before any test module imports app.core.config / database,
whose module-level Supabase client construction requires a JWT-format key.

Uses setdefault so a real environment (CI, which injects TEST_SUPABASE_* secrets)
always wins — these fakes only fill gaps for local, offline test runs. No
network is made at client construction, so fake creds are sufficient for the
unit/safety/authz tests (test_e2e, which needs a live server + real project, is
not collected by pytest — it has no test_-prefixed functions).
"""
import os

from jose import jwt as _jwt

_fake_key = _jwt.encode({"role": "anon"}, "x", algorithm="HS256")


def _fill(key: str, value: str) -> None:
    # Treat an empty string as unset too — CI may inject a secret env var that is
    # empty when the secret isn't configured, which would otherwise crash client
    # construction. A real, non-empty value always wins.
    if not os.environ.get(key):
        os.environ[key] = value


_fill("SUPABASE_URL", "https://testproj.supabase.co")
_fill("SUPABASE_ANON_KEY", _fake_key)
_fill("SUPABASE_SERVICE_ROLE_KEY", _fake_key)
_fill("SUPABASE_JWT_SECRET", "test-secret-at-least-32-chars-long-aaaaaa")
_fill("GROQ_API_KEY", "test-key")
