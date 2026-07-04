"""
Voice transcription endpoint (app/services/voice.py). Online-only by
design — the frontend (useVoiceInput.js) falls back to the browser's own
Web Speech API when offline, matching every other network-dependent
VitalNet feature. No PHI is persisted by this endpoint: the audio is
transcribed and discarded, never written to storage or the database.
"""
import logging

from fastapi import APIRouter, Depends, File, Header, HTTPException, Request, UploadFile

from app.core.auth import require_role
from app.services.voice import TranscriptionUnavailable, transcribe
from app.api.routes.cases import limiter

logger = logging.getLogger("vitalnet")

router = APIRouter(prefix="/api/voice", tags=["voice"])

MAX_AUDIO_BYTES = 10 * 1024 * 1024  # 10 MB — several minutes of compressed speech
ALLOWED_CONTENT_TYPES = {
    "audio/webm", "audio/wav", "audio/wave", "audio/x-wav", "audio/mp4",
    "audio/mpeg", "audio/ogg", "audio/m4a", "audio/x-m4a",
}


@router.post("/transcribe")
@limiter.limit("20/minute")
async def transcribe_audio(
    request: Request,
    file: UploadFile = File(...),
    language: str | None = None,
    authorization: str = Header(None),
    user: dict = Depends(require_role("asha_worker", "doctor", "admin")),
):
    # Browsers report MediaRecorder blobs with a codec suffix (e.g.
    # "audio/webm;codecs=opus") — compare on the base MIME type only.
    base_content_type = (file.content_type or "").split(";")[0].strip()
    if base_content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail=f"Unsupported audio content type: {file.content_type}")

    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")
    if len(audio_bytes) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio file too large (max 10 MB)")

    try:
        transcript = await transcribe(audio_bytes, file.filename or "audio.webm", language)
    except TranscriptionUnavailable as e:
        raise HTTPException(status_code=503, detail=str(e))

    return {"transcript": transcript}
