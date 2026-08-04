"""
Tests for app/core/scoping.py::resolve_facility_scope — the shared
facility-scope rule used by supervisor_routes.py and outbreak_routes.py:
`admin` is global (system-wide by default, or narrows via a query param);
every other role is pinned to their own facility_id and cannot widen that
scope by passing a different one.

Run: cd backend && pytest tests/test_scoping.py -v
"""
import pytest
from fastapi import HTTPException

from app.core.scoping import resolve_facility_scope


def test_non_admin_role_is_scoped_to_own_facility():
    assert resolve_facility_scope("supervisor", "fac-1", None) == "fac-1"
    assert resolve_facility_scope("doctor", "fac-1", None) == "fac-1"


def test_non_admin_role_cannot_widen_scope_via_query_param():
    assert resolve_facility_scope("supervisor", "fac-1", "fac-2") == "fac-1"
    assert resolve_facility_scope("doctor", "fac-1", "fac-2") == "fac-1"


def test_non_admin_role_without_facility_is_rejected():
    with pytest.raises(HTTPException) as exc:
        resolve_facility_scope("supervisor", None, None)
    assert exc.value.status_code == 400


def test_admin_defaults_to_system_wide():
    assert resolve_facility_scope("admin", None, None) is None


def test_admin_can_narrow_to_one_facility():
    assert resolve_facility_scope("admin", None, "fac-9") == "fac-9"
