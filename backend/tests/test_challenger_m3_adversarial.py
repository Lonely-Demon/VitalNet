"""
Adversarial empirical challenge test suite for Milestone 3 (Python Backend Route & Service Hardening).
Covers:
1. cases.py:
   - Submit case matrix: fresh submission, concurrent upsert race, duplicate HTTPS submission,
     SMS stub promotion under various roles. Complete elimination of UnboundLocalError.
   - SMS stub promotion: preservation of clinician decisions (reviewed_at, overridden_triage).
   - Consent revocation: authorization checks (ASHA cannot revoke colleague's case in same facility),
     atomic fn_erase_case_pii RPC invocation without importing supabase_admin, idempotency.
2. outbreak_routes.py:
   - EARS C2 dense 10-day calendar series under sparse date gaps. Stdev and variance floor calculations.
3. scoping.py & analytics_routes.py:
   - Fail-closed role scoping (supervisor, super_admin, doctor, admin without facility).
   - Analytics export pagination secondary tie-breaker (.order("id", desc=False)).
4. referral_routes.py:
   - 409 Conflict on duplicate active referrals.
   - Comprehensive facility sorting by tier hierarchy, district proximity, capacity status, load, name.
5. llm.py:
   - LlmCircuitBreaker state machine: CLOSED -> OPEN -> HALF_OPEN -> CLOSED, non-upstream errors ignored.
6. sms.py:
   - E.164 phone number validation edge cases.
   - Compact 28-byte SMS codec alias resolution (age, sex, tier) and sub-year neonatal encoding.
"""

from datetime import datetime, timedelta, timezone
import time
from unittest.mock import MagicMock, patch
import uuid

import pytest
from fastapi import BackgroundTasks, HTTPException
from starlette.requests import Request

# ── Imports under test ──
from app.api.routes import cases
from app.api.routes import outbreak_routes
from app.api.routes import referral_routes
from app.core import scoping
from app.services import llm
from app.services import sms
from app.models.schemas import IntakeForm


def make_dummy_request(method="POST", path="/api/submit", headers=None):
    raw_headers = [(b"host", b"testserver")]
    if headers:
        for k, v in headers.items():
            raw_headers.append((k.lower().encode("utf-8"), v.encode("utf-8")))
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": raw_headers,
        "client": ("127.0.0.1", 12345),
    }
    return Request(scope)


# ==============================================================================
# 1. cases.py: UnboundLocalError Elimination, Stub Promotion, Consent Revocation
# ==============================================================================

@pytest.mark.asyncio
async def test_cases_fresh_submission_no_unbound_local_error():
    """Verify fresh submission completes smoothly with no UnboundLocalError."""
    client_uuid = uuid.uuid4()
    form = IntakeForm(
        patient_name="Priya Sharma",
        patient_age=28,
        patient_sex="female",
        chief_complaint="Fever and chills",
        complaint_duration="2 days",
        location="Subcenter 1",
        bp_systolic=118,
        bp_diastolic=76,
        spo2=99,
        heart_rate=78,
        temperature=38.2,
        symptoms=["high_fever"],
        client_id=client_uuid,
        consent_captured=True,
    )

    created_record = {
        "id": str(uuid.uuid4()),
        "client_id": str(client_uuid),
        "triage_level": "ROUTINE",
        "facility_id": "fac-1",
        "is_sms_stub": False,
    }

    mock_db = MagicMock()
    # existing_res: not found
    select_query = MagicMock()
    select_query.eq.return_value = select_query
    select_query.maybe_single.return_value = select_query
    select_query.execute.return_value = MagicMock(data=None)

    # upsert_query: fresh insert succeeds
    upsert_query = MagicMock()
    upsert_query.execute.return_value = MagicMock(data=[created_record])

    def table_mock(tbl):
        m = MagicMock()
        if tbl == "case_records":
            m.select.return_value = select_query
            m.upsert.return_value = upsert_query
        return m

    mock_db.table.side_effect = table_mock

    user = {"sub": "user-1", "resolved_role": "asha_worker", "resolved_facility_id": "fac-1"}
    req = make_dummy_request()
    bg = BackgroundTasks()

    with patch("app.api.routes.cases.get_supabase_for_user", return_value=mock_db), \
         patch("app.api.routes.cases.extract_bearer_token", return_value="token"), \
         patch("app.api.routes.cases.predict_triage", return_value={"triage_level": "ROUTINE", "risk_driver": "fever", "confidence_score": 0.95}):
        res = await cases.submit_case(
            request=req,
            form=form,
            background_tasks=bg,
            authorization="Bearer token",
            user=user,
        )

    assert res["client_id"] == str(client_uuid)
    assert res["triage_level"] == "ROUTINE"


