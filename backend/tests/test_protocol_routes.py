"""
Route-level tests for app/api/routes/protocol_routes.py (Phase 41, docs/DECISIONS.md §40).

Verifies:
1. A verified Supervisor without a facility (resolved_role="supervisor", resolved_facility_id=None)
   can ask a general protocol question; the inserted row contains facility_id=None and asked_by=sub.
2. Unassigned local roles (admin, doctor, asha_worker with resolved_facility_id=None) receive HTTP 400
   with "Account has no facility assigned", triggering NO LLM call and NO database insert.
3. Facility-assigned local roles persist only their verified resolved_facility_id.
4. The route strictly enforces verified resolved_role from the database profile, ignoring spoofed
   JWT user_metadata.

Run: cd backend && pytest tests/test_protocol_routes.py -v
"""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.api.routes.protocol_routes import (
    AskProtocolQuestionRequest,
    ask_protocol_question,
)


from jose import jwt as _jwt

_FAKE_TOKEN = _jwt.encode(
    {"sub": "test", "role": "authenticated"}, "secret", algorithm="HS256"
)
_AUTH_HEADER = f"Bearer {_FAKE_TOKEN}"


def _make_dummy_request(method="POST", path="/api/protocol/ask"):
    scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": [
            (b"host", b"testserver"),
            (b"authorization", _AUTH_HEADER.encode()),
        ],
        "client": ("127.0.0.1", 12345),
    }
    return Request(scope)


def test_supervisor_without_facility_asks_and_persists_global_question(monkeypatch):
    user = {
        "sub": "00000000-0000-0000-0000-000000000b01",
        "resolved_role": "supervisor",
        "resolved_facility_id": None,
    }

    mock_llm_result = {
        "answer": "Referral danger signs in pregnancy include severe headache, visual disturbance, and bleeding.",
        "grounded": True,
        "generated": True,
    }
    mock_generate = AsyncMock(return_value=mock_llm_result)
    monkeypatch.setattr(
        "app.api.routes.protocol_routes.generate_protocol_answer", mock_generate
    )

    mock_db = MagicMock()
    mock_insert_table = MagicMock()
    mock_insert_call = MagicMock()

    def fake_insert(row_dict):
        mock_insert_call(row_dict)
        mock_res = MagicMock()
        mock_res.execute.return_value = SimpleNamespace(
            data=[{**row_dict, "id": "00000000-0000-0000-0000-00000000c003"}]
        )
        return mock_res

    mock_insert_table.insert.side_effect = fake_insert
    mock_db.table.return_value = mock_insert_table
    monkeypatch.setattr(
        "app.api.routes.protocol_routes.get_supabase_for_user", lambda token: mock_db
    )

    req = _make_dummy_request()
    body = AskProtocolQuestionRequest(
        question_text="What are the referral danger signs in pregnancy?",
        language="en",
    )

    result = asyncio.run(
        ask_protocol_question(
            request=req,
            body=body,
            authorization=_AUTH_HEADER,
            user=user,
        )
    )

    assert result["id"] == "00000000-0000-0000-0000-00000000c003"
    assert result["asked_by"] == "00000000-0000-0000-0000-000000000b01"
    assert result["facility_id"] is None
    assert result["llm_answer_text"] == mock_llm_result["answer"]
    assert result["llm_grounded"] is True
    assert result["status"] == "answered"

    mock_generate.assert_awaited_once_with(
        "What are the referral danger signs in pregnancy?", "en"
    )
    mock_db.table.assert_called_with("protocol_questions")
    mock_insert_call.assert_called_once()
    inserted_row = mock_insert_call.call_args[0][0]
    assert inserted_row["asked_by"] == "00000000-0000-0000-0000-000000000b01"
    assert inserted_row["facility_id"] is None
    assert (
        inserted_row["question_text"]
        == "What are the referral danger signs in pregnancy?"
    )


