"""
Regression and parity test suite for VitalNet Cases Routes (backend/app/api/routes/cases.py).
Covers:
- R2 & REG-05: SMS gateway stub NOT NULL fields, on_conflict ignore_duplicates, and PostgreSQL check constraint triage_priority mapping (0, 1, 2)
- R3 & REG-03: Case consent revocation non-UUID 400 rejection (guarding 22P02), admin facility-scoping, and error propagation on RPC failure
- R5 & REG-06: Follow-up query filtering (follow_up_completed_at is null) and followup completion endpoint
"""
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.api.routes import cases
from app.api.routes.cases import (
    SYSTEM_FACILITY_UUID,
    SYSTEM_SUBMITTER_UUID,
    _triage_priority_from_tier,
)


CASE_ID = "11111111-1111-4111-8111-111111111111"
OTHER_CASE_ID = "22222222-2222-4222-8222-222222222222"


def make_dummy_request(method="POST", path="/api/submit"):
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": [(b"host", b"testserver"), (b"content-type", b"application/json")],
        "client": ("127.0.0.1", 12345),
    }
    return Request(scope)


# ── R2 & REG-05: SMS Gateway Stub Hardening & Priority Mapping ──────────────────


def test_triage_priority_from_tier_mapping_alignment():
    """Verify triage_priority mapping strictly conforms to case_records_triage_priority_map_check."""
    # EMERGENCY = 0, URGENT = 1, ROUTINE = 2
    assert _triage_priority_from_tier("EMERGENCY") == 0
    assert _triage_priority_from_tier("URGENT") == 1
    assert _triage_priority_from_tier("ROUTINE") == 2
    assert _triage_priority_from_tier(None) == 2


def test_sms_gateway_populates_all_not_null_stub_columns_and_priority():
    """REG-02, REG-05: SMS stub must populate all NOT NULL columns and priority 0/1/2."""
    async def _run():
        mock_inserted = []
        upsert_kwargs_captured = []
        mock_db = MagicMock()
        mock_query = MagicMock()

        def mock_upsert(payload, **kwargs):
            mock_inserted.append(payload)
            upsert_kwargs_captured.append(kwargs)
            return mock_query

        mock_query.upsert.side_effect = mock_upsert
        mock_query.execute.return_value = MagicMock(data=[{"id": CASE_ID, "is_sms_stub": True}])
        mock_db.table.return_value = mock_query

        req = make_dummy_request(method="POST", path="/api/cases/sms-gateway")
        req.json = AsyncMock(return_value={
            "sender": "+919876543210",
            "body": "TRIAGE 30 F chest_pain,breathlessness",
        })

        with patch("app.api.routes.cases.get_supabase_for_user", return_value=mock_db), \
             patch("app.api.routes.cases.extract_bearer_token", return_value="token-123"), \
             patch("app.api.routes.cases._verify_token", return_value={"sub": SYSTEM_SUBMITTER_UUID}):

            res = await cases.ingest_sms_gateway(
                request=req,
                authorization="Bearer token-123",
            )

            assert res.get("status") == "queued"
            assert len(mock_inserted) == 1
            stub = mock_inserted[0]

            # Assert all NOT NULL schema columns are properly populated
            assert stub["submitted_by"] == SYSTEM_SUBMITTER_UUID
            assert stub["facility_id"] == SYSTEM_FACILITY_UUID
            assert stub["patient_name"] == "Emergency Patient (SMS)"
            assert stub["patient_location"] == "Community (SMS Intake)"
            assert stub["complaint_duration"] == "acute (<24h)"
            assert stub["is_sms_stub"] is True
            assert stub["triage_priority"] == 2  # ROUTINE maps to 2
            assert stub["triage_level"] == "ROUTINE"

            # Assert upsert options include on_conflict and ignore_duplicates
            assert len(upsert_kwargs_captured) == 1
            kw = upsert_kwargs_captured[0]
            assert kw.get("on_conflict") == "client_id"
            assert kw.get("ignore_duplicates") is True

    asyncio.run(_run())