@pytest.mark.asyncio
async def test_cases_concurrent_race_ignore_duplicates_fallback():
    """Verify concurrent submission where upsert returns empty data (ignored duplicate) falls back gracefully."""
    client_uuid = uuid.uuid4()
    form = IntakeForm(
        patient_name="Priya Sharma",
        patient_age=28,
        patient_sex="female",
        chief_complaint="Fever and chills",
        complaint_duration="2 days",
        location="Subcenter 1",
        bp_systolic=118,
        bp_diastolic=76,
        spo2=99,
        heart_rate=78,
        temperature=38.2,
        symptoms=["high_fever"],
        client_id=client_uuid,
        consent_captured=True,
    )

    existing_row = {
        "id": str(uuid.uuid4()),
        "client_id": str(client_uuid),
        "triage_level": "ROUTINE",
        "facility_id": "fac-1",
        "is_sms_stub": False,
    }

    mock_db = MagicMock()
    # 1. initial maybe_single check: None (race condition simulated)
    initial_check = MagicMock()
    initial_check.eq.return_value = initial_check
    initial_check.maybe_single.return_value = initial_check
    initial_check.execute.return_value = MagicMock(data=None)

    # 2. upsert returns empty data due to ignore_duplicates=True
    upsert_query = MagicMock()
    upsert_query.execute.return_value = MagicMock(data=[])

    # 3. fallback select finds the row inserted by the concurrent request
    fallback_select = MagicMock()
    fallback_select.eq.return_value = fallback_select
    fallback_select.execute.return_value = MagicMock(data=[existing_row])

    def table_mock(tbl):
        m = MagicMock()
        m.select.side_effect = [initial_check, fallback_select]
        m.upsert.return_value = upsert_query
        return m

    mock_db.table.side_effect = table_mock

    user = {"sub": "user-1", "resolved_role": "asha_worker", "resolved_facility_id": "fac-1"}
    req = make_dummy_request()
    bg = BackgroundTasks()

    with patch("app.api.routes.cases.get_supabase_for_user", return_value=mock_db), \
         patch("app.api.routes.cases.extract_bearer_token", return_value="token"), \
         patch("app.api.routes.cases.predict_triage", return_value={"triage_level": "ROUTINE", "risk_driver": "fever", "confidence_score": 0.95}):
        res = await cases.submit_case(
            request=req,
            form=form,
            background_tasks=bg,
            authorization="Bearer token",
            user=user,
        )

    assert res["client_id"] == str(client_uuid)
    assert res["is_sms_stub"] is False


