"""
Tests for app/services/llm.py::generate_patient_summary — the on-demand,
patient-facing plain-language restatement of an already-decided triage
result. Never regenerates the triage itself; these tests confirm the
fallback path and that a successful call doesn't alter the given tier.

Run: cd backend && pytest tests/test_patient_summary.py -v
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services import llm


def test_falls_back_when_no_groq_client_configured(monkeypatch):
    monkeypatch.setattr(llm, "_groq_client", None)

    result = asyncio.run(llm.generate_patient_summary(
        briefing={"primary_risk_driver": "x", "recommended_immediate_actions": []},
        triage_result={"triage_level": "EMERGENCY", "risk_driver": "x"},
    ))

    assert result["generated"] is False
    assert "urgent" in result["summary"].lower()


def test_falls_back_on_groq_failure(monkeypatch):
    mock_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=AsyncMock(side_effect=RuntimeError("upstream error")))
        )
    )
    monkeypatch.setattr(llm, "_groq_client", mock_client)

    result = asyncio.run(llm.generate_patient_summary(
        briefing={"primary_risk_driver": "x", "recommended_immediate_actions": []},
        triage_result={"triage_level": "ROUTINE", "risk_driver": "x"},
    ))

    assert result["generated"] is False


def test_successful_call_returns_generated_text(monkeypatch):
    mock_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="  Plain language summary.  "))]
    )
    mock_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=AsyncMock(return_value=mock_response))
        )
    )
    monkeypatch.setattr(llm, "_groq_client", mock_client)

    result = asyncio.run(llm.generate_patient_summary(
        briefing={"primary_risk_driver": "fever", "recommended_immediate_actions": ["see a doctor"]},
        triage_result={"triage_level": "URGENT", "risk_driver": "fever"},
        language="hi",
    ))

    assert result == {"summary": "Plain language summary.", "generated": True}
    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    assert "Hindi" in call_kwargs["messages"][1]["content"]


def test_empty_llm_response_falls_back(monkeypatch):
    mock_response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="   "))])
    mock_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=AsyncMock(return_value=mock_response))
        )
    )
    monkeypatch.setattr(llm, "_groq_client", mock_client)

    result = asyncio.run(llm.generate_patient_summary(
        briefing={}, triage_result={"triage_level": "ROUTINE", "risk_driver": ""},
    ))

    assert result["generated"] is False
