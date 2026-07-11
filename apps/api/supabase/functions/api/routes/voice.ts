// Ported from app/api/routes/voice_routes.py. Online-only by design — the
// frontend falls back to the browser's own Web Speech API when offline,
// matching every other network-dependent VitalNet feature. No PHI is
// persisted by this endpoint: the audio is transcribed and discarded,
// never written to storage or the database.
import { Hono } from "hono";
import { requireRole } from "../_shared/auth.ts";
import { rateLimit } from "../_shared/rateLimit.ts";
import { HttpError } from "../_shared/database.ts";
import { transcribe, TranscriptionUnavailable } from "../_shared/voice.ts";
import type { AppEnv } from "../_shared/types.ts";

export const voice = new Hono<AppEnv>();

const MAX_AUDIO_BYTES = 10 * 1024 * 1024; // 10 MB — several minutes of compressed speech
const ALLOWED_CONTENT_TYPES = new Set([
  "audio/webm",
  "audio/wav",
  "audio/wave",
  "audio/x-wav",
  "audio/mp4",
  "audio/mpeg",
  "audio/ogg",
  "audio/m4a",
  "audio/x-m4a",
]);

voice.post(
  "/api/voice/transcribe",
  rateLimit(20, 60),
  requireRole("asha_worker", "doctor", "admin"),
  async (c) => {
    let formData: FormData;
    try {
      formData = await c.req.formData();
    } catch {
      throw new HttpError(400, "Expected multipart/form-data");
    }

    const file = formData.get("file");
    if (!(file instanceof File)) {
      throw new HttpError(400, "Missing audio file");
    }
    // language is a query param, not a form field — matches the Python
    // original's signature (a plain `str | None` alongside `File(...)`
    // resolves as a query parameter under FastAPI's parameter rules).
    const language = c.req.query("language") ?? null;

    // Browsers report MediaRecorder blobs with a codec suffix (e.g.
    // "audio/webm;codecs=opus") — compare on the base MIME type only.
    const baseContentType = (file.type || "").split(";")[0]!.trim();
    if (!ALLOWED_CONTENT_TYPES.has(baseContentType)) {
      throw new HttpError(415, `Unsupported audio content type: ${file.type}`);
    }

    const audioBytes = new Uint8Array(await file.arrayBuffer());
    if (audioBytes.length === 0) {
      throw new HttpError(400, "Empty audio file");
    }
    if (audioBytes.length > MAX_AUDIO_BYTES) {
      throw new HttpError(413, "Audio file too large (max 10 MB)");
    }

    try {
      const transcript = await transcribe(audioBytes, file.name || "audio.webm", language);
      return c.json({ transcript });
    } catch (e) {
      if (e instanceof TranscriptionUnavailable) {
        throw new HttpError(503, e.message);
      }
      throw e;
    }
  },
);
