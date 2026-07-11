"""
Tests for app/api/routes/cases.py::_check_deterioration_pattern — the
cross-visit deterioration signal that forces needs_review when a patient_key
has had 2+ URGENT/EMERGENCY visits (this one included) within the trailing
window. Calls fn_deterioration_count (backend/supabase/migrations/
phase28_security_definer_fns.sql) through the caller's own RLS-scoped
client via .rpc() — mocked here rather than hit against a real database.

Run: cd backend && pytest tests/test_deterioration_alert.py -v
"""
from types import SimpleNamespace
from unittest.mock import MagicMock

from app.api.routes.cases import _check_deterioration_pattern


def _mock_db_with_rpc_result(has_pattern: bool, visit_count):
    db = MagicMock()
    db.rpc.return_value.execute.return_value = SimpleNamespace(
        data=[{"has_pattern": has_pattern, "visit_count": visit_count}]
    )
    return db


def test_no_patient_key_skips_query_entirely():
    db = MagicMock()

    alert, count = _check_deterioration_pattern(db, None, "EMERGENCY")

    assert (alert, count) == (False, None)
    db.rpc.assert_not_called()


def test_no_prior_visits_and_routine_today_no_alert():
    db = _mock_db_with_rpc_result(False, None)

    alert, count = _check_deterioration_pattern(db, "AB3C-9XYZ", "ROUTINE")

    assert (alert, count) == (False, None)


def test_one_prior_qualifying_visit_plus_qualifying_today_triggers_alert():
    db = _mock_db_with_rpc_result(True, 2)

    alert, count = _check_deterioration_pattern(db, "AB3C-9XYZ", "EMERGENCY")

    assert alert is True
    assert count == 2


def test_two_prior_qualifying_visits_alert_even_if_today_is_routine():
    db = _mock_db_with_rpc_result(True, 2)

    alert, count = _check_deterioration_pattern(db, "AB3C-9XYZ", "ROUTINE")

    assert alert is True
    assert count == 2


def test_single_qualifying_visit_alone_does_not_trigger():
    db = _mock_db_with_rpc_result(False, None)

    alert, count = _check_deterioration_pattern(db, "AB3C-9XYZ", "URGENT")

    assert (alert, count) == (False, None)


def test_calls_fn_deterioration_count_with_patient_key_and_current_tier():
    db = _mock_db_with_rpc_result(False, None)

    _check_deterioration_pattern(db, "AB3C-9XYZ", "ROUTINE")

    db.rpc.assert_called_once_with(
        "fn_deterioration_count",
        {
            "p_patient_key": "AB3C-9XYZ",
            "p_current_triage_level": "ROUTINE",
            "p_window_days": 7,
        },
    )
