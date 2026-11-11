"""
Unit tests for the doctor queue's flagged-first keyset contract and cases routing logic.
Covers:
- Flagged-first cursor pagination filter generation (app.utils.case_queue)
- BUG-01, BUG-52, BUG-63: SMS stub promotion state transitions and clinician review preservation in submit_case
- BUG-54, BUG-63: Longitudinal patient trajectory extraction via fn_patient_recent_trajectory RPC
- BUG-23: Inbound SMS gateway stub creation (POST /api/cases/sms-gateway)
- BUG-09, BUG-10: Atomic PII erasure via fn_erase_case_pii in consent revocation
"""
import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import BackgroundTasks, HTTPException
from starlette.requests import Request

from app.api.routes import cases
from app.models.schemas import IntakeForm
from app.utils.case_queue import build_cases_cursor_filter


CURSOR_TIME = "2026-01-01T12:00:00+00:00"
CASE_ID = "11111111-1111-4111-8111-111111111111"


def make_dummy_request(method="POST", path="/api/submit"):
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": [(b"host", b"testserver"), (b"content-type", b"application/json")],
        "client": ("127.0.0.1", 12345),
    }
    return Request(scope)


# ── Keyset Cursor Filter Tests ────────────────────────────────────────────────

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


# ── Cases Routing: SMS Stub Promotion (BUG-01, BUG-52, BUG-63) ───────────────

def test_sms_stub_state_promotion_record_payload():
    """
    BUG-01, BUG-52, BUG-63:
    Exercises submit_case route logic to verify that:
    1. An existing SMS stub is promoted (is_sms_stub becomes False).
    2. Clinician review overrides on the stub are preserved (triage_level, triage_priority, needs_review).
    3. Immutable columns (id, client_id, submitted_by, facility_id) are not updated.
    4. UnboundLocalError (BUG-01) does not occur when promoting existing stub.
    """
    async def _run():
        client_uuid = uuid.UUID(CASE_ID)
        form = IntakeForm(
            patient_name="Ramesh Kumar",
            patient_age=45,
            patient_sex="male",
            chief_complaint="Severe acute respiratory distress and cough",
            complaint_duration="1 day",
            location="Subcenter B",
            bp_systolic=120,
            bp_diastolic=80,
            spo2=88,
            heart_rate=110,
            temperature=38.5,
            symptoms=["chest_pain", "breathlessness"],
            client_id=client_uuid,
            consent_captured=True,
        )

        mock_existing_stub = {
            "id": CASE_ID,
            "client_id": CASE_ID,
            "is_sms_stub": True,
            "submitted_by": "asha-user-1",
            "facility_id": "fac-1",
            "created_at": "2026-01-01T00:00:00Z",
            "reviewed_at": "2026-01-01T01:00:00Z",
            "overridden_triage": "EMERGENCY",
            "triage_level": "EMERGENCY",
            "triage_priority": 0,
            "needs_review": False,
        }

        updated_payload_captured = {}

        class MockCaseTable:
            def select(self, *args, **kwargs):
                return self

            def eq(self, col, val):
                return self

            def maybe_single(self):
                return self

            def update(self, payload):
                updated_payload_captured.update(payload)
                return self

            def execute(self):
                if updated_payload_captured:
                    merged = dict(mock_existing_stub)
                    merged.update(updated_payload_captured)
                    return MagicMock(data=[merged])
                return MagicMock(data=mock_existing_stub)

        mock_db = MagicMock()
        mock_db.table.return_value = MockCaseTable()

        user = {"sub": "asha-user-1", "resolved_role": "asha_worker", "resolved_facility_id": "fac-1"}
        req = make_dummy_request()
        bg = BackgroundTasks()

        with patch("app.api.routes.cases.get_supabase_for_user", return_value=mock_db), \
             patch("app.api.routes.cases.extract_bearer_token", return_value="token-123"), \
             patch("app.api.routes.cases.predict_triage", return_value={
                 "triage_level": "URGENT",
                 "confidence_score": 0.85,
                 "risk_driver": "High Heart Rate",
                 "model_version": "v1.0",
                 "low_confidence": False,
                 "contraindication_flags": [],
             }), \
             patch("app.api.routes.cases.generate_briefing", return_value={
                 "llm_status": "generated",
                 "needs_review": False,
                 "_model_used": "mock-llm",
             }), \
             patch("app.api.routes.cases._check_deterioration_pattern", return_value=(False, None)), \
             patch("app.api.routes.cases.log_phi_access"):

            res = await cases.submit_case(
                request=req,
                form=form,
                background_tasks=bg,
                authorization="Bearer token-123",
                user=user,
            )

            # Assert actual route execution promoted the stub and set is_sms_stub = False
            assert updated_payload_captured.get("is_sms_stub") is False
            # BUG-52: Clinician review preserved
            assert updated_payload_captured.get("triage_level") == "EMERGENCY"
            assert updated_payload_captured.get("triage_priority") == 0
            assert updated_payload_captured.get("needs_review") is False
            # Immutables not in update payload
            assert "id" not in updated_payload_captured
            assert "client_id" not in updated_payload_captured
            assert "submitted_by" not in updated_payload_captured
            assert "facility_id" not in updated_payload_captured
            # Response was returned successfully without UnboundLocalError
            assert res is not None

    asyncio.run(_run())


