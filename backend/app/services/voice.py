"""
Server-side voice transcription (Groq Whisper) — closes a gap versus
VitalNet's original design intent: the browser Web Speech API
(useVoiceInput.js) was always meant to be a fast, offline-gated UX-layer
convenience, not the accuracy layer for clinical transcription — browser
STT accuracy on Indic medical speech is insufficient to rely on for a
clinical record. This module adds that accuracy layer using the
already-configured GROQ_API_KEY (the same key app/services/llm.py uses for
briefing generation) — no new credential is required.
"""
import logging

from groq import AsyncGroq

from app.core.config import settings

logger = logging.getLogger("vitalnet")

_groq_client: AsyncGroq | None = None
if settings.groq_api_key:
    _groq_client = AsyncGroq(api_key=settings.groq_api_key)

MODEL = "whisper-large-v3"

# i18n language codes this app supports (frontend/src/i18n.js) happen to be
# valid ISO-639-1 codes Whisper accepts directly — no translation table.
SUPPORTED_LANGUAGES = {"en", "hi", "ta"}


class TranscriptionUnavailable(Exception):
    """Raised when GROQ_API_KEY isn't configured, or the Groq call fails."""


async def transcribe(audio_bytes: bytes, filename: str, language: str | None = None) -> str:
    if not _groq_client:
        raise TranscriptionUnavailable("Voice transcription is not configured on this server")

    lang = language if language in SUPPORTED_LANGUAGES else None

    try:
        result = await _groq_client.audio.transcriptions.create(
            model=MODEL,
            file=(filename, audio_bytes),
            language=lang,
        )
    except Exception as e:
        logger.warning("Groq transcription failed: %s", e)
        raise TranscriptionUnavailable("Transcription failed") from e

    return (result.text or "").strip()