@pytest.mark.parametrize("local_role", ["admin", "doctor", "asha_worker"])
def test_unassigned_local_roles_rejected_with_no_llm_and_no_insert(
    monkeypatch, local_role
):
    user = {
        "sub": "00000000-0000-0000-0000-000000000001",
        "resolved_role": local_role,
        "resolved_facility_id": None,
    }

    mock_generate = AsyncMock()
    monkeypatch.setattr(
        "app.api.routes.protocol_routes.generate_protocol_answer", mock_generate
    )

    mock_get_db = MagicMock()
    monkeypatch.setattr(
        "app.api.routes.protocol_routes.get_supabase_for_user", mock_get_db
    )

    req = _make_dummy_request()
    body = AskProtocolQuestionRequest(
        question_text="When is the first ANC visit?",
        language="en",
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            ask_protocol_question(
                request=req,
                body=body,
                authorization=_AUTH_HEADER,
                user=user,
            )
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Account has no facility assigned"

    mock_generate.assert_not_called()
    mock_get_db.assert_not_called()


def test_facility_assigned_local_role_persists_only_resolved_facility(monkeypatch):
    facility_id = "00000000-0000-0000-0000-0000000000f1"
    user = {
        "sub": "00000000-0000-0000-0000-000000000e01",
        "resolved_role": "asha_worker",
        "resolved_facility_id": facility_id,
    }

    mock_llm_result = {
        "answer": "First ANC visit is within the first trimester.",
        "grounded": True,
        "generated": True,
    }
    mock_generate = AsyncMock(return_value=mock_llm_result)
    monkeypatch.setattr(
        "app.api.routes.protocol_routes.generate_protocol_answer", mock_generate
    )

    mock_db = MagicMock()
    mock_insert_table = MagicMock()
    mock_insert_call = MagicMock()

    def fake_insert(row_dict):
        mock_insert_call(row_dict)
        mock_res = MagicMock()
        mock_res.execute.return_value = SimpleNamespace(
            data=[{**row_dict, "id": "00000000-0000-0000-0000-00000000c001"}]
        )
        return mock_res

    mock_insert_table.insert.side_effect = fake_insert
    mock_db.table.return_value = mock_insert_table
    monkeypatch.setattr(
        "app.api.routes.protocol_routes.get_supabase_for_user", lambda token: mock_db
    )

    req = _make_dummy_request()
    body = AskProtocolQuestionRequest(
        question_text="When is the first ANC visit?",
        language="en",
    )

    result = asyncio.run(
        ask_protocol_question(
            request=req,
            body=body,
            authorization=_AUTH_HEADER,
            user=user,
        )
    )

    assert result["facility_id"] == facility_id
    assert result["asked_by"] == "00000000-0000-0000-0000-000000000e01"

    mock_insert_call.assert_called_once()
    inserted_row = mock_insert_call.call_args[0][0]
    assert inserted_row["facility_id"] == facility_id
    assert inserted_row["asked_by"] == "00000000-0000-0000-0000-000000000e01"


def test_endpoint_uses_resolved_role_not_jwt_metadata(monkeypatch):
    user = {
        "sub": "00000000-0000-0000-0000-00000000eeee",
        "resolved_role": "asha_worker",
        "resolved_facility_id": None,
        "user_metadata": {"role": "supervisor"},
    }

    mock_generate = AsyncMock()
    monkeypatch.setattr(
        "app.api.routes.protocol_routes.generate_protocol_answer", mock_generate
    )
    mock_get_db = MagicMock()
    monkeypatch.setattr(
        "app.api.routes.protocol_routes.get_supabase_for_user", mock_get_db
    )

    req = _make_dummy_request()
    body = AskProtocolQuestionRequest(
        question_text="When is the first ANC visit?",
        language="en",
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(
            ask_protocol_question(
                request=req,
                body=body,
                authorization="Bearer fake-test-token",
                user=user,
            )
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == "Account has no facility assigned"

    mock_generate.assert_not_called()
    mock_get_db.assert_not_called()