def test_sms_stub_promotion_unauthorized_user_rejected():
    """BUG-52: An ASHA worker cannot promote an SMS stub submitted by a different user."""
    async def _run():
        client_uuid = uuid.UUID(CASE_ID)
        form = IntakeForm(
            patient_name="Ramesh Kumar",
            patient_age=45,
            patient_sex="male",
            chief_complaint="Severe acute respiratory distress",
            complaint_duration="1 day",
            location="Subcenter B",
            bp_systolic=120,
            bp_diastolic=80,
            client_id=client_uuid,
            consent_captured=True,
        )

        mock_existing_stub = {
            "id": CASE_ID,
            "client_id": CASE_ID,
            "is_sms_stub": True,
            "submitted_by": "different-asha-user",
            "facility_id": "fac-1",
        }

        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.maybe_single.return_value = mock_query
        mock_query.execute.return_value = MagicMock(data=mock_existing_stub)
        mock_db.table.return_value = mock_query

        user = {"sub": "asha-user-1", "resolved_role": "asha_worker", "resolved_facility_id": "fac-1"}
        req = make_dummy_request()
        bg = BackgroundTasks()

        with patch("app.api.routes.cases.get_supabase_for_user", return_value=mock_db), \
             patch("app.api.routes.cases.extract_bearer_token", return_value="token-123"), \
             patch("app.api.routes.cases.predict_triage", return_value={"triage_level": "ROUTINE", "confidence_score": 0.9, "risk_driver": "None"}), \
             patch("app.api.routes.cases.generate_briefing", return_value={"llm_status": "generated"}), \
             patch("app.api.routes.cases._check_deterioration_pattern", return_value=(False, None)), \
             patch("app.api.routes.cases.log_phi_access"):

            with pytest.raises(HTTPException) as exc_info:
                await cases.submit_case(
                    request=req,
                    form=form,
                    background_tasks=bg,
                    authorization="Bearer token-123",
                    user=user,
                )
            assert exc_info.value.status_code == 403
            assert "Not authorized to promote this SMS stub" in exc_info.value.detail

    asyncio.run(_run())


# ── Longitudinal Trajectory: fn_patient_recent_trajectory (BUG-54, BUG-63) ────

