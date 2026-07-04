"""
Tests for the DPDP data-subject-request lifecycle
(app/api/routes/dsr_routes.py, docs/COMPLIANCE_DPDP.md). Exercises the
plain helper functions directly — the route handlers themselves are behind
slowapi's rate-limit decorator, which needs a real Request to exercise via
HTTP (same reasoning as test_bulk_user_import.py; full-stack coverage lives
in test_e2e.py against a live server).

Run: cd backend && pytest tests/test_dsr_routes.py -v
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.api.routes.dsr_routes import (
    REDACTED,
    _ERASABLE_CASE_FIELDS,
    _erase_case_row,
    _fetch_case_or_404,
)
from fastapi import HTTPException
import pytest


def _mock_supabase_admin():
    admin = MagicMock()
    return admin


def test_fetch_case_or_404_returns_row(monkeypatch):
    admin = _mock_supabase_admin()
    admin.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = (
        SimpleNamespace(data={"id": "case-1", "patient_name": "Jane"})
    )
    monkeypatch.setattr("app.api.routes.dsr_routes.supabase_admin", admin)

    row = _fetch_case_or_404("case-1")

    assert row == {"id": "case-1", "patient_name": "Jane"}


def test_fetch_case_or_404_raises_when_missing(monkeypatch):
    admin = _mock_supabase_admin()
    admin.table.return_value.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value = (
        SimpleNamespace(data=None)
    )
    monkeypatch.setattr("app.api.routes.dsr_routes.supabase_admin", admin)

    with pytest.raises(HTTPException) as exc:
        _fetch_case_or_404("missing-case")

    assert exc.value.status_code == 404


def test_erase_case_row_redacts_identifying_fields_and_soft_deletes(monkeypatch):
    admin = _mock_supabase_admin()
    monkeypatch.setattr("app.api.routes.dsr_routes.supabase_admin", admin)

    _erase_case_row("case-1", {"deleted_at": None})

    case_update_call = admin.table.return_value.update.call_args_list[0]
    update_body = case_update_call.args[0]

    for field in _ERASABLE_CASE_FIELDS:
        assert update_body[field] == REDACTED
    assert "deleted_at" in update_body  # was None — this call sets it

    # referrals.reason also redacted
    referrals_update_calls = [
        call for call in admin.table.return_value.update.call_args_list
        if call.args[0] == {"reason": REDACTED}
    ]
    assert referrals_update_calls, "referrals.reason must be redacted alongside case_records"


def test_erase_case_row_does_not_overwrite_existing_deleted_at(monkeypatch):
    admin = _mock_supabase_admin()
    monkeypatch.setattr("app.api.routes.dsr_routes.supabase_admin", admin)

    _erase_case_row("case-1", {"deleted_at": "2026-01-01T00:00:00+00:00"})

    case_update_call = admin.table.return_value.update.call_args_list[0]
    update_body = case_update_call.args[0]
    assert "deleted_at" not in update_body


def test_erase_case_row_never_touches_case_outcomes(monkeypatch):
    """
    case_outcomes is immutable-by-design (docs/DECISIONS.md) and carries no
    direct patient identifier — erasure must not write to it.
    """
    admin = _mock_supabase_admin()
    monkeypatch.setattr("app.api.routes.dsr_routes.supabase_admin", admin)

    _erase_case_row("case-1", {"deleted_at": None})

    tables_written = {call.args[0] for call in admin.table.call_args_list}
    assert "case_outcomes" not in tables_written
