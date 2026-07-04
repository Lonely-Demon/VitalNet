"""
Tests for _provision_user (app/api/routes/admin_routes.py) — the shared
create-user logic behind both POST /api/admin/users and the bulk import
endpoint (FEATURES_ROADMAP §1b.4). Bulk import's whole value proposition is
that one bad row (weak password, missing facility, a failed profile write)
never takes down the rest of the batch — these tests pin that contract at
the unit level, since the route itself is behind slowapi's rate-limit
decorator which needs a real Request to exercise via HTTP (covered instead by
test_e2e.py against a live server).

Run: cd backend && pytest tests/test_bulk_user_import.py -v
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.api.routes.admin_routes import CreateUserRequest, _provision_user


def _valid_row(**overrides):
    defaults = dict(
        email="asha1@example.com",
        password="Str0ng!Passw0rd",
        full_name="Asha One",
        role="asha_worker",
        facility_id="11111111-1111-1111-1111-111111111111",
        asha_id="A-001",
    )
    defaults.update(overrides)
    return CreateUserRequest(**defaults)


def _mock_supabase_admin(create_user_result=None, profile_update_data=None):
    admin = MagicMock()
    admin.auth.admin.create_user.return_value = create_user_result or SimpleNamespace(
        user=SimpleNamespace(id="22222222-2222-2222-2222-222222222222")
    )
    admin.table.return_value.update.return_value.eq.return_value.execute.return_value = SimpleNamespace(
        data=profile_update_data if profile_update_data is not None else [{"id": "22222222-2222-2222-2222-222222222222"}]
    )
    return admin


def test_provision_user_success(monkeypatch):
    admin = _mock_supabase_admin()
    monkeypatch.setattr("app.api.routes.admin_routes.supabase_admin", admin)

    result = _provision_user(_valid_row())

    assert result == {"id": "22222222-2222-2222-2222-222222222222", "email": "asha1@example.com"}
    admin.auth.admin.delete_user.assert_not_called()


def test_provision_user_rejects_weak_password(monkeypatch):
    # 12+ chars (passes the pydantic-level min_length) but no digit/symbol —
    # exercises _validate_password's complexity check, which the schema
    # itself doesn't enforce.
    admin = _mock_supabase_admin()
    monkeypatch.setattr("app.api.routes.admin_routes.supabase_admin", admin)

    with pytest.raises(HTTPException) as exc:
        _provision_user(_valid_row(password="alllowercaseletters"))

    assert exc.value.status_code == 400
    admin.auth.admin.create_user.assert_not_called()


def test_provision_user_requires_facility_for_asha_worker(monkeypatch):
    admin = _mock_supabase_admin()
    monkeypatch.setattr("app.api.routes.admin_routes.supabase_admin", admin)

    with pytest.raises(HTTPException) as exc:
        _provision_user(_valid_row(facility_id=None))

    assert exc.value.status_code == 400
    assert "facility_id" in exc.value.detail


def test_provision_user_rolls_back_orphaned_auth_user_on_profile_failure(monkeypatch):
    # Profile update returns no rows (e.g. the DB trigger hadn't fired yet) —
    # _provision_user must roll back the just-created auth user rather than
    # leave an account with no usable profile.
    admin = _mock_supabase_admin(profile_update_data=[])
    monkeypatch.setattr("app.api.routes.admin_routes.supabase_admin", admin)

    with pytest.raises(HTTPException) as exc:
        _provision_user(_valid_row())

    assert exc.value.status_code == 500
    admin.auth.admin.delete_user.assert_called_once_with("22222222-2222-2222-2222-222222222222")


def test_one_bad_row_does_not_affect_others_in_a_batch(monkeypatch):
    """
    Mirrors bulk_create_users' per-row try/except: a batch of 3 rows where
    the middle row has a weak password must still create rows 1 and 3.
    """
    admin = _mock_supabase_admin()
    monkeypatch.setattr("app.api.routes.admin_routes.supabase_admin", admin)

    rows = [
        _valid_row(email="a@example.com"),
        _valid_row(email="b@example.com", password="alllowercaseletters"),
        _valid_row(email="c@example.com"),
    ]

    results = []
    for row in rows:
        try:
            created = _provision_user(row)
            results.append({"email": row.email, "status": "created", "id": created["id"]})
        except HTTPException as e:
            results.append({"email": row.email, "status": "error", "detail": e.detail})

    statuses = {r["email"]: r["status"] for r in results}
    assert statuses == {
        "a@example.com": "created",
        "b@example.com": "error",
        "c@example.com": "created",
    }
