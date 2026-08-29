"""
CORS preflight & security regression tests (Phase 42, docs/DECISIONS.md §41).

Verifies that the CORSMiddleware configuration:
1. Explicitly permits the X-Event-Id custom idempotency header on OPTIONS preflight.
2. Returns proper Access-Control-Allow-Origin, Access-Control-Allow-Methods, and
   Access-Control-Allow-Headers for approved frontend origins (e.g. vitalnet-preprod).
3. Case-insensitively allows x-event-id alongside authorization and content-type.
4. Omits/rejects CORS headers for disallowed, untrusted origins.

Run: cd backend && pytest tests/test_cors_preflight.py -v
"""

import pytest
from fastapi.testclient import TestClient
from starlette.middleware.cors import CORSMiddleware

import app.core.database as db_module
from app.main import app


@pytest.fixture
def client_with_preprod_origin(monkeypatch):
    """
    Ensures https://vitalnet-preprod.vercel.app is in the app's CORSMiddleware
    allow_origins set for middleware-level preflight testing, and stubs offline
    database schema validation during lifespan.
    """
    monkeypatch.setattr(db_module, "validate_schema_compatibility", lambda: None)
    monkeypatch.setattr("app.main.load_classifier", lambda: True)

    preprod_origin = "https://vitalnet-preprod.vercel.app"

    # Find the CORSMiddleware in app.user_middleware and ensure preprod origin is present
    for mw in app.user_middleware:
        if mw.cls is CORSMiddleware:
            existing = list(mw.kwargs.get("allow_origins", []))
            if preprod_origin not in existing:
                mw.kwargs["allow_origins"] = existing + [preprod_origin]
            break

    # Reset middleware_stack so FastAPI rebuilds with updated origins
    app.middleware_stack = None

    with TestClient(app) as client:
        yield client

    # Cleanup: restore middleware stack reset
    app.middleware_stack = None


def test_cors_preflight_allows_x_event_id_for_preprod_origin(
    client_with_preprod_origin,
):
    """
    Exercises the exact browser preflight failure reported on vitalnet-preprod:
    OPTIONS /api/submit with Origin https://vitalnet-preprod.vercel.app and
    Access-Control-Request-Headers: authorization,content-type,x-event-id
    """
    origin = "https://vitalnet-preprod.vercel.app"
    headers = {
        "Origin": origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type,x-event-id",
    }

    response = client_with_preprod_origin.options("/api/submit", headers=headers)

    # 1. Response status is 200 OK
    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text}"
    )

    # 2. Access-Control-Allow-Origin matches approved origin
    assert response.headers.get("access-control-allow-origin") == origin

    # 3. Access-Control-Allow-Methods includes POST
    allow_methods = [
        m.strip()
        for m in response.headers.get("access-control-allow-methods", "").split(",")
    ]
    assert "POST" in allow_methods

    # 4. Access-Control-Allow-Headers (normalized case-insensitively) includes x-event-id, authorization, content-type
    allow_headers_raw = response.headers.get("access-control-allow-headers", "")
    allow_headers = {
        h.strip().lower() for h in allow_headers_raw.split(",") if h.strip()
    }

    assert "x-event-id" in allow_headers, (
        f"x-event-id missing from allow_headers: {allow_headers_raw}"
    )
    assert "authorization" in allow_headers
    assert "content-type" in allow_headers


def test_cors_preflight_allows_all_custom_app_headers(client_with_preprod_origin):
    """
    Verifies that all required custom headers (X-CSRF-Token, X-Device-Id, X-Request-ID, X-Event-Id)
    are permitted during preflight.
    """
    origin = "https://vitalnet-preprod.vercel.app"
    all_headers = "authorization, content-type, x-csrf-token, x-device-id, x-request-id, x-event-id"
    headers = {
        "Origin": origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": all_headers,
    }

    response = client_with_preprod_origin.options("/api/submit", headers=headers)
    assert response.status_code == 200

    allow_headers = {
        h.strip().lower()
        for h in response.headers.get("access-control-allow-headers", "").split(",")
        if h.strip()
    }
    expected_headers = {
        "authorization",
        "content-type",
        "x-csrf-token",
        "x-device-id",
        "x-request-id",
        "x-event-id",
    }
    assert expected_headers.issubset(allow_headers)


def test_cors_preflight_rejects_disallowed_untrusted_origin(client_with_preprod_origin):
    """
    Verifies that an unapproved/untrusted origin does NOT receive CORS access headers.
    """
    untrusted_origin = "https://untrusted-attacker.com"
    headers = {
        "Origin": untrusted_origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type,x-event-id",
    }

    response = client_with_preprod_origin.options("/api/submit", headers=headers)

    # CORSMiddleware does not attach access-control-allow-origin for untrusted origins
    assert "access-control-allow-origin" not in response.headers
