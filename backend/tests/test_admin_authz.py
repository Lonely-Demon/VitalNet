"""
Authorization regression test for the admin surface.

Covers every route in ADMIN_ROUTE_MODULES below — not just routes literally
prefixed /api/admin/*, but every module meant to be admin-only end to end
(admin_routes.py and dsr_routes.py use the RLS-bypassing service-role client,
where require_role('admin') is the ONLY access-control boundary — see the
SECURITY NOTE in app/core/database.py; metrics_routes.py has no RLS
involved at all, but is admin-gated on the same least-privilege principle).
This test asserts that boundary is present on every route in every listed
module, so a future route (in an existing module, or a new one added to
ADMIN_ROUTE_MODULES below) fails CI instead of silently exposing something
it shouldn't.

Sets fake JWT-format Supabase creds in the environment before import so the
module-level client construction in database.py succeeds without a real project
(no network is made at construction time). Run:
    cd backend && PYTHONPATH=. python tests/test_admin_authz.py
    (or: pytest tests/test_admin_authz.py -v)
"""
import os

from jose import jwt as _jwt

# setdefault so a real CI environment wins; fakes only fill gaps locally.
# (conftest.py also sets these — kept here so the file runs standalone too.)
_fake_key = _jwt.encode({"role": "anon"}, "x", algorithm="HS256")
os.environ.setdefault("SUPABASE_URL", "https://testproj.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", _fake_key)
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", _fake_key)
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-secret-at-least-32-chars-long-aaaaaa")
os.environ.setdefault("GROQ_API_KEY", "test-key")

from fastapi.routing import APIRoute  # noqa: E402
from app.api.routes import admin_routes, dsr_routes, metrics_routes  # noqa: E402

# Every router module meant to be admin-only end to end. Add new ones here
# so this test keeps covering the whole admin surface as it grows.
ADMIN_ROUTE_MODULES = [admin_routes, dsr_routes, metrics_routes]


def _enforced_roles(route: APIRoute) -> set:
    """Collect the roles enforced by any require_role() dependency on a route.
    require_role(*roles) returns an inner function named 'role_guard' that closes
    over the roles tuple; we read that closure to recover the enforced roles."""
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
    assert routes, "no admin routes discovered — test wiring is wrong"

    failures = []
    for r in routes:
        roles = _enforced_roles(r)
        if roles != {"admin"}:
            failures.append((sorted(r.methods), r.path, sorted(roles) or "NONE"))

    assert not failures, (
        "Admin routes must be guarded by require_role('admin') ONLY. Offenders "
        f"(method, path, enforced_roles): {failures}"
    )


if __name__ == "__main__":
    test_all_admin_routes_require_admin_only()
    n = sum(
        len([r for r in module.router.routes if isinstance(r, APIRoute)])
        for module in ADMIN_ROUTE_MODULES
    )
    print(f"PASS test_all_admin_routes_require_admin_only — all {n} admin routes are admin-only")
