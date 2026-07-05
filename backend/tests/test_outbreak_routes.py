"""
Tests for app/api/routes/outbreak_routes.py::_compute_ears_signals — the EARS
C1 aberration-detection aggregation (docs/DECISIONS.md §26): flags a
(facility, symptom) pair when today's count meets MIN_FLOOR and exceeds the
7-day trailing baseline mean + 3 standard deviations.

Run: cd backend && pytest tests/test_outbreak_routes.py -v
"""
from app.api.routes.outbreak_routes import _compute_ears_signals, MIN_FLOOR

TODAY = "2026-07-05"
FAC = "fac-1"


def _row(day, symptom, facility_id=FAC):
    return {"facility_id": facility_id, "symptoms": [symptom], "created_at": f"{day}T10:00:00Z"}


def _day_n_days_before_today(n):
    from datetime import datetime, timedelta
    d = datetime.fromisoformat(TODAY).date() - timedelta(days=n)
    return d.isoformat()


def test_no_rows_returns_no_signals():
    assert _compute_ears_signals([], TODAY) == []


def test_below_floor_never_flags_even_with_zero_baseline():
    # Jump from 0 baseline to 1-2 cases today must never flag (floor = 3).
    rows = [_row(TODAY, "high_fever")] * (MIN_FLOOR - 1)
    assert _compute_ears_signals(rows, TODAY) == []


def test_stable_baseline_matching_today_does_not_flag():
    rows = []
    for n in range(1, 8):
        rows += [_row(_day_n_days_before_today(n), "high_fever")] * 3
    rows += [_row(TODAY, "high_fever")] * 3  # same as baseline — not elevated
    assert _compute_ears_signals(rows, TODAY) == []


def test_sharp_spike_above_baseline_flags():
    rows = []
    for n in range(1, 8):
        rows += [_row(_day_n_days_before_today(n), "high_fever")] * 2  # steady baseline of 2/day
    rows += [_row(TODAY, "high_fever")] * 20  # sharp spike
    signals = _compute_ears_signals(rows, TODAY)
    assert len(signals) == 1
    assert signals[0]["symptom"] == "high_fever"
    assert signals[0]["facility_id"] == FAC
    assert signals[0]["today_count"] == 20


def test_zero_baseline_with_floor_met_flags():
    # No prior cases at all, then a fresh cluster meeting the floor — the
    # exact "new cluster in a tiny population" case §26 requires catching.
    rows = [_row(TODAY, "persistent_vomiting")] * MIN_FLOOR
    signals = _compute_ears_signals(rows, TODAY)
    assert len(signals) == 1
    assert signals[0]["baseline_mean"] == 0
    assert signals[0]["baseline_stddev"] == 0


def test_high_variance_baseline_requires_larger_spike_to_flag():
    # Noisy baseline (0,0,0,0,0,0,10) has a large stddev, so a modest bump
    # today should NOT flag — this is the whole point of using stddev
    # instead of a flat multiple of the mean.
    rows = []
    noisy_counts = [0, 0, 0, 0, 0, 0, 10]
    for n, count in zip(range(1, 8), noisy_counts):
        rows += [_row(_day_n_days_before_today(n), "chest_pain")] * count
    rows += [_row(TODAY, "chest_pain")] * 4
    assert _compute_ears_signals(rows, TODAY) == []


def test_different_facilities_and_symptoms_scored_independently():
    rows = []
    for n in range(1, 8):
        rows += [_row(_day_n_days_before_today(n), "high_fever", facility_id="fac-A")] * 1
        rows += [_row(_day_n_days_before_today(n), "chest_pain", facility_id="fac-B")] * 1
    rows += [_row(TODAY, "high_fever", facility_id="fac-A")] * 15
    rows += [_row(TODAY, "chest_pain", facility_id="fac-B")] * 1  # not elevated, below floor too
    signals = _compute_ears_signals(rows, TODAY)
    assert len(signals) == 1
    assert signals[0]["facility_id"] == "fac-A"
    assert signals[0]["symptom"] == "high_fever"


def test_rows_missing_facility_id_are_skipped():
    rows = [{"facility_id": None, "symptoms": ["high_fever"], "created_at": f"{TODAY}T10:00:00Z"}] * 5
    assert _compute_ears_signals(rows, TODAY) == []


def test_case_with_multiple_symptoms_contributes_to_each():
    rows = [
        {"facility_id": FAC, "symptoms": ["high_fever", "severe_headache"], "created_at": f"{TODAY}T10:00:00Z"}
        for _ in range(MIN_FLOOR)
    ]
    signals = _compute_ears_signals(rows, TODAY)
    symptoms_flagged = {s["symptom"] for s in signals}
    assert symptoms_flagged == {"high_fever", "severe_headache"}
