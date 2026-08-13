"""
Tests for app/core/scoping.py::resolve_facility_scope — the shared
facility-scope rule used by outbreak_routes.py, supervisor_routes.py, and analytics_routes.py:
`supervisor` is global (system-wide by default, or narrows via a query param);
every other role (admin, doctor, asha_worker) is pinned to their own facility_id and cannot widen that
scope by passing a different one.

Run: cd backend && pytest tests/test_scoping.py -v
"""
import pytest
from fastapi import HTTPException

from app.core.scoping import resolve_facility_scope


def test_supervisor_defaults_to_system_wide():
    assert resolve_facility_scope("supervisor", None, None) is None


def test_supervisor_can_narrow_to_one_facility():
    assert resolve_facility_scope("supervisor", None, "fac-9") == "fac-9"


def test_phc_admin_and_staff_roles_are_scoped_to_own_facility():
    assert resolve_facility_scope("admin", "fac-1", None) == "fac-1"
    assert resolve_facility_scope("doctor", "fac-1", None) == "fac-1"
    assert resolve_facility_scope("asha_worker", "fac-1", None) == "fac-1"


def test_phc_admin_and_staff_roles_cannot_widen_scope_via_query_param():
    assert resolve_facility_scope("admin", "fac-1", "fac-2") == "fac-1"
    assert resolve_facility_scope("doctor", "fac-1", "fac-2") == "fac-1"
    assert resolve_facility_scope("asha_worker", "fac-1", "fac-2") == "fac-1"


def test_phc_admin_without_facility_is_rejected():
    with pytest.raises(HTTPException) as exc:
        resolve_facility_scope("admin", None, None)
    assert exc.value.status_code == 400
    assert "no facility assigned" in exc.value.detail.lower()