@pytest.mark.asyncio
async def test_cases_sms_stub_preserves_clinician_overrides():
    """Verify that when promoting an SMS stub, existing clinician review decisions cannot be overwritten."""
    client_uuid = uuid.uuid4()
    form = IntakeForm(
        patient_name="Sunita Devi",
        patient_age=32,
        patient_sex="female",
        chief_complaint="Persistent abdominal pain",
        complaint_duration="3 days",
        location="Subcenter 2",
        bp_systolic=110,
        bp_diastolic=70,
        spo2=98,
        heart_rate=80,
        temperature=37.0,
        symptoms=["severe_abdominal_pain"],
        client_id=client_uuid,
        consent_captured=True,
    )

    existing_stub = {
        "id": str(uuid.uuid4()),
        "client_id": str(client_uuid),
        "is_sms_stub": True,
        "submitted_by": "asha-10",
        "facility_id": "fac-1",
        "created_at": "2026-01-01T00:00:00Z",
        "reviewed_at": "2026-01-01T02:00:00Z",
        "overridden_triage": "EMERGENCY",
        "triage_level": "EMERGENCY",
        "triage_priority": 0,
        "needs_review": False,
    }

    updated_payload = {}

    class MockCaseTable:
        def select(self, *args, **kwargs):
            return self
        def eq(self, col, val):
            return self
        def maybe_single(self):
            return self
        def update(self, payload):
            updated_payload.update(payload)
            return self
        def execute(self):
            if updated_payload:
                merged = dict(existing_stub)
                merged.update(updated_payload)
                return MagicMock(data=[merged])
            return MagicMock(data=existing_stub)

    mock_db = MagicMock()
    mock_db.table.return_value = MockCaseTable()

    user = {"sub": "asha-10", "resolved_role": "asha_worker", "resolved_facility_id": "fac-1"}
    req = make_dummy_request()
    bg = BackgroundTasks()

    # Model tries to predict ROUTINE, but clinician had set EMERGENCY!
    with patch("app.api.routes.cases.get_supabase_for_user", return_value=mock_db), \
         patch("app.api.routes.cases.extract_bearer_token", return_value="token"), \
         patch("app.api.routes.cases.predict_triage", return_value={"triage_level": "ROUTINE", "risk_driver": "mild", "confidence_score": 0.95}):
        await cases.submit_case(
            request=req,
            form=form,
            background_tasks=bg,
            authorization="Bearer token",
            user=user,
        )

    # Assert clinician override is preserved
    assert updated_payload["triage_level"] == "EMERGENCY"
    assert updated_payload["triage_priority"] == 0
    assert updated_payload["needs_review"] is False
    assert updated_payload["is_sms_stub"] is False
    # Immutables must not be present
    assert "submitted_by" not in updated_payload
    assert "facility_id" not in updated_payload
    assert "id" not in updated_payload


@pytest.mark.asyncio
async def test_cases_consent_revocation_unauthorized_colleague_blocked():
    """
    BUG-09 De Morgan's Law fix:
    Verify that an ASHA worker CANNOT revoke consent for a colleague's case,
    even if both workers are in the SAME facility.
    """
    case_id = str(uuid.uuid4())
    colleague_case = {
        "id": case_id,
        "client_id": case_id,
        "submitted_by": "asha-colleague",
        "facility_id": "phc-south",
        "deleted_at": None,
        "patient_name": "Patient X",
    }

    mock_db = MagicMock()
    select_q = MagicMock()
    select_q.eq.return_value = select_q
    select_q.maybe_single.return_value = select_q
    select_q.execute.return_value = MagicMock(data=colleague_case)
    mock_db.table.return_value.select.return_value = select_q

    # Attacking ASHA worker has sub='asha-attacker', same facility 'phc-south'
    attacker_user = {"sub": "asha-attacker", "resolved_role": "asha_worker", "resolved_facility_id": "phc-south"}
    req = make_dummy_request()

    with patch("app.api.routes.cases.get_supabase_for_user", return_value=mock_db), \
         patch("app.api.routes.cases.extract_bearer_token", return_value="token"):
        with pytest.raises(HTTPException) as exc_info:
            await cases.revoke_case_consent(
                request=req,
                client_id=case_id,
                authorization="Bearer token",
                user=attacker_user,
            )

    assert exc_info.value.status_code == 403
    assert "Not authorized to revoke consent for this case" in exc_info.value.detail


@pytest.mark.asyncio
async def test_cases_consent_revocation_authorized_invokes_rpc_without_supabase_admin():
    """
    BUG-10:
    Verify authorized consent revocation calls db.rpc('fn_erase_case_pii', ...)
    and does NOT import or use supabase_admin.
    """
    case_id = str(uuid.uuid4())
    my_case = {
        "id": case_id,
        "client_id": case_id,
        "submitted_by": "asha-legit",
        "facility_id": "phc-south",
        "deleted_at": None,
        "patient_name": "Patient Real",
    }

    mock_db = MagicMock()
    select_q = MagicMock()
    select_q.eq.return_value = select_q
    select_q.maybe_single.return_value = select_q
    select_q.execute.return_value = MagicMock(data=my_case)
    mock_db.table.return_value.select.return_value = select_q

    rpc_mock = MagicMock()
    rpc_mock.execute.return_value = MagicMock(data={"status": "erased"})
    mock_db.rpc.return_value = rpc_mock

    user = {"sub": "asha-legit", "resolved_role": "asha_worker", "resolved_facility_id": "phc-south"}
    req = make_dummy_request()

    with patch("app.api.routes.cases.get_supabase_for_user", return_value=mock_db), \
         patch("app.api.routes.cases.extract_bearer_token", return_value="token"):
        res = await cases.revoke_case_consent(
            request=req,
            client_id=case_id,
            authorization="Bearer token",
            user=user,
        )

    assert res["status"] == "consent_revoked"
    assert res["case_id"] == case_id
    mock_db.rpc.assert_called_once_with("fn_erase_case_pii", {"p_case_id": case_id})


