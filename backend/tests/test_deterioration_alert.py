"""
Tests for app/api/routes/cases.py::_check_deterioration_pattern — the
cross-visit deterioration signal that forces needs_review when a patient_key
has had 2+ URGENT/EMERGENCY visits (this one included) within the trailing
window. Uses supabase_admin for a count-only aggregate query (docs/DECISIONS.md
§22), mocked here rather than hit against a real database.

Run: cd backend && pytest tests/test_deterioration_alert.py -v
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.api.routes.cases import _check_deterioration_pattern


def _mock_admin_with_count(count):
    admin = MagicMock()
    chain = admin.table.return_value.select.return_value.eq.return_value.gte.return_value.in_.return_value.is_.return_value
    chain.execute.return_value = SimpleNamespace(count=count, data=[{"id": "x"}] * count)
    return admin


def test_no_patient_key_skips_query_entirely(monkeypatch):
    admin = MagicMock()
    monkeypatch.setattr("app.api.routes.cases.supabase_admin", admin)

    alert, count = _check_deterioration_pattern(None, "EMERGENCY")

    assert (alert, count) == (False, None)
    admin.table.assert_not_called()


def test_no_prior_visits_and_routine_today_no_alert(monkeypatch):
    admin = _mock_admin_with_count(0)
    monkeypatch.setattr("app.api.routes.cases.supabase_admin", admin)

    alert, count = _check_deterioration_pattern("AB3C-9XYZ", "ROUTINE")

    assert (alert, count) == (False, None)


def test_one_prior_qualifying_visit_plus_qualifying_today_triggers_alert(monkeypatch):
    admin = _mock_admin_with_count(1)
    monkeypatch.setattr("app.api.routes.cases.supabase_admin", admin)

    alert, count = _check_deterioration_pattern("AB3C-9XYZ", "EMERGENCY")

    assert alert is True
    assert count == 2


def test_two_prior_qualifying_visits_alert_even_if_today_is_routine(monkeypatch):
    admin = _mock_admin_with_count(2)
    monkeypatch.setattr("app.api.routes.cases.supabase_admin", admin)

    alert, count = _check_deterioration_pattern("AB3C-9XYZ", "ROUTINE")

    assert alert is True
    assert count == 2


def test_single_qualifying_visit_alone_does_not_trigger(monkeypatch):
    admin = _mock_admin_with_count(0)
    monkeypatch.setattr("app.api.routes.cases.supabase_admin", admin)

    alert, count = _check_deterioration_pattern("AB3C-9XYZ", "URGENT")

    assert (alert, count) == (False, None)


def test_query_filters_by_patient_key_and_qualifying_tiers(monkeypatch):
    admin = _mock_admin_with_count(0)
    monkeypatch.setattr("app.api.routes.cases.supabase_admin", admin)

    _check_deterioration_pattern("AB3C-9XYZ", "ROUTINE")

    admin.table.assert_called_once_with("case_records")
    eq_call = admin.table.return_value.select.return_value.eq.call_args
    assert eq_call.args == ("patient_key", "AB3C-9XYZ")
    in_call = admin.table.return_value.select.return_value.eq.return_value.gte.return_value.in_.call_args
    assert in_call.args[1] == ("URGENT", "EMERGENCY")
