// Tests for _shared/llm.ts. Network calls to Groq/Gemini aren't exercised
// here (no live credentials in CI, by design — same posture as the Python
// suite's test_voice_transcription.py, which forces its own credentials
// empty via conftest.py); these tests instead lock down the two invariants
// that must hold with ZERO network access: (1) with no LLM keys configured,
// generateBriefing/generatePatientSummary/generateProtocolAnswer all
// resolve to their safe canned fallback rather than hanging or throwing,
// and (2) the triage tier is hard-locked onto every output regardless of
// what a (mocked) LLM tier returns — ported from llm.py's _enforce_schema
// contract.
import { assertEquals, assertStringIncludes } from "@std/assert";
import { generateBriefing, generatePatientSummary, generateProtocolAnswer } from "../_shared/llm.ts";
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

const FORM = {
  patient_age: 34,
  patient_sex: "female",
  location: "Village X",
  chief_complaint: "chest pain",
  complaint_duration: "2 hours",
  bp_systolic: 190,
  bp_diastolic: 110,
  spo2: 88,
  heart_rate: 130,
  temperature: 38.5,
  symptoms: ["chest_pain", "breathlessness"],
  observations: null,
  known_conditions: null,
  current_medications: null,
};

Deno.test("generateBriefing: no LLM keys configured returns the safe fallback with the tier intact", async () => {
  _setConfigForTest(testConfig());
  const briefing = await generateBriefing(FORM, {
    triage_level: "EMERGENCY",
    confidence_score: 1.0,
    risk_driver: "aggregate score 9",
    low_confidence: false,
  });

  assertEquals(briefing.triage_level, "EMERGENCY");
  assertEquals(briefing.llm_status, "fallback");
  assertEquals(briefing._model_used, "fallback");
  // EMERGENCY always needs_review, even when low_confidence is false —
  // matches llm.py's _fallback_briefing.
  assertEquals(briefing.needs_review, true);
  assertStringIncludes(briefing.disclaimer, "decision support only");
});

Deno.test("generateBriefing: fallback needs_review is false for a confident ROUTINE case", async () => {
  _setConfigForTest(testConfig());
  const briefing = await generateBriefing(FORM, {
    triage_level: "ROUTINE",
    confidence_score: 1.0,
    risk_driver: "no rule fired",
    low_confidence: false,
  });
  assertEquals(briefing.needs_review, false);
});

Deno.test("generateBriefing: fallback needs_review is true when low_confidence is set, even for ROUTINE", async () => {
  _setConfigForTest(testConfig());
  const briefing = await generateBriefing(FORM, {
    triage_level: "ROUTINE",
    confidence_score: 0.4,
    risk_driver: "no rule fired",
    low_confidence: true,
  });
  assertEquals(briefing.needs_review, true);
});

Deno.test("generatePatientSummary: no Groq key configured returns the canned fallback, generated=false", async () => {
  _setConfigForTest(testConfig());
  const result = await generatePatientSummary(
    { primary_risk_driver: "chest pain", recommended_immediate_actions: ["See a doctor"] },
    { triage_level: "URGENT", risk_driver: "chest pain" },
    "en",
  );
  assertEquals(result.generated, false);
  assertStringIncludes(result.summary, "doctor to check soon");
});

Deno.test("generateProtocolAnswer: no LLM keys configured queues the question for curation", async () => {
  _setConfigForTest(testConfig());
  const result = await generateProtocolAnswer("What is the ANC visit schedule?", "en");
  assertEquals(result.grounded, false);
  assertEquals(result.generated, false);
  assertStringIncludes(result.answer, "forwarded to a supervisor/doctor");
});
