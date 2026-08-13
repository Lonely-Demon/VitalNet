"""
Tests for app/services/voice.py — the Groq Whisper / Sarvam AI transcription
service behind POST /api/voice/transcribe. The route itself is behind
slowapi's rate-limit decorator and a real multipart upload (covered by
test_e2e.py against a live server); these tests exercise the plain async
service function directly via asyncio.run (no pytest-asyncio dependency
needed — nothing else in this suite is async).

conftest.py forces SARVAM_API_KEY="" by default, so these tests see a
deterministic "Sarvam not configured" starting point regardless of any real
key in a developer's local .env.local — tests that need Sarvam configured
set settings.sarvam_api_key directly via monkeypatch.

Run: cd backend && pytest tests/test_voice_transcription.py -v
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.core.config import settings
from app.services import voice


def test_transcribe_raises_when_nothing_configured(monkeypatch):
    monkeypatch.setattr(voice, "_groq_client", None)
    monkeypatch.setattr(settings, "sarvam_api_key", "")

    with pytest.raises(voice.TranscriptionUnavailable):
        asyncio.run(voice.transcribe(b"fake-audio-bytes", "clip.webm"))


def test_transcribe_returns_stripped_text_from_groq(monkeypatch):
    mock_client = SimpleNamespace(
        audio=SimpleNamespace(
            transcriptions=SimpleNamespace(
                create=AsyncMock(return_value=SimpleNamespace(text="  fever for three days  "))
            )
        )
    )
    monkeypatch.setattr(voice, "_groq_client", mock_client)

    result = asyncio.run(voice.transcribe(b"fake-audio-bytes", "clip.webm", language="en"))

    assert result == "fever for three days"
    mock_client.audio.transcriptions.create.assert_awaited_once()
    call_kwargs = mock_client.audio.transcriptions.create.call_args.kwargs
    assert call_kwargs["language"] == "en"
    assert call_kwargs["model"] == voice.GROQ_MODEL


def test_transcribe_ignores_unsupported_language(monkeypatch):
    mock_client = SimpleNamespace(
        audio=SimpleNamespace(
            transcriptions=SimpleNamespace(
                create=AsyncMock(return_value=SimpleNamespace(text="hola"))
            )
        )
    )
    monkeypatch.setattr(voice, "_groq_client", mock_client)

    asyncio.run(voice.transcribe(b"fake-audio-bytes", "clip.webm", language="es"))

    call_kwargs = mock_client.audio.transcriptions.create.call_args.kwargs
    assert call_kwargs["language"] is None


def test_groq_is_tried_before_sarvam_when_both_configured(monkeypatch):
    """Groq goes first regardless of language — Sarvam's free tier is a
    fixed signup credit, reserved for requests Groq can't serve."""
    mock_client = SimpleNamespace(
        audio=SimpleNamespace(
            transcriptions=SimpleNamespace(
                create=AsyncMock(return_value=SimpleNamespace(text="groq answered"))
            )
        )
    )
    monkeypatch.setattr(voice, "_groq_client", mock_client)
    monkeypatch.setattr(settings, "sarvam_api_key", "fake-sarvam-key")

    with patch.object(voice, "_transcribe_sarvam", new=AsyncMock()) as mock_sarvam:
        result = asyncio.run(voice.transcribe(b"fake-audio-bytes", "clip.webm", language="hi"))

    assert result == "groq answered"
    mock_sarvam.assert_not_called()


def test_sarvam_used_as_fallback_when_groq_fails(monkeypatch):
    mock_client = SimpleNamespace(
        audio=SimpleNamespace(
            transcriptions=SimpleNamespace(
                create=AsyncMock(side_effect=RuntimeError("upstream error"))
            )
        )
    )
    monkeypatch.setattr(voice, "_groq_client", mock_client)
    monkeypatch.setattr(settings, "sarvam_api_key", "fake-sarvam-key")

    with patch.object(voice, "_transcribe_sarvam", new=AsyncMock(return_value="sarvam answered")) as mock_sarvam:
        result = asyncio.run(voice.transcribe(b"fake-audio-bytes", "clip.webm", language="hi"))

    assert result == "sarvam answered"
    mock_sarvam.assert_awaited_once()


def test_sarvam_not_attempted_when_unconfigured(monkeypatch):
    mock_client = SimpleNamespace(
        audio=SimpleNamespace(
            transcriptions=SimpleNamespace(
                create=AsyncMock(side_effect=RuntimeError("upstream error"))
            )
        )
    )
    monkeypatch.setattr(voice, "_groq_client", mock_client)
    monkeypatch.setattr(settings, "sarvam_api_key", "")

    with patch.object(voice, "_transcribe_sarvam", new=AsyncMock()) as mock_sarvam:
        with pytest.raises(voice.TranscriptionUnavailable):
            asyncio.run(voice.transcribe(b"fake-audio-bytes", "clip.webm", language="hi"))

    mock_sarvam.assert_not_called()


def test_transcribe_wraps_failure_when_all_providers_fail(monkeypatch):
    mock_client = SimpleNamespace(
        audio=SimpleNamespace(
            transcriptions=SimpleNamespace(
                create=AsyncMock(side_effect=RuntimeError("upstream error"))
            )
        )
    )
    monkeypatch.setattr(voice, "_groq_client", mock_client)
    monkeypatch.setattr(settings, "sarvam_api_key", "fake-sarvam-key")

    with patch.object(voice, "_transcribe_sarvam", new=AsyncMock(side_effect=RuntimeError("sarvam down"))):
        with pytest.raises(voice.TranscriptionUnavailable):
            asyncio.run(voice.transcribe(b"fake-audio-bytes", "clip.webm"))


def test_transcribe_sarvam_posts_expected_request(monkeypatch):
    monkeypatch.setattr(settings, "sarvam_api_key", "fake-sarvam-key")

    captured = {}

    class MockResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"transcript": "  bukhar hai  "}

    class MockAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, headers, files, data):
            captured["url"] = url
            captured["headers"] = headers
            captured["data"] = data
            return MockResponse()

    with patch.object(httpx, "AsyncClient", MockAsyncClient):
        result = asyncio.run(voice._transcribe_sarvam(b"fake-audio-bytes", "clip.webm", "hi"))

    assert result == "bukhar hai"
    assert captured["url"] == voice.SARVAM_URL
    assert captured["headers"]["api-subscription-key"] == "fake-sarvam-key"
    assert captured["data"]["model"] == voice.SARVAM_MODEL
    assert captured["data"]["language_code"] == "hi-IN"
