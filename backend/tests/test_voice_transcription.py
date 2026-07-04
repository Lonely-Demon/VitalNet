"""
Tests for app/services/voice.py — the Groq Whisper transcription service
behind POST /api/voice/transcribe. The route itself is behind slowapi's
rate-limit decorator and a real multipart upload (covered by test_e2e.py
against a live server); these tests exercise the plain async service
function directly via asyncio.run (no pytest-asyncio dependency needed —
nothing else in this suite is async).

Run: cd backend && pytest tests/test_voice_transcription.py -v
"""
import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services import voice


def test_transcribe_raises_when_not_configured(monkeypatch):
    monkeypatch.setattr(voice, "_groq_client", None)

    with pytest.raises(voice.TranscriptionUnavailable):
        asyncio.run(voice.transcribe(b"fake-audio-bytes", "clip.webm"))


def test_transcribe_returns_stripped_text(monkeypatch):
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
    assert call_kwargs["model"] == voice.MODEL


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


def test_transcribe_wraps_groq_failures(monkeypatch):
    mock_client = SimpleNamespace(
        audio=SimpleNamespace(
            transcriptions=SimpleNamespace(
                create=AsyncMock(side_effect=RuntimeError("upstream error"))
            )
        )
    )
    monkeypatch.setattr(voice, "_groq_client", mock_client)

    with pytest.raises(voice.TranscriptionUnavailable):
        asyncio.run(voice.transcribe(b"fake-audio-bytes", "clip.webm"))