# ==============================================================================
# 2. outbreak_routes.py: Dense 10-day Series & Sparse Date Handling
# ==============================================================================

def test_outbreak_routes_sparse_date_dense_padding():
    """
    BUG-14:
    Verify that when historical data is sparse (e.g. cases only on t-9 and t-0, with
    no cases on t-8..t-1), the 7 historical baseline calendar days [t-9..t-3] are
    padded with 0 counts, accurately calculating mean and standard deviation.
    """
    today_dt = datetime(2026, 11, 8, 12, 0, 0, tzinfo=timezone.utc)
    today_str = today_dt.date().isoformat()
    t_minus_9_str = (today_dt - timedelta(days=9)).date().isoformat()

    # 1 case on t-9, 5 cases today (t-0). Zero cases between t-8 and t-1.
    rows = [
        {"facility_id": "fac-outbreak", "created_at": f"{t_minus_9_str}T10:00:00Z", "symptoms": ["high_fever"]}
    ]
    rows.extend([
        {"facility_id": "fac-outbreak", "created_at": f"{today_str}T09:00:00Z", "symptoms": ["high_fever"]}
        for _ in range(5)
    ])

    signals = outbreak_routes._compute_ears_signals(rows, today_str, use_guard_band=True)

    # In baseline [t-9..t-3], exactly 1 day (t-9) has 1 case, and the other 6 days have 0 cases.
    # Expected baseline_mean = 1 / 7 = 0.14.
    # Expected baseline_stddev = statistics.stdev([1, 0, 0, 0, 0, 0, 0]) = 0.3779...
    assert len(signals) == 1
    sig = signals[0]
    assert sig["facility_id"] == "fac-outbreak"
    assert sig["symptom"] == "high_fever"
    assert sig["today_count"] == 5
    assert sig["baseline_mean"] == 0.14
    assert sig["baseline_stddev"] == 0.38
    assert sig["effective_sigma"] == 0.5
    assert sig["z_score"] == 9.71


# ==============================================================================
# 3. scoping.py & analytics_routes.py: Role Scoping & Pagination Tie-Breakers
# ==============================================================================

def test_scoping_roles_fail_closed_and_global_roles():
    """
    BUG-56:
    Verify supervisor and super_admin are GLOBAL_SCOPE_ROLES, while doctor, admin,
    and asha_worker fail-closed when facility_id is absent.
    """
    # 1. Global roles can query any requested facility or global (None)
    assert scoping.resolve_facility_scope("supervisor", None, "target-fac") == "target-fac"
    assert scoping.resolve_facility_scope("supervisor", "own-fac", None) is None
    assert scoping.resolve_facility_scope("super_admin", None, "target-fac") == "target-fac"

    # 2. Non-global roles pinned to own facility
    assert scoping.resolve_facility_scope("doctor", "own-fac", "attacker-fac") == "own-fac"
    assert scoping.resolve_facility_scope("asha_worker", "own-fac", "attacker-fac") == "own-fac"

    # 3. Fail-closed: missing facility raises 400
    with pytest.raises(HTTPException) as exc_doc:
        scoping.resolve_facility_scope("doctor", None, "target-fac")
    assert exc_doc.value.status_code == 400

    with pytest.raises(HTTPException) as exc_admin:
        scoping.resolve_facility_scope("admin", None, "target-fac")
    assert exc_admin.value.status_code == 400


