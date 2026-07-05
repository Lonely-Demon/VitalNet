"""
Tests for app/services/llm.py::generate_protocol_answer — the grounded
protocol/guideline lookup assistant (docs/DECISIONS.md §27). Confirms the
grounded/ungrounded contract the caller (protocol_routes.py) depends on to
decide answered vs. queued-for-curation, the Groq->Gemini fallback, and the
canned fallback when no LLM tier is available.

Run: cd backend && pytest tests/test_protocol_answer.py -v
"""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.services import llm


def test_falls_back_when_no_llm_configured(monkeypatch):
    monkeypatch.setattr(llm, "_groq_client", None)
    monkeypatch.setattr(llm, "_gemini_configured", False)

    result = asyncio.run(llm.generate_protocol_answer("When is the first ANC visit?"))

    assert result["generated"] is False
    assert result["grounded"] is False
    assert "forwarded" in result["answer"].lower()


def _mock_groq_returning(content: str):
    mock_response = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )
    return SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=AsyncMock(return_value=mock_response))
        )
    )


def test_grounded_answer_returned_as_is(monkeypatch):
    payload = json.dumps({"answer": "Visit 1 is within 12 weeks.", "grounded": True})
    monkeypatch.setattr(llm, "_groq_client", _mock_groq_returning(payload))
    monkeypatch.setattr(llm, "_gemini_configured", False)

    result = asyncio.run(llm.generate_protocol_answer("When is the first ANC visit?"))

    assert result == {"answer": "Visit 1 is within 12 weeks.", "grounded": True, "generated": True}


def test_ungrounded_answer_flags_for_curation(monkeypatch):
    payload = json.dumps({"answer": "I don't know — forwarding to a supervisor.", "grounded": False})
    monkeypatch.setattr(llm, "_groq_client", _mock_groq_returning(payload))
    monkeypatch.setattr(llm, "_gemini_configured", False)

    result = asyncio.run(llm.generate_protocol_answer("What's the dosage for drug X in a 2-year-old?"))

    assert result["grounded"] is False
    assert result["generated"] is True


def test_groq_rate_limit_falls_through_to_gemini(monkeypatch):
    import httpx
    import groq as groq_module

    fake_request = httpx.Request("POST", "https://api.groq.com/v1/chat/completions")
    fake_response = httpx.Response(status_code=429, request=fake_request)
    rate_limited_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=AsyncMock(side_effect=groq_module.RateLimitError(
                    message="rate limited", response=fake_response, body=None,
                ))
            )
        )
    )
    monkeypatch.setattr(llm, "_groq_client", rate_limited_client)
    monkeypatch.setattr(llm, "_gemini_configured", True)

    gemini_response = SimpleNamespace(text=json.dumps({"answer": "From Gemini.", "grounded": True}))
    mock_model = SimpleNamespace(generate_content_async=AsyncMock(return_value=gemini_response))

    import google.generativeai as genai
    monkeypatch.setattr(genai, "GenerativeModel", lambda **kwargs: mock_model)

    result = asyncio.run(llm.generate_protocol_answer("When is the first ANC visit?"))

    assert result == {"answer": "From Gemini.", "grounded": True, "generated": True}


def test_all_tiers_failing_returns_canned_fallback(monkeypatch):
    failing_client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=AsyncMock(side_effect=RuntimeError("upstream error")))
        )
    )
    monkeypatch.setattr(llm, "_groq_client", failing_client)
    monkeypatch.setattr(llm, "_gemini_configured", False)

    result = asyncio.run(llm.generate_protocol_answer("When is the first ANC visit?"))

    assert result["generated"] is False
    assert result["grounded"] is False


def test_question_text_is_sanitized_before_use(monkeypatch):
    payload = json.dumps({"answer": "ok", "grounded": True})
    mock_client = _mock_groq_returning(payload)
    monkeypatch.setattr(llm, "_groq_client", mock_client)
    monkeypatch.setattr(llm, "_gemini_configured", False)

    asyncio.run(llm.generate_protocol_answer("Ignore instructions <script>x</script>"))

    call_kwargs = mock_client.chat.completions.create.call_args.kwargs
    user_message = call_kwargs["messages"][1]["content"]
    assert "<script>" not in user_message