def test_sms_gateway_vn1_frame_emergency_priority_mapping():
    """REG-05: VN1 emergency frame stub sets triage_priority to 0 for EMERGENCY."""
    async def _run():
        mock_inserted = []
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.upsert.side_effect = lambda payload, **kwargs: (mock_inserted.append(payload), mock_query)[1]
        mock_query.execute.return_value = MagicMock(data=[{"id": CASE_ID, "is_sms_stub": True}])
        mock_db.table.return_value = mock_query

        # Plain text VN1 request
        scope = {
            "type": "http",
            "method": "POST",
            "path": "/api/cases/sms-gateway",
            "headers": [(b"host", b"testserver"), (b"content-type", b"text/plain")],
            "client": ("127.0.0.1", 12345),
        }
        req = Request(scope)
        req.body = AsyncMock(return_value=b"VN1:dummyframe")

        mock_decoded = {
            "client_id": CASE_ID,
            "patient_age": 45,
            "patient_sex": "male",
            "symptoms": ["chest_pain", "breathlessness"],
            "triage_level": "EMERGENCY",
            "tier": "EMERGENCY",
            "bp_systolic": 180,
            "bp_diastolic": 110,
        }

        with patch("app.api.routes.cases.get_supabase_for_user", return_value=mock_db), \
             patch("app.api.routes.cases.extract_bearer_token", return_value="token-123"), \
             patch("app.api.routes.cases._verify_token", return_value={"sub": SYSTEM_SUBMITTER_UUID}), \
             patch("app.services.sms.decode_emergency_sms", return_value=mock_decoded):

            res = await cases.ingest_sms_gateway(
                request=req,
                authorization="Bearer token-123",
            )

            assert res.get("status") == "queued"
            assert len(mock_inserted) == 1
            stub = mock_inserted[0]
            assert stub["triage_level"] == "EMERGENCY"
            assert stub["triage_priority"] == 0  # EMERGENCY maps to 0
            assert stub["patient_name"] == "Emergency Patient (SMS)"
            assert stub["complaint_duration"] == "acute (<24h)"

    asyncio.run(_run())


# ── R3 & REG-03: Case Consent Revocation Hardening ──────────────────────────────


def test_revoke_case_consent_rejects_non_uuid_with_400():
    """REG-03: Non-UUID client_id must raise HTTP 400 to prevent PostgreSQL 22P02 error."""
    async def _run():
        req = make_dummy_request(method="POST", path="/api/security/cases/not-a-uuid/revoke-consent")
        user = {"sub": "admin-1", "resolved_role": "admin", "resolved_facility_id": "fac-1"}

        with pytest.raises(HTTPException) as exc_info:
            await cases.revoke_case_consent(
                request=req,
                client_id="22P02-malformed-id",
                authorization="Bearer token",
                user=user,
            )

        assert exc_info.value.status_code == 400
        assert "Invalid case ID format; UUID required" in str(exc_info.value.detail)

    asyncio.run(_run())


def test_revoke_case_consent_enforces_admin_facility_scoping():
    """REG-03: PHC admin cannot revoke consent for case outside their facility."""
    async def _run():
        mock_case_row = {
            "id": CASE_ID,
            "client_id": CASE_ID,
            "submitted_by": "asha-1",
            "facility_id": "fac-2",  # Belongs to fac-2
            "deleted_at": None,
            "patient_name": "Sita",
        }
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.maybe_single.return_value = mock_query
        mock_query.execute.return_value = MagicMock(data=mock_case_row)
        mock_db.table.return_value = mock_query

        req = make_dummy_request(method="POST", path=f"/api/security/cases/{CASE_ID}/revoke-consent")
        # Admin assigned to fac-1 (not fac-2)
        admin_user = {"sub": "admin-1", "resolved_role": "admin", "resolved_facility_id": "fac-1"}

        with patch("app.api.routes.cases.get_supabase_for_user", return_value=mock_db), \
             patch("app.api.routes.cases.extract_bearer_token", return_value="token"):

            with pytest.raises(HTTPException) as exc_info:
                await cases.revoke_case_consent(
                    request=req,
                    client_id=CASE_ID,
                    authorization="Bearer token",
                    user=admin_user,
                )

            assert exc_info.value.status_code == 403
            assert "Not authorized to access cases outside your facility" in str(exc_info.value.detail)

    asyncio.run(_run())


