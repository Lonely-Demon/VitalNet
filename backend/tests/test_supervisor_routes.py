"""
Tests for app/api/routes/supervisor_routes.py — the per-ASHA-worker aggregate
metrics used for supportive supervision (docs/DECISIONS.md §25). Covers the
pure aggregation logic and the facility-scope resolution rule (a supervisor
can never widen their own scope; admin can query system-wide or narrow to
one facility).

Run: cd backend && pytest tests/test_supervisor_routes.py -v
"""
import pytest
from fastapi import HTTPException

from app.api.routes.supervisor_routes import _aggregate_team_metrics, _resolve_scope


# ── _resolve_scope ────────────────────────────────────────────────────────────

def test_supervisor_is_scoped_to_own_facility():
    assert _resolve_scope("supervisor", "fac-1", None) == "fac-1"


def test_supervisor_cannot_widen_scope_via_query_param():
    # Even if a supervisor passes a different facility_id, their own wins.
    assert _resolve_scope("supervisor", "fac-1", "fac-2") == "fac-1"


def test_supervisor_without_facility_is_rejected():
    with pytest.raises(HTTPException) as exc:
        _resolve_scope("supervisor", None, None)
    assert exc.value.status_code == 400


def test_admin_defaults_to_system_wide():
    assert _resolve_scope("admin", None, None) is None


def test_admin_can_narrow_to_one_facility():
    assert _resolve_scope("admin", None, "fac-9") == "fac-9"


# ── _aggregate_team_metrics ───────────────────────────────────────────────────

def _row(uid, tier, needs_review=False, contraindication=False, deterioration=False, name="Asha One"):
    return {
        "submitted_by": uid,
        "triage_level": tier,
        "needs_review": needs_review,
        "contraindication_flags": ["x"] if contraindication else [],
        "deterioration_alert": deterioration,
        "profiles": {"full_name": name},
    }


def test_empty_rows_returns_empty_list():
    assert _aggregate_team_metrics([]) == []


def test_rows_grouped_by_worker():
    rows = [
        _row("u1", "ROUTINE", name="Asha One"),
        _row("u1", "URGENT", name="Asha One"),
        _row("u2", "EMERGENCY", name="Asha Two"),
    ]
    result = _aggregate_team_metrics(rows)
    by_id = {w["user_id"]: w for w in result}

    assert by_id["u1"]["submission_count"] == 2
    assert by_id["u1"]["full_name"] == "Asha One"
    assert by_id["u1"]["tier_distribution"] == {"ROUTINE": 1, "URGENT": 1, "EMERGENCY": 0}
    assert by_id["u2"]["submission_count"] == 1
    assert by_id["u2"]["tier_distribution"] == {"ROUTINE": 0, "URGENT": 0, "EMERGENCY": 1}


def test_rates_computed_correctly():
    rows = [
        _row("u1", "EMERGENCY", needs_review=True, contraindication=True, deterioration=True),
        _row("u1", "ROUTINE"),
        _row("u1", "ROUTINE"),
        _row("u1", "ROUTINE"),
    ]
    result = _aggregate_team_metrics(rows)
    w = result[0]

    assert w["submission_count"] == 4
    assert w["needs_review_count"] == 1
    assert w["needs_review_rate"] == 0.25
    assert w["contraindication_flag_rate"] == 0.25
    assert w["deterioration_alert_rate"] == 0.25


def test_rows_with_no_submitted_by_are_skipped():
    rows = [{"submitted_by": None, "triage_level": "ROUTINE", "profiles": {}}]
    assert _aggregate_team_metrics(rows) == []


def test_unknown_full_name_defaults_to_unknown():
    rows = [{"submitted_by": "u1", "triage_level": "ROUTINE", "profiles": None,
             "needs_review": False, "contraindication_flags": [], "deterioration_alert": False}]
    result = _aggregate_team_metrics(rows)
    assert result[0]["full_name"] == "Unknown"


def test_result_sorted_by_submission_count_descending():
    rows = [
        _row("low", "ROUTINE", name="Low Volume"),
        _row("high", "ROUTINE", name="High Volume"),
        _row("high", "ROUTINE", name="High Volume"),
        _row("high", "ROUTINE", name="High Volume"),
    ]
    result = _aggregate_team_metrics(rows)
    assert [w["user_id"] for w in result] == ["high", "low"]