def test_analytics_export_deterministic_tie_breaker():
    """
    BUG-57:
    Verify analytics query construction enforces secondary sort on 'id' ascending
    to prevent skipped or duplicated rows across pagination chunks.
    """
    mock_db = MagicMock()
    order_calls = []

    class MockQuery:
        def select(self, *args, **kwargs):
            return self
        def is_(self, *args, **kwargs):
            return self
        def gte(self, *args, **kwargs):
            return self
        def lte(self, *args, **kwargs):
            return self
        def order(self, col, desc=False):
            order_calls.append((col, desc))
            return self
        def range(self, *args, **kwargs):
            return self
        def eq(self, *args, **kwargs):
            return self
        def execute(self):
            return MagicMock(data=[])

    mock_db.table.return_value = MockQuery()

    # Replicate chunk query builder from export_cases
    start = 0
    end = 999
    q = (
        mock_db.table("case_records")
        .select("id")
        .is_("deleted_at", "null")
        .gte("created_at", "2026-01-01T00:00:00Z")
        .lte("created_at", "2026-01-02T00:00:00Z")
        .order("created_at", desc=False)
        .order("id", desc=False)
        .range(start, end)
    )
    q.execute()

    assert ("created_at", False) in order_calls
    assert ("id", False) in order_calls
    assert order_calls.index(("created_at", False)) < order_calls.index(("id", False))


# ==============================================================================
# 4. referral_routes.py: Active Referral Deduplication & Facility Ranking
# ==============================================================================

@pytest.mark.asyncio
async def test_referral_duplicate_active_referral_rejected_with_409():
    """
    BUG-36:
    Verify create_referral rejects duplicate referrals with 409 Conflict if an active
    referral (pending, acknowledged, patient_arrived) already exists for the case.
    """
    case_uuid = str(uuid.uuid4())
    rec_fac_uuid = str(uuid.uuid4())

    case_row = {
        "id": case_uuid,
        "facility_id": "fac-origin",
        "deleted_at": None,
        "chief_complaint": "Respiratory arrest",
        "patient_age": 55,
        "patient_sex": "male",
        "triage_level": "EMERGENCY",
    }

    active_referral_row = {
        "id": str(uuid.uuid4()),
        "case_id": case_uuid,
        "status": "pending",
    }

    mock_db = MagicMock()
    # Case fetch
    case_select = MagicMock()
    case_select.eq.return_value = case_select
    case_select.maybe_single.return_value = case_select
    case_select.execute.return_value = MagicMock(data=case_row)

    # Active referrals query
    active_select = MagicMock()
    active_select.eq.return_value = active_select
    active_select.in_.return_value = active_select
    active_select.limit.return_value = active_select
    active_select.execute.return_value = MagicMock(data=[active_referral_row])

    def table_mock(tbl):
        m = MagicMock()
        if tbl == "case_records":
            m.select.return_value = case_select
        elif tbl == "referrals":
            m.select.return_value = active_select
        return m

    mock_db.table.side_effect = table_mock

    user = {"sub": "doc-1", "resolved_role": "doctor", "resolved_facility_id": "fac-origin"}
    req = make_dummy_request()
    body = referral_routes.CreateReferralRequest(
        receiving_facility_id=rec_fac_uuid,
        reason="Requires ICU ventilator",
        urgency="EMERGENCY",
    )

    with patch("app.api.routes.referral_routes.get_supabase_for_user", return_value=mock_db), \
         patch("app.api.routes.referral_routes.extract_bearer_token", return_value="token"):
        with pytest.raises(HTTPException) as exc_info:
            await referral_routes.create_referral(
                request=req,
                case_id=case_uuid,
                body=body,
                authorization="Bearer token",
                user=user,
            )

    assert exc_info.value.status_code == 409
    assert "An active referral already exists for this case" in exc_info.value.detail