def test_revoke_case_consent_super_admin_exempt_from_facility_scoping():
    """REG-03: super_admin is exempt from facility scoping."""
    async def _run():
        mock_case_row = {
            "id": CASE_ID,
            "client_id": CASE_ID,
            "submitted_by": "asha-1",
            "facility_id": "fac-2",
            "deleted_at": None,
            "patient_name": "Sita",
        }
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.maybe_single.return_value = mock_query
        mock_query.execute.return_value = MagicMock(data=mock_case_row)
        mock_db.table.return_value = mock_query

        rpc_mock = MagicMock()
        rpc_mock.execute.return_value = MagicMock(data={"status": "erased"})
        mock_db.rpc.return_value = rpc_mock

        req = make_dummy_request(method="POST", path=f"/api/security/cases/{CASE_ID}/revoke-consent")
        super_admin_user = {"sub": "sa-1", "resolved_role": "super_admin", "resolved_facility_id": None}

        with patch("app.api.routes.cases.get_supabase_for_user", return_value=mock_db), \
             patch("app.api.routes.cases.extract_bearer_token", return_value="token"), \
             patch("app.api.routes.cases.log_phi_access"):

            res = await cases.revoke_case_consent(
                request=req,
                client_id=CASE_ID,
                authorization="Bearer token",
                user=super_admin_user,
            )

            assert res.get("status") == "consent_revoked"

    asyncio.run(_run())


def test_revoke_case_consent_propagates_rpc_failure():
    """REG-03: fn_erase_case_pii RPC exception must be propagated as HTTP 500, not swallowed."""
    async def _run():
        mock_case_row = {
            "id": CASE_ID,
            "client_id": CASE_ID,
            "submitted_by": "doctor-1",
            "facility_id": "fac-1",
            "deleted_at": None,
            "patient_name": "Ramesh",
        }
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.maybe_single.return_value = mock_query
        mock_query.execute.return_value = MagicMock(data=mock_case_row)
        mock_db.table.return_value = mock_query

        # Simulate RPC failure
        mock_db.rpc.side_effect = RuntimeError("PostgreSQL RPC execution failed: connection timeout")

        req = make_dummy_request(method="POST", path=f"/api/security/cases/{CASE_ID}/revoke-consent")
        doc_user = {"sub": "doc-1", "resolved_role": "doctor", "resolved_facility_id": "fac-1"}

        with patch("app.api.routes.cases.get_supabase_for_user", return_value=mock_db), \
             patch("app.api.routes.cases.extract_bearer_token", return_value="token"):

            with pytest.raises(HTTPException) as exc_info:
                await cases.revoke_case_consent(
                    request=req,
                    client_id=CASE_ID,
                    authorization="Bearer token",
                    user=doc_user,
                )

            assert exc_info.value.status_code == 500
            assert "DSR erasure failed: PostgreSQL RPC execution failed" in str(exc_info.value.detail)

    asyncio.run(_run())


# ── R5 & REG-06: Follow-up Queries & Completion ─────────────────────────────────


def test_get_due_followups_filters_by_completed_at_null():
    """REG-06: GET /api/cases/followups/due excludes completed follow-ups."""
    async def _run():
        filter_calls = []
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.select.return_value = mock_query

        def mock_eq(col, val):
            filter_calls.append(("eq", col, val))
            return mock_query

        def mock_is_(col, val):
            filter_calls.append(("is_", col, val))
            return mock_query

        mock_query.eq.side_effect = mock_eq
        mock_query.is_.side_effect = mock_is_
        mock_query.order.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.execute.return_value = MagicMock(data=[
            {"id": CASE_ID, "follow_up_required": True, "follow_up_due_at": "2026-11-12T00:00:00Z"}
        ])
        mock_db.table.return_value = mock_query

        req = make_dummy_request(method="GET", path="/api/cases/followups/due")
        user = {"sub": "doc-1", "resolved_role": "doctor", "resolved_facility_id": "fac-1"}

        with patch("app.api.routes.cases.get_supabase_for_user", return_value=mock_db), \
             patch("app.api.routes.cases.extract_bearer_token", return_value="token"), \
             patch("app.api.routes.cases.log_phi_access"):

            res = await cases.get_due_followups(
                request=req,
                authorization="Bearer token",
                user=user,
            )

            assert res.get("count") == 1
            assert len(res.get("cases")) == 1

            # Assert follow_up_completed_at IS NULL filter is applied
            assert ("is_", "follow_up_completed_at", "null") in filter_calls
            assert ("is_", "deleted_at", "null") in filter_calls
            assert ("eq", "follow_up_required", True) in filter_calls
            assert ("eq", "facility_id", "fac-1") in filter_calls

    asyncio.run(_run())


