// Tests for _shared/voice.ts — ported from backend/tests/test_voice_transcription.py's
// coverage (provider-not-configured, Groq-tried-first, Sarvam-as-fallback).
// fetch() is monkey-patched per test (restored in a `finally`) rather than
// hitting the real Groq/Sarvam APIs, matching the Python suite's own
// monkeypatch-the-client approach.
import { assertEquals, assertRejects } from "@std/assert";
import { transcribe, TranscriptionUnavailable } from "../_shared/voice.ts";
import { _setConfigForTest, type Config } from "../_shared/config.ts";

function testConfig(overrides: Partial<Config> = {}): Config {
  return {
    supabaseUrl: "https://example.supabase.co",
    supabaseAnonKey: "anon",
    supabaseJwtSecret: "secret",
    supabaseServiceRoleKey: "service",
    environment: "development",
    corsAllowedOrigins: "",
    frontendUrl: "",
    jwtLocalVerification: true,
    revocationRecheckSeconds: 300,
    csrfToken: "vitalnet-spa",
    groqApiKey: "",
    geminiApiKey: "",
    sarvamApiKey: "",
    vapidPublicKey: "",
    vapidPrivateKey: "",
    vapidSubject: "mailto:admin@example.com",
    dataRetentionDays: 0,
    ...overrides,
  };
}

async function withMockFetch<T>(
  impl: (input: RequestInfo | URL, init?: RequestInit) => Promise<Response>,
  fn: () => Promise<T>,
): Promise<T> {
  const original = globalThis.fetch;
  globalThis.fetch = impl as typeof fetch;
  try {
    return await fn();
  } finally {
    globalThis.fetch = original;
  }
}

Deno.test("transcribe: throws TranscriptionUnavailable when nothing is configured", async () => {
  _setConfigForTest(testConfig());
  await assertRejects(() => transcribe(new Uint8Array([1, 2, 3]), "clip.webm"), TranscriptionUnavailable);
});

Deno.test("transcribe: returns stripped text from Groq when configured", async () => {
  _setConfigForTest(testConfig({ groqApiKey: "test-groq-key" }));

  const result = await withMockFetch(
    (input) => {
      const url = String(input);
      if (url.includes("api.groq.com")) {
        return Promise.resolve(
          new Response(JSON.stringify({ text: "  fever for three days  " }), { status: 200 }),
        );
      }
      throw new Error(`unexpected fetch to ${url}`);
    },
    () => transcribe(new Uint8Array([1, 2, 3]), "clip.webm", "en"),
  );

  assertEquals(result, "fever for three days");
});

Deno.test("transcribe: Groq is tried before Sarvam when both are configured", async () => {
  _setConfigForTest(testConfig({ groqApiKey: "groq-key", sarvamApiKey: "sarvam-key" }));
  let sarvamCalled = false;

  const result = await withMockFetch(
    (input) => {
      const url = String(input);
      if (url.includes("api.groq.com")) {
        return Promise.resolve(new Response(JSON.stringify({ text: "groq answered" }), { status: 200 }));
      }
      if (url.includes("api.sarvam.ai")) {
        sarvamCalled = true;
        return Promise.resolve(new Response(JSON.stringify({ transcript: "sarvam answered" }), { status: 200 }));
      }
      throw new Error(`unexpected fetch to ${url}`);
    },
    () => transcribe(new Uint8Array([1, 2, 3]), "clip.webm", "hi"),
  );

  assertEquals(result, "groq answered");
  assertEquals(sarvamCalled, false);
});

Deno.test("transcribe: falls back to Sarvam when Groq fails", async () => {
  _setConfigForTest(testConfig({ groqApiKey: "groq-key", sarvamApiKey: "sarvam-key" }));

  const result = await withMockFetch(
    (input) => {
      const url = String(input);
      if (url.includes("api.groq.com")) {
        return Promise.resolve(new Response("upstream error", { status: 500 }));
      }
      if (url.includes("api.sarvam.ai")) {
        return Promise.resolve(new Response(JSON.stringify({ transcript: "sarvam answered" }), { status: 200 }));
      }
      throw new Error(`unexpected fetch to ${url}`);
    },
    () => transcribe(new Uint8Array([1, 2, 3]), "clip.webm", "hi"),
  );

  assertEquals(result, "sarvam answered");
});

Deno.test("transcribe: Sarvam is never attempted when unconfigured, even if Groq fails", async () => {
  _setConfigForTest(testConfig({ groqApiKey: "groq-key", sarvamApiKey: "" }));

  await assertRejects(
    () =>
      withMockFetch(
        (input) => {
          const url = String(input);
          if (url.includes("api.groq.com")) {
            return Promise.resolve(new Response("upstream error", { status: 500 }));
          }
          throw new Error(`unexpected fetch to ${url}`);
        },
        () => transcribe(new Uint8Array([1, 2, 3]), "clip.webm", "hi"),
      ),
    TranscriptionUnavailable,
  );
});