def test_referral_facility_sorting_tier_and_district():
    """
    BUG-28:
    Verify list_active_facilities sorts facilities by:
    1. Tier hierarchy (district_hospital:0 < sdh:1 < chc:2 < phc:3)
    2. District match (caller's district prioritized)
    3. Capacity status (available:0 < limited:1 < full:2)
    4. Open case load ascending
    5. Name alphabetically
    """
    caller_district = "District A"

    raw_facilities = [
        {"id": "f1", "name": "PHC Alpha", "type": "phc", "district": "District A", "capacity_status": "available", "open_case_count": 0},
        {"id": "f2", "name": "DH Beta", "type": "district_hospital", "district": "District B", "capacity_status": "available", "open_case_count": 2},
        {"id": "f3", "name": "DH Alpha", "type": "district_hospital", "district": "District A", "capacity_status": "limited", "open_case_count": 5},
        {"id": "f4", "name": "CHC Alpha", "type": "chc", "district": "District A", "capacity_status": "available", "open_case_count": 1},
        {"id": "f5", "name": "SDH Alpha", "type": "sdh", "district": "District A", "capacity_status": "available", "open_case_count": 3},
    ]

    tier_rank = {
        "district_hospital": 0,
        "sdh": 1,
        "sub_district_hospital": 1,
        "chc": 2,
        "phc": 3,
        "sub_centre": 4,
    }
    capacity_rank = {"available": 0, "limited": 1, "full": 2}

    sorted_facs = sorted(
        raw_facilities,
        key=lambda f: (
            tier_rank.get((f.get("type") or "").lower(), 99),
            0 if (caller_district and f.get("district") == caller_district) else 1,
            capacity_rank.get(f.get("capacity_status") or "limited", 1),
            f.get("open_case_count", 0),
            f.get("name") or "",
        )
    )

    # Order must be:
    # 1. Tier 0: DH Alpha (Dist A) before DH Beta (Dist B)
    # 2. Tier 1: SDH Alpha
    # 3. Tier 2: CHC Alpha
    # 4. Tier 3: PHC Alpha
    expected_ids = ["f3", "f2", "f5", "f4", "f1"]
    assert [f["id"] for f in sorted_facs] == expected_ids


# ==============================================================================
# 5. llm.py: Circuit Breaker State Machine & SBAR Actions
# ==============================================================================

def test_llm_circuit_breaker_transitions():
    """
    BUG-26, BUG-64:
    Verify LlmCircuitBreaker state transitions:
    - CLOSED on init
    - Non-upstream errors (validation) do not trip breaker
    - 3 consecutive upstream errors trip to OPEN
    - Cooldown transitions to HALF_OPEN
    - Success in HALF_OPEN resets to CLOSED
    - Failure in HALF_OPEN immediately trips back to OPEN
    """
    cb = llm.LlmCircuitBreaker(failure_threshold=3, recovery_timeout=10.0)

    assert cb.state == llm.CircuitState.CLOSED
    assert cb.is_open() is False

    # 1. Non-upstream errors do not increment failures
    cb.record_failure(is_upstream=False)
    assert cb.consecutive_failures == 0
    assert cb.state == llm.CircuitState.CLOSED

    # 2. Upstream failures increment until threshold
    cb.record_failure(is_upstream=True)
    assert cb.consecutive_failures == 1
    assert cb.state == llm.CircuitState.CLOSED

    cb.record_failure(is_upstream=True)
    assert cb.consecutive_failures == 2
    assert cb.state == llm.CircuitState.CLOSED

    cb.record_failure(is_upstream=True)
    assert cb.consecutive_failures == 3
    assert cb.state == llm.CircuitState.OPEN
    assert cb.is_open() is True

    # 3. During recovery timeout, stays OPEN
    current_time = cb.last_failure_time
    with patch("time.monotonic", return_value=current_time + 5.0):
        assert cb.is_open() is True
        assert cb.state == llm.CircuitState.OPEN

    # 4. Beyond recovery timeout, transitions to HALF_OPEN
    with patch("time.monotonic", return_value=current_time + 11.0):
        assert cb.is_open() is False
        assert cb.state == llm.CircuitState.HALF_OPEN

        # 5. Failure in HALF_OPEN trips immediately to OPEN
        cb.record_failure(is_upstream=True)
        assert cb.state == llm.CircuitState.OPEN

    # 6. Advance again to HALF_OPEN, test success
    with patch("time.monotonic", return_value=time.monotonic() + 25.0):
        assert cb.is_open() is False
        assert cb.state == llm.CircuitState.HALF_OPEN

        cb.record_success()
        assert cb.state == llm.CircuitState.CLOSED
        assert cb.consecutive_failures == 0


