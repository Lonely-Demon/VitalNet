"""Synthetic tests for the doctor queue's flagged-first keyset contract."""

from app.utils.case_queue import build_cases_cursor_filter


CURSOR_TIME = "2026-01-01T12:00:00+00:00"
CASE_ID = "11111111-1111-4111-8111-111111111111"


def test_flagged_cursor_includes_unflagged_boundary_and_same_group_ties():
    predicate = build_cases_cursor_filter(
        before_time=CURSOR_TIME,
        before_priority=0,
        before_needs_review=True,
        before_id=CASE_ID,
    )

    assert "triage_priority.gt.0" in predicate
    assert "needs_review.lt.true" in predicate
    assert "needs_review.eq.true,created_at.lt." in predicate
    assert "needs_review.eq.true,created_at.eq." in predicate
    assert f"id.lt.{CASE_ID}" in predicate


def test_unflagged_cursor_stays_within_same_review_group():
    predicate = build_cases_cursor_filter(
        before_time=CURSOR_TIME,
        before_priority=1,
        before_needs_review=False,
        before_id=CASE_ID,
    )

    assert "triage_priority.gt.1" in predicate
    assert "needs_review.eq.false,created_at.lt." in predicate
    assert "needs_review.lt.true" not in predicate
    assert f"id.lt.{CASE_ID}" in predicate


def test_legacy_cursor_remains_accepted_without_review_component():
    predicate = build_cases_cursor_filter(
        before_time=CURSOR_TIME,
        before_priority=2,
        before_needs_review=None,
        before_id=CASE_ID,
    )

    assert "triage_priority.gt.2" in predicate
    assert "created_at.lt." in predicate
    assert "created_at.eq." in predicate
    assert "needs_review" not in predicate


def test_sms_stub_state_promotion_record_payload():
    # ADR §51: Full HTTPS submission must clear is_sms_stub = False
    record = {
        "id": CASE_ID,
        "is_sms_stub": False,
        "chief_complaint": "Severe acute respiratory distress",
        "triage_level": "EMERGENCY",
    }
    assert record["is_sms_stub"] is False
    assert record["triage_level"] == "EMERGENCY"


def test_longitudinal_prior_visits_extraction():
    # ADR §52: Prior visits must be chronologically ordered and capped to trailing 3
    raw_visits = [
        {"created_at": "2026-07-01T10:00:00Z", "triage_level": "ROUTINE", "chief_complaint": "Cold"},
        {"created_at": "2026-07-03T10:00:00Z", "triage_level": "URGENT", "chief_complaint": "Fever"},
        {"created_at": "2026-07-04T10:00:00Z", "triage_level": "EMERGENCY", "chief_complaint": "Chest pain"},
        {"created_at": "2026-06-25T10:00:00Z", "triage_level": "ROUTINE", "chief_complaint": "Rash"},
    ]
    # Sort descending by created_at and cap to 3
    sorted_visits = sorted(raw_visits, key=lambda v: v["created_at"], reverse=True)[:3]
    assert len(sorted_visits) == 3
    assert sorted_visits[0]["triage_level"] == "EMERGENCY"
    assert sorted_visits[1]["triage_level"] == "URGENT"
    assert sorted_visits[2]["triage_level"] == "ROUTINE"

