"""
Authorization regression & PHC Admin scoping tests.
"""
import os

from fastapi import HTTPException
from fastapi.routing import APIRoute
from jose import jwt as _jwt
from starlette.requests import Request

_fake_key = _jwt.encode({"role": "anon"}, "x", algorithm="HS256")
os.environ.setdefault("SUPABASE_URL", "https://testproj.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", _fake_key)
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", _fake_key)
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-secret-at-least-32-chars-long-aaaaaa")
os.environ.setdefault("GROQ_API_KEY", "test-key")

from app.api.routes import admin_routes, dsr_routes, metrics_routes  # noqa: E402

ADMIN_ROUTE_MODULES = [admin_routes, dsr_routes, metrics_routes]


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


def test_all_admin_routes_require_admin_only():
    routes = [
        r
        for module in ADMIN_ROUTE_MODULES
        for r in module.router.routes
        if isinstance(r, APIRoute)
    ]
    assert routes, "No admin routes discovered — test wiring is wrong"

    failures = []
    for r in routes:
        roles = _enforced_roles(r)
        if roles != {"admin"}:
            failures.append((sorted(r.methods), r.path, sorted(roles) or "NONE"))

    assert not failures, (
        "Admin routes must be guarded by require_role('admin') ONLY. Offenders: "
        f"{failures}"
    )


def test_phc_admin_cannot_create_admin_or_supervisor():
    """Verify PHC Admin is forbidden from creating Admin/Supervisor accounts."""
    req = make_dummy_request("POST", "/api/admin/users")
    user = {"sub": "admin-1", "resolved_role": "admin", "resolved_facility_id": "fac-1"}
    body = admin_routes.CreateUserRequest(
        email="newadmin@test.com",
        password="Password123!@",
        full_name="New Admin",
        role="admin",
        facility_id="fac-1",
    )

    import asyncio
    try:
        asyncio.run(admin_routes.create_user(request=req, body=body, authorization="Bearer token", user=user))
        assert False, "Should have raised 403 Forbidden"
    except HTTPException as exc:
        assert exc.status_code == 403
        assert "only create Doctor and ASHA Worker" in exc.detail


def test_phc_admin_cannot_self_manage():
    """Verify PHC Admin cannot edit or deactivate their own account."""
    req = make_dummy_request("DELETE", "/api/admin/users/admin-1")
    user = {"sub": "admin-1", "resolved_role": "admin", "resolved_facility_id": "fac-1"}

    import asyncio
    try:
        asyncio.run(admin_routes.deactivate_user(request=req, user_id="admin-1", authorization="Bearer token", user=user))
        assert False, "Should have raised 403 Forbidden for self-deactivation"
    except HTTPException as exc:
        assert exc.status_code == 403
        assert "cannot deactivate their own account" in exc.detail


def test_phc_admin_cannot_create_facility():
    """Verify facility creation returns 403 for PHC Admin."""
    req = make_dummy_request("POST", "/api/admin/facilities")
    user = {"sub": "admin-1", "resolved_role": "admin", "resolved_facility_id": "fac-1"}
    body = admin_routes.CreateFacilityRequest(name="New PHC")

    import asyncio
    try:
        asyncio.run(admin_routes.create_facility(request=req, body=body, authorization="Bearer token", user=user))
        assert False, "Should have raised 403 Forbidden"
    except HTTPException as exc:
        assert exc.status_code == 403
        assert "managed by Supervisor Governance" in exc.detail
