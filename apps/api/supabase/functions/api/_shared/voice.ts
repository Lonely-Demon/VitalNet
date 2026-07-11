// Server-side voice transcription — ported from app/services/voice.py.
// Two independent providers, tried in a fixed order:
//   1. Groq Whisper (whisper-large-v3-turbo) — tried FIRST for every
//      language, including hi/ta. Groq has no metered free-credit ceiling
//      for this app's volume; Sarvam's free tier is a fixed signup credit.
//   2. Sarvam AI (saaras:v3) — specialised Indian-language STT, used only
//      as the fallback if Groq isn't configured or a request to it fails.
// Both are optional and independent: either credential alone is enough for
// transcription to work for every supported language.
import { getConfig } from "./config.ts";

const GROQ_TRANSCRIPTION_URL = "https://api.groq.com/openai/v1/audio/transcriptions";
const SARVAM_URL = "https://api.sarvam.ai/speech-to-text";
const GROQ_MODEL = "whisper-large-v3-turbo";
const SARVAM_MODEL = "saaras:v3";

// i18n language codes this app supports happen to be valid ISO-639-1 codes
// Whisper accepts directly — no translation table needed for Groq.
const SUPPORTED_LANGUAGES = new Set(["en", "hi", "ta"]);

// ISO-639-1 -> Sarvam's BCP-47 language codes.
const SARVAM_LANGUAGE_CODES: Record<string, string> = { en: "en-IN", hi: "hi-IN", ta: "ta-IN" };

export class TranscriptionUnavailable extends Error {}

async function transcribeGroq(
  apiKey: string,
  audio: Uint8Array,
  filename: string,
  language: string | null,
): Promise<string> {
  const form = new FormData();
  form.append("file", new Blob([audio.slice()]), filename);
  form.append("model", GROQ_MODEL);
  if (language) form.append("language", language);

  const response = await fetch(GROQ_TRANSCRIPTION_URL, {
    method: "POST",
    headers: { Authorization: `Bearer ${apiKey}` },
    body: form,
  });
  if (!response.ok) {
    throw new Error(`Groq transcription failed: HTTP ${response.status}`);
  }
  const body = await response.json();
  return String(body.text ?? "").trim();
}

async function transcribeSarvam(
  apiKey: string,
  audio: Uint8Array,
  filename: string,
  language: string | null,
): Promise<string> {
  const languageCode = SARVAM_LANGUAGE_CODES[language ?? ""] ?? "hi-IN";
  const form = new FormData();
  form.append("file", new Blob([audio.slice()]), filename);
  form.append("model", SARVAM_MODEL);
  form.append("language_code", languageCode);

  const response = await fetch(SARVAM_URL, {
    method: "POST",
    headers: { "api-subscription-key": apiKey },
    body: form,
  });
  if (!response.ok) {
    throw new Error(`Sarvam transcription failed: HTTP ${response.status}`);
  }
  const body = await response.json();
  return String(body.transcript ?? "").trim();
}

/**
 * Groq first (unmetered for this app's volume), Sarvam as the fallback
 * only. Only configured providers are attempted, so an unconfigured one is
 * never counted as a failure.
 */
export async function transcribe(
  audio: Uint8Array,
  filename: string,
  language: string | null = null,
): Promise<string> {
  const config = getConfig();
  const lang = language && SUPPORTED_LANGUAGES.has(language) ? language : null;

  const providers: Array<[string, () => Promise<string>]> = [];
  if (config.groqApiKey) providers.push(["groq", () => transcribeGroq(config.groqApiKey, audio, filename, lang)]);
  if (config.sarvamApiKey) {
    providers.push(["sarvam", () => transcribeSarvam(config.sarvamApiKey, audio, filename, lang)]);
  }

  if (providers.length === 0) {
    throw new TranscriptionUnavailable("Voice transcription is not configured on this server");
  }

  let lastError: unknown;
  for (const [name, fn] of providers) {
    try {
      return await fn();
    } catch (e) {
      console.warn(`${name} transcription failed:`, e);
      lastError = e;
    }
  }
  throw new TranscriptionUnavailable(`Transcription failed: ${lastError}`);
}