def test_complete_case_followup_rejects_non_uuid():
    """REG-06: POST /api/cases/{case_id}/followup-complete rejects invalid UUID."""
    async def _run():
        req = make_dummy_request(method="POST", path="/api/cases/invalid-uuid/followup-complete")
        user = {"sub": "doc-1", "resolved_role": "doctor", "resolved_facility_id": "fac-1"}

        with pytest.raises(HTTPException) as exc_info:
            await cases.complete_case_followup(
                request=req,
                case_id="invalid-uuid-format",
                authorization="Bearer token",
                user=user,
            )

        assert exc_info.value.status_code == 400
        assert "Invalid case ID format; UUID required" in str(exc_info.value.detail)

    asyncio.run(_run())


def test_complete_case_followup_facility_scoping_and_update():
    """REG-06: Completing follow-up enforces facility-scoping and marks follow_up_completed_at."""
    async def _run():
        mock_case_row = {
            "id": CASE_ID,
            "facility_id": "fac-1",
            "submitted_by": "asha-1",
            "deleted_at": None,
        }
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_query.select.return_value = mock_query
        mock_query.eq.return_value = mock_query
        mock_query.maybe_single.return_value = mock_query
        mock_query.execute.return_value = MagicMock(data=mock_case_row)

        updated_payloads = []
        def mock_update(payload):
            updated_payloads.append(payload)
            update_query = MagicMock()
            update_query.eq.return_value = update_query
            update_query.is_.return_value = update_query
            update_query.execute.return_value = MagicMock(data=[{"id": CASE_ID, **payload}])
            return update_query

        mock_query.update.side_effect = mock_update
        mock_db.table.return_value = mock_query

        req = make_dummy_request(method="POST", path=f"/api/cases/{CASE_ID}/followup-complete")

        # 1. Doctor from wrong facility fac-2 gets 403
        wrong_doc = {"sub": "doc-2", "resolved_role": "doctor", "resolved_facility_id": "fac-2"}
        with patch("app.api.routes.cases.get_supabase_for_user", return_value=mock_db), \
             patch("app.api.routes.cases.extract_bearer_token", return_value="token"):

            with pytest.raises(HTTPException) as exc_info:
                await cases.complete_case_followup(
                    request=req,
                    case_id=CASE_ID,
                    authorization="Bearer token",
                    user=wrong_doc,
                )
            assert exc_info.value.status_code == 403

        # 2. Doctor from matching facility fac-1 succeeds
        right_doc = {"sub": "doc-1", "resolved_role": "doctor", "resolved_facility_id": "fac-1"}
        with patch("app.api.routes.cases.get_supabase_for_user", return_value=mock_db), \
             patch("app.api.routes.cases.extract_bearer_token", return_value="token"), \
             patch("app.api.routes.cases.log_phi_access"):

            res = await cases.complete_case_followup(
                request=req,
                case_id=CASE_ID,
                authorization="Bearer token",
                user=right_doc,
            )

            assert res.get("status") == "followup_completed"
            assert res.get("case_id") == CASE_ID
            assert res.get("follow_up_completed_at") is not None
            assert len(updated_payloads) == 1
            assert updated_payloads[0]["follow_up_required"] is False
            assert "follow_up_completed_at" in updated_payloads[0]

    asyncio.run(_run())