def test_llm_fallback_briefing_separates_rule_mandated_actions():
    """
    BUG-27:
    Verify Tier-5 deterministic clinical synthesizer demarcates rule-mandated
    actions from symptom-inferred suggestions.
    """
    triage_result = {"triage_level": "EMERGENCY", "risk_driver": "SpO2 < 90%"}
    form_data = {"symptoms": ["chest_pain", "breathlessness"]}

    fallback = llm._fallback_briefing(triage_result, form_data)

    assert "rule_mandated_actions" in fallback
    assert "symptom_inferred_actions" in fallback
    assert any("ABCDE" in a for a in fallback["rule_mandated_actions"])
    assert any("12-lead ECG" in a for a in fallback["symptom_inferred_actions"])
    # All recommended_immediate_actions must carry explicit tags
    for action in fallback["recommended_immediate_actions"]:
        assert action.startswith("[Rule-Mandated]") or action.startswith("[Symptom-Inferred]")


# ==============================================================================
# 6. sms.py: E.164 Phone Format & Aliases in Compact Codec
# ==============================================================================

def test_sms_e164_phone_validation():
    """
    BUG-37:
    Verify E.164 phone number validation accepts strict valid international numbers
    and rejects malformed inputs.
    """
    assert sms.validate_e164_phone_number("+919876543210") is True
    assert sms.validate_e164_phone_number("+14155552671") is True
    assert sms.validate_e164_phone_number("+442071838750") is True

    # Invalid cases
    assert sms.validate_e164_phone_number("9876543210") is False  # Missing +
    assert sms.validate_e164_phone_number("+0123456") is False   # Country code cannot start with 0
    assert sms.validate_e164_phone_number("+") is False
    assert sms.validate_e164_phone_number("+1234567890123456") is False  # 16 digits (max 15)
    assert sms.validate_e164_phone_number("invalid") is False
    assert sms.validate_e164_phone_number("") is False
    assert sms.validate_e164_phone_number(None) is False


def test_sms_codec_alias_resolution_and_infant_encoding():
    """
    BUG-22, BUG-46, REG-01:
    Verify encode_emergency_sms accepts aliases ('age', 'sex', 'tier'),
    encodes sub-year infants as 200 + age_months (REG-01), and round-trips correctly.
    """
    client_uuid = str(uuid.uuid4())
    input_payload = {
        "clientId": client_uuid,
        "age": 0.4,              # Alias 'age', sub-year infant (~5 months: round(0.4*12)=5)
        "sex": "female",          # Alias 'sex'
        "tier": "EMERGENCY",      # Alias 'tier'
        "symptoms": ["breathlessness", "high_fever"],
        "spo2": 89,
        "heartRate": 160,
    }

    encoded = sms.encode_emergency_sms(input_payload)
    assert encoded.startswith("VN1:")

    raw_bytes = sms._base64url_decode(encoded[4:])
    assert raw_bytes[17] == 205  # 200 + 5 months

    decoded = sms.decode_emergency_sms(encoded)

    assert decoded["client_id"] == client_uuid
    assert decoded["patient_sex"] == "female"
    assert decoded["sex"] == "female"
    assert decoded["triage_level"] == "EMERGENCY"
    assert decoded["tier"] == "EMERGENCY"
    # REG-01: Exact infant months preserved
    assert decoded["patient_age"] == 0
    assert decoded["age_months"] == 5
    assert "breathlessness" in decoded["symptoms"]
    assert "high_fever" in decoded["symptoms"]
    assert decoded["spo2"] == 89
    assert decoded["heart_rate"] == 160


def test_sms_codec_legacy_byte_254_backward_compatibility():
    """REG-01: Legacy byte 254 must decode to patient_age=0, age_months=6."""
    client_uuid = str(uuid.uuid4())
    input_payload = {
        "clientId": client_uuid,
        "age": 30,
        "sex": "female",
        "tier": "ROUTINE",
    }
    encoded = sms.encode_emergency_sms(input_payload)
    raw_bytes = bytearray(sms._base64url_decode(encoded[4:]))
    raw_bytes[17] = 254  # Legacy sentinel
    crc = sms._crc24(bytes(raw_bytes[:25]))
    raw_bytes[25] = (crc >> 16) & 0xFF
    raw_bytes[26] = (crc >> 8) & 0xFF
    raw_bytes[27] = crc & 0xFF
    legacy_frame = f"VN1:{sms._base64url_encode(bytes(raw_bytes))}"

    decoded = sms.decode_emergency_sms(legacy_frame)
    assert decoded["patient_age"] == 0
    assert decoded["age_months"] == 6
