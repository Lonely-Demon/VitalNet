"""
Server-side voice transcription — closes a gap versus VitalNet's original
design intent: the browser Web Speech API (useVoiceInput.js) was always
meant to be a fast, offline-gated UX-layer convenience, not the accuracy
layer for clinical transcription — browser STT accuracy on Indic medical
speech is insufficient to rely on for a clinical record. This module adds
that accuracy layer with two independent providers, tried in a fixed order:

  1. Groq Whisper (`whisper-large-v3-turbo`) — tried FIRST for every
     language, including hi/ta. Groq has no metered free-credit ceiling
     for this app's volume; Sarvam's free tier is a fixed signup credit, so
     Groq goes first to conserve it rather than spend it on requests Groq
     already handles well.
  2. Sarvam AI (`saaras:v3`) — specialised Indian-language STT, used only
     as the fallback if Groq isn't configured or a request to it fails.

Both are optional and independent: either credential alone is enough for
transcription to work for every supported language. See docs/DECISIONS.md
for the provider-ordering rationale.
"""
import logging

import httpx
from groq import AsyncGroq

from app.core.config import settings

logger = logging.getLogger("vitalnet")

_groq_client: AsyncGroq | None = None
if settings.groq_api_key:
    _groq_client = AsyncGroq(api_key=settings.groq_api_key)

GROQ_MODEL = "whisper-large-v3-turbo"
SARVAM_MODEL = "saaras:v3"
SARVAM_URL = "https://api.sarvam.ai/speech-to-text"

# i18n language codes this app supports (frontend/src/i18n.js) happen to be
# valid ISO-639-1 codes Whisper accepts directly — no translation table.
SUPPORTED_LANGUAGES = {"en", "hi", "ta"}

# ISO-639-1 -> Sarvam's BCP-47 language codes.
_SARVAM_LANGUAGE_CODES = {"en": "en-IN", "hi": "hi-IN", "ta": "ta-IN"}


class TranscriptionUnavailable(Exception):
    """Raised when no transcription provider is configured, or every configured provider fails."""


async def _transcribe_groq(audio_bytes: bytes, filename: str, language: str | None) -> str:
    result = await _groq_client.audio.transcriptions.create(
        model=GROQ_MODEL,
        file=(filename, audio_bytes),
        language=language,
    )
    return (result.text or "").strip()


async def _transcribe_sarvam(audio_bytes: bytes, filename: str, language: str | None) -> str:
    language_code = _SARVAM_LANGUAGE_CODES.get(language or "", "hi-IN")
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            SARVAM_URL,
            headers={"api-subscription-key": settings.sarvam_api_key},
            files={"file": (filename, audio_bytes)},
            data={"model": SARVAM_MODEL, "language_code": language_code},
        )
        response.raise_for_status()
        return (response.json().get("transcript") or "").strip()


def _ordered_providers():
    """
    Groq first (unmetered for this app's volume), Sarvam as the fallback
    only (its free tier is a fixed signup credit — reserved for requests
    Groq can't serve). Only configured providers are included, so an
    unconfigured one is never attempted or counted as a failure.
    """
    providers = []
    if _groq_client:
        providers.append(("groq", _transcribe_groq))
    if settings.sarvam_api_key:
        providers.append(("sarvam", _transcribe_sarvam))
    return providers


async def transcribe(audio_bytes: bytes, filename: str, language: str | None = None) -> str:
    lang = language if language in SUPPORTED_LANGUAGES else None
    providers = _ordered_providers()

    if not providers:
        raise TranscriptionUnavailable("Voice transcription is not configured on this server")

    last_error: Exception | None = None
    for name, fn in providers:
        try:
            return await fn(audio_bytes, filename, lang)
        except Exception as e:
            logger.warning("%s transcription failed: %s", name, e)
            last_error = e

    raise TranscriptionUnavailable("Transcription failed") from last_error
