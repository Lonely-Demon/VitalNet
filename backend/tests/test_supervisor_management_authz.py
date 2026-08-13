"""
Authorization & Lifecycle Invariant Tests for Supervisor Management Surface.
"""
import os
from unittest.mock import MagicMock, patch
from fastapi import HTTPException
from fastapi.routing import APIRoute
from jose import jwt as _jwt
from starlette.requests import Request

_fake_key = _jwt.encode({"role": "anon"}, "x", algorithm="HS256")
os.environ.setdefault("SUPABASE_URL", "https://testproj.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", _fake_key)
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", _fake_key)
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-secret-at-least-32-chars-long-aaaaaa")

from app.api.routes import supervisor_management_routes  # noqa: E402


def make_dummy_request(method="GET", path="/"):
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": [(b"host", b"testserver")],
        "client": ("127.0.0.1", 12345),
    }
    return Request(scope)


def _enforced_roles(route: APIRoute) -> set:
    roles: set = set()

    def walk(dep):
        call = getattr(dep, "call", None)
        if getattr(call, "__name__", "") == "role_guard" and getattr(call, "__closure__", None):
            for cell in call.__closure__:
                val = cell.cell_contents
                if isinstance(val, tuple):
                    roles.update(val)
        for sub in getattr(dep, "dependencies", []):
            walk(sub)

    walk(route.dependant)
    return roles


def test_all_supervisor_management_routes_require_supervisor():
    routes = [
        r
        for r in supervisor_management_routes.router.routes
        if isinstance(r, APIRoute)
    ]
    assert routes, "No supervisor management routes found"

    failures = []
    for r in routes:
        roles = _enforced_roles(r)
        if roles != {"supervisor"}:
            failures.append((sorted(r.methods), r.path, sorted(roles) or "NONE"))

    assert not failures, f"Supervisor management routes must be supervisor-only: {failures}"


def test_deactivate_facility_with_active_staff_returns_409():
    """Verify lifecycle invariant: Deactivating a PHC with active users raises 409 Conflict."""
    mock_fac = MagicMock()
    mock_fac.data = {'is_active': True}

    mock_active_users = MagicMock()
    mock_active_users.data = [{'id': 'user-1', 'role': 'doctor'}]

    with patch.object(supervisor_management_routes.supabase_admin, 'table') as mock_table:
        def table_side_effect(name):
            m = MagicMock()
            if name == 'facilities':
                m.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = mock_fac
            elif name == 'profiles':
                m.select.return_value.eq.return_value.eq.return_value.execute.return_value = mock_active_users
            return m

        mock_table.side_effect = table_side_effect

        req = make_dummy_request("PATCH", "/api/supervisor/management/facilities/fac-1/toggle")
        user = {"sub": "sup-1", "resolved_role": "supervisor"}

        try:
            import asyncio
            asyncio.run(supervisor_management_routes.toggle_facility(
                request=req, facility_id="fac-1", authorization="Bearer token", user=user
            ))
            assert False, "Should have raised HTTPException 409"
        except HTTPException as exc:
            assert exc.status_code == 409
            assert "active assigned user" in exc.detail


def test_update_admin_on_non_admin_returns_403():
    """Verify target role invariant: Supervisor management update on non-admin returns 403."""
    mock_target = MagicMock()
    mock_target.data = {'id': 'user-2', 'role': 'doctor', 'facility_id': 'fac-1'}

    with patch.object(supervisor_management_routes.supabase_admin, 'table') as mock_table:
        def table_side_effect(name):
            m = MagicMock()
            if name == 'profiles':
                m.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = mock_target
            return m

        mock_table.side_effect = table_side_effect

        req = make_dummy_request("PATCH", "/api/supervisor/management/admins/user-2")
        user = {"sub": "sup-1", "resolved_role": "supervisor"}
        update_body = supervisor_management_routes.UpdateAdminRequest(full_name="Dr. Test")

        try:
            import asyncio
            asyncio.run(supervisor_management_routes.update_admin(
                request=req, user_id="user-2", body=update_body, authorization="Bearer token", user=user
            ))
            assert False, "Should have raised HTTPException 403"
        except HTTPException as exc:
            assert exc.status_code == 403
            assert "operate only on PHC Administrator accounts" in exc.detail