def test_longitudinal_prior_visits_extraction():
    """
    BUG-54, BUG-63:
    Exercises submit_case route logic to verify that:
    1. fn_patient_recent_trajectory RPC is invoked with p_patient_key and p_limit=3.
    2. Prior visits are returned and passed into briefing generation.
    """
    async def _run():
        form = IntakeForm(
            patient_name="Sita Devi",
            patient_age=32,
            patient_sex="female",
            chief_complaint="Persistent high fever and headache",
            complaint_duration="3 days",
            location="Subcenter C",
            patient_key="2345-6789",
            consent_captured=True,
        )

        mock_visits = [
            {"created_at": "2026-07-04T10:00:00Z", "triage_level": "EMERGENCY", "chief_complaint": "Chest pain"},
            {"created_at": "2026-07-03T10:00:00Z", "triage_level": "URGENT", "chief_complaint": "Fever"},
            {"created_at": "2026-07-01T10:00:00Z", "triage_level": "ROUTINE", "chief_complaint": "Cold"},
        ]

        rpc_called_params = []

        mock_db = MagicMock()
        def mock_rpc(proc_name, params):
            rpc_called_params.append((proc_name, params))
            rpc_mock = MagicMock()
            rpc_mock.execute.return_value = MagicMock(data=mock_visits)
            return rpc_mock

        mock_db.rpc.side_effect = mock_rpc

        class MockCaseTable:
            def __init__(self):
                self._is_single = False

            def select(self, *args, **kwargs):
                return self

            def eq(self, col, val):
                return self

            def maybe_single(self):
                self._is_single = True
                return self

            def upsert(self, *args, **kwargs):
                self._is_single = False
                return self

            def execute(self):
                if self._is_single:
                    return MagicMock(data=None)
                return MagicMock(data=[{"id": CASE_ID, "patient_key": "2345-6789"}])

        mock_db.table.return_value = MockCaseTable()

        user = {"sub": "asha-user-1", "resolved_role": "asha_worker", "resolved_facility_id": "fac-1"}
        req = make_dummy_request()
        bg = BackgroundTasks()

        briefing_triage_passed = {}
        async def mock_briefing(form_data, triage_result):
            briefing_triage_passed.update(triage_result)
            return {"llm_status": "generated", "needs_review": False, "_model_used": "mock-llm"}

        with patch("app.api.routes.cases.get_supabase_for_user", return_value=mock_db), \
             patch("app.api.routes.cases.extract_bearer_token", return_value="token-123"), \
             patch("app.api.routes.cases.predict_triage", return_value={
                 "triage_level": "URGENT",
                 "confidence_score": 0.88,
                 "risk_driver": "Fever",
                 "model_version": "v1.0",
             }), \
             patch("app.api.routes.cases.generate_briefing", side_effect=mock_briefing), \
             patch("app.api.routes.cases._check_deterioration_pattern", return_value=(False, None)), \
             patch("app.api.routes.cases.log_phi_access"):

            res = await cases.submit_case(
                request=req,
                form=form,
                background_tasks=bg,
                authorization="Bearer token-123",
                user=user,
            )

            # Assert RPC was invoked with p_patient_key and p_limit=3
            assert len(rpc_called_params) == 1
            proc_name, params = rpc_called_params[0]
            assert proc_name == "fn_patient_recent_trajectory"
            assert params == {"p_patient_key": "2345-6789", "p_limit": 3}

            # Assert prior visits were received by briefing
            assert briefing_triage_passed.get("prior_visits") == mock_visits
            assert len(briefing_triage_passed["prior_visits"]) == 3
            assert briefing_triage_passed["prior_visits"][0]["triage_level"] == "EMERGENCY"
            assert res is not None

    asyncio.run(_run())


def test_longitudinal_prior_visits_fallback_on_rpc_error():
    """BUG-54: When fn_patient_recent_trajectory RPC fails, fallback query executes."""
    async def _run():
        form = IntakeForm(
            patient_name="Sita Devi",
            patient_age=32,
            patient_sex="female",
            chief_complaint="Fever and cough",
            complaint_duration="2 days",
            location="Subcenter C",
            patient_key="2345-6789",
            consent_captured=True,
        )

        mock_fallback_visits = [
            {"created_at": "2026-07-04T10:00:00Z", "triage_level": "URGENT", "chief_complaint": "Fever"},
        ]

        fallback_query_executed = False

        class MockCaseTable:
            def __init__(self):
                self._is_single = False
                self._is_limit = False

            def select(self, *args, **kwargs):
                return self

            def eq(self, col, val):
                return self

            def is_(self, col, val):
                return self

            def order(self, col, desc=True):
                return self

            def limit(self, count):
                nonlocal fallback_query_executed
                fallback_query_executed = True
                self._is_limit = True
                return self

            def maybe_single(self):
                self._is_single = True
                return self

            def upsert(self, *args, **kwargs):
                self._is_single = False
                return self

            def execute(self):
                if self._is_limit:
                    return MagicMock(data=mock_fallback_visits)
                if self._is_single:
                    return MagicMock(data=None)
                return MagicMock(data=[{"id": CASE_ID, "patient_key": "2345-6789"}])

        mock_db = MagicMock()
        def mock_failing_rpc(proc_name, params):
            raise RuntimeError("RPC function does not exist")

        mock_db.rpc.side_effect = mock_failing_rpc
        mock_db.table.return_value = MockCaseTable()

        user = {"sub": "asha-user-1", "resolved_role": "asha_worker", "resolved_facility_id": "fac-1"}
        req = make_dummy_request()
        bg = BackgroundTasks()

        briefing_triage_passed = {}
        async def mock_briefing(form_data, triage_result):
            briefing_triage_passed.update(triage_result)
            return {"llm_status": "generated", "needs_review": False, "_model_used": "mock-llm"}

        with patch("app.api.routes.cases.get_supabase_for_user", return_value=mock_db), \
             patch("app.api.routes.cases.extract_bearer_token", return_value="token-123"), \
             patch("app.api.routes.cases.predict_triage", return_value={
                 "triage_level": "ROUTINE",
                 "confidence_score": 0.9,
                 "risk_driver": "None",
                 "model_version": "v1.0",
             }), \
             patch("app.api.routes.cases.generate_briefing", side_effect=mock_briefing), \
             patch("app.api.routes.cases._check_deterioration_pattern", return_value=(False, None)), \
             patch("app.api.routes.cases.log_phi_access"):

            res = await cases.submit_case(
                request=req,
                form=form,
                background_tasks=bg,
                authorization="Bearer token-123",
                user=user,
            )

            assert fallback_query_executed is True
            assert briefing_triage_passed.get("prior_visits") == mock_fallback_visits
            assert res is not None

    asyncio.run(_run())


# ── Inbound SMS Gateway Stub Ingest (BUG-23) ──────────────────────────────────

def test_sms_gateway_inbound_stub_creation():
    """BUG-23: Test inbound SMS ingest route creating an offline case stub."""
    async def _run():
        mock_inserted = []
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.upsert.side_effect = lambda payload, **kwargs: (mock_inserted.append(payload), mock_query)[1]
        mock_query.execute.return_value = MagicMock(data=[{"id": CASE_ID, "is_sms_stub": True}])
        mock_db.table.return_value = mock_query

        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/cases/sms-gateway",
            "headers": [
                (b"host", b"testserver"),
                (b"content-type", b"application/json"),
            ],
            "client": ("127.0.0.1", 12345),
        }
        req = Request(scope)
        req.json = AsyncMock(return_value={
            "sender": "+919876543210",
            "body": "TRIAGE 30 F chest_pain,breathlessness",
            "facility_id": "fac-1",
        })

        with patch("app.api.routes.cases.get_supabase_for_user", return_value=mock_db), \
             patch("app.api.routes.cases.extract_bearer_token", return_value="token-123"), \
             patch("app.api.routes.cases.log_phi_access"):

            res = await cases.ingest_sms_gateway(
                request=req,
                authorization="Bearer token-123",
            )

            assert res.get("status") == "queued"
            assert len(mock_inserted) == 1
            stub = mock_inserted[0]
            assert stub["is_sms_stub"] is True
            assert stub["patient_age"] == 30
            assert stub["patient_sex"] == "female"
            assert stub["facility_id"] == "fac-1"

    asyncio.run(_run())


# ── Consent Revocation: fn_erase_case_pii RPC (BUG-09, BUG-10) ────────────────

def test_revoke_case_consent_invokes_fn_erase_case_pii_rpc():
    """BUG-09, BUG-10: Test revoke_case_consent calls atomic fn_erase_case_pii stored procedure."""
    async def _run():
        mock_case_row = {
            "id": CASE_ID,
            "client_id": CASE_ID,
            "submitted_by": "asha-user-1",
            "facility_id": "fac-1",
            "deleted_at": None,
            "patient_name": "Ramesh",
        }

        rpc_calls = []
        mock_db = MagicMock()
        def mock_rpc(proc_name, params):
            rpc_calls.append((proc_name, params))
            rpc_mock = MagicMock()
            rpc_mock.execute.return_value = MagicMock(data={"status": "erased"})
            return rpc_mock

        mock_db.rpc.side_effect = mock_rpc

        mock_query = MagicMock()
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.maybe_single.return_value = mock_query
        mock_query.execute.return_value = MagicMock(data=mock_case_row)
        mock_db.table.return_value = mock_query

        user = {"sub": "asha-user-1", "resolved_role": "asha_worker", "resolved_facility_id": "fac-1"}
        req = make_dummy_request(method="DELETE", path=f"/api/cases/{CASE_ID}/consent")

        with patch("app.api.routes.cases.get_supabase_for_user", return_value=mock_db), \
             patch("app.api.routes.cases.extract_bearer_token", return_value="token-123"), \
             patch("app.api.routes.cases.log_phi_access"):

            res = await cases.revoke_case_consent(
                request=req,
                client_id=CASE_ID,
                authorization="Bearer token-123",
                user=user,
            )

            assert res.get("status") == "consent_revoked"
            assert len(rpc_calls) == 1
            proc_name, params = rpc_calls[0]
            assert proc_name == "fn_erase_case_pii"
            assert params == {"p_case_id": CASE_ID}

    asyncio.run(_run())
