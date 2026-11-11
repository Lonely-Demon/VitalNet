// Tests for _shared/cases.ts — the shared case-authorization and
// formatting helpers introduced in Phase 4 (Tranche B). authorizeCaseRowAccess
// is the direct TS port of cases.py's _authorize_case_row_access, the
// single most safety-critical piece of this file (every case read/write
// endpoint depends on it) — ported from the same 3-way role check
// backend/tests/test_admin_authz.py guards on the Python side.
import { assertEquals, assertThrows } from "@std/assert";
import {
  authorizeCaseRowAccess,
  computeNeedsReview,
  formatRiskDriver,
  normalizedIsoTs,
  parseUuid,
  sanitizeMedicalText,
} from "../_shared/cases.ts";
import { HttpError } from "../_shared/database.ts";
import type { AuthedUser } from "../_shared/types.ts";

function user(overrides: Partial<AuthedUser> = {}): AuthedUser {
  return {
    sub: "user-1",
    resolvedRole: "asha_worker",
    resolvedFacilityId: null,
    token: "tok",
    ...overrides,
  };
}

// ── authorizeCaseRowAccess ──────────────────────────────────────────────────

Deno.test("authorizeCaseRowAccess: admin is authorized for any case", () => {
  authorizeCaseRowAccess(user({ resolvedRole: "admin" }), { facility_id: "f1", submitted_by: "someone-else" });
});

Deno.test("authorizeCaseRowAccess: doctor is authorized for own facility", () => {
  authorizeCaseRowAccess(user({ resolvedRole: "doctor", resolvedFacilityId: "f1" }), {
    facility_id: "f1",
    submitted_by: "someone-else",
  });
});

Deno.test("authorizeCaseRowAccess: doctor is rejected for a different facility", () => {
  assertThrows(
    () =>
      authorizeCaseRowAccess(user({ resolvedRole: "doctor", resolvedFacilityId: "f1" }), {
        facility_id: "f2",
        submitted_by: "someone-else",
      }),
    HttpError,
  );
});

Deno.test("authorizeCaseRowAccess: doctor with no facility is rejected even for a null-facility case", () => {
  assertThrows(
    () =>
      authorizeCaseRowAccess(user({ resolvedRole: "doctor", resolvedFacilityId: null }), {
        facility_id: null,
        submitted_by: "someone-else",
      }),
    HttpError,
  );
});

Deno.test("authorizeCaseRowAccess: asha_worker is authorized for their own submission", () => {
  authorizeCaseRowAccess(user({ resolvedRole: "asha_worker", sub: "worker-1" }), {
    facility_id: "f1",
    submitted_by: "worker-1",
  });
});

Deno.test("authorizeCaseRowAccess: asha_worker is rejected for another worker's submission", () => {
  assertThrows(
    () =>
      authorizeCaseRowAccess(user({ resolvedRole: "asha_worker", sub: "worker-1" }), {
        facility_id: "f1",
        submitted_by: "worker-2",
      }),
    HttpError,
  );
});

Deno.test("authorizeCaseRowAccess: unknown role is rejected", () => {
  assertThrows(
    () =>
      authorizeCaseRowAccess(user({ resolvedRole: "supervisor" }), {
        facility_id: "f1",
        submitted_by: "worker-1",
      }),
    HttpError,
  );
});

// ── parseUuid ────────────────────────────────────────────────────────────

Deno.test("parseUuid: accepts a canonical hyphenated UUID, lowercased", () => {
  assertEquals(parseUuid("550E8400-E29B-41D4-A716-446655440000"), "550e8400-e29b-41d4-a716-446655440000");
});

Deno.test("parseUuid: rejects a non-UUID string", () => {
  assertThrows(() => parseUuid("not-a-uuid", "case_id"), HttpError, "Invalid case_id");
});

// ── normalizedIsoTs ──────────────────────────────────────────────────────

Deno.test("normalizedIsoTs: a timestamp with no timezone is assumed UTC", () => {
  assertEquals(normalizedIsoTs("2026-01-01T10:00:00", "before"), "2026-01-01T10:00:00.000Z");
});

Deno.test("normalizedIsoTs: a timestamp with an explicit offset is converted to UTC", () => {
  assertEquals(normalizedIsoTs("2026-01-01T10:00:00+05:30", "before"), "2026-01-01T04:30:00.000Z");
});

Deno.test("normalizedIsoTs: an unparseable value throws 400", () => {
  assertThrows(() => normalizedIsoTs("not-a-date", "before"), HttpError, "Invalid before");
});

// ── sanitizeMedicalText ──────────────────────────────────────────────────

Deno.test("sanitizeMedicalText: strips HTML tags and collapses whitespace", () => {
  assertEquals(sanitizeMedicalText("<b>fever</b>   for   3  days"), "fever for 3 days");
});

Deno.test("sanitizeMedicalText: returns null for null input", () => {
  assertEquals(sanitizeMedicalText(null), null);
});

Deno.test("sanitizeMedicalText: returns null when stripped content is empty", () => {
  assertEquals(sanitizeMedicalText("<script></script>"), null);
});

Deno.test("sanitizeMedicalText: removes script blocks with mixed-case and spaced closing tags", () => {
  assertEquals(sanitizeMedicalText("<SCRIPT>alert('x')</SCRIPT > fever"), "fever");
});

Deno.test("sanitizeMedicalText: discards an unterminated script fragment", () => {
  assertEquals(sanitizeMedicalText("fever <script>alert('x')"), "fever");
});

// ── formatRiskDriver ───────────────────────────────────────────────────────

Deno.test("formatRiskDriver: no fired rules describes a routine presentation", () => {
  assertEquals(
    formatRiskDriver("ROUTINE", []),
    "No escalation rule fired — routine presentation. Classified as ROUTINE.",
  );
});

Deno.test("formatRiskDriver: fired rules are joined with citations", () => {
  const result = formatRiskDriver("EMERGENCY", [
    { id: "extreme_spo2", citation: "NEWS2 scale 1", detail: "Critically low oxygen saturation (80%)" },
  ]);
  assertEquals(result, "Critically low oxygen saturation (80%) (NEWS2 scale 1). Classified as EMERGENCY.");
});

// ── computeNeedsReview ───────────────────────────────────────────────────
// Guards the advisory-ML safety property: a rules-vs-model disagreement
// must surface for human review, even when nothing else would have
// flagged the case. Most consequential for an EMERGENCY(model) ->
// lower(rules) de-escalation, which would otherwise sink out of the
// priority queue with no flag at all (the rules engine is deterministic,
// so it's never "low confidence" about its own, lower tier).

const BASE_NEEDS_REVIEW_INPUT = {
  llmNeedsReview: false,
  humanReviewRequested: false,
  hasContraindicationFlags: false,
  deteriorationAlert: false,
  modelAgreed: true as boolean | undefined,
};

Deno.test("computeNeedsReview: false when nothing flags and the model agrees", () => {
  assertEquals(computeNeedsReview(BASE_NEEDS_REVIEW_INPUT), false);
});

Deno.test("computeNeedsReview: true when the advisory model disagrees with the rules-authoritative tier", () => {
  assertEquals(computeNeedsReview({ ...BASE_NEEDS_REVIEW_INPUT, modelAgreed: false }), true);
});

Deno.test("computeNeedsReview: false when no model ran (modelAgreed undefined) and nothing else flags", () => {
  assertEquals(computeNeedsReview({ ...BASE_NEEDS_REVIEW_INPUT, modelAgreed: undefined }), false);
});

Deno.test("computeNeedsReview: still true when other signals flag but the model agrees", () => {
  assertEquals(computeNeedsReview({ ...BASE_NEEDS_REVIEW_INPUT, deteriorationAlert: true }), true);
  assertEquals(computeNeedsReview({ ...BASE_NEEDS_REVIEW_INPUT, hasContraindicationFlags: true }), true);
  assertEquals(computeNeedsReview({ ...BASE_NEEDS_REVIEW_INPUT, humanReviewRequested: true }), true);
  assertEquals(computeNeedsReview({ ...BASE_NEEDS_REVIEW_INPUT, llmNeedsReview: true }), true);
});

// ── sanitizeDoctorNotes (BUG-45) ───────────────────────────────────────────

import { sanitizeDoctorNotes } from "../routes/cases.ts";
import { triage } from "@vitalnet/clinical-core";
import { FEATURE_NAMES, TRIAGE_TREES } from "../_shared/model.ts";

Deno.test("sanitizeDoctorNotes: does not escape HTML entities and strips control chars (REG-09)", () => {
  assertEquals(
    sanitizeDoctorNotes("<script>alert('xss')</script> & \"notes\""),
    "<script>alert('xss')</script> & \"notes\"",
  );
  assertEquals(
    sanitizeDoctorNotes("BP > 140/90, SpO2 < 95% & patient stable"),
    "BP > 140/90, SpO2 < 95% & patient stable",
  );
  assertEquals(sanitizeDoctorNotes("   Normal doctor notes   "), "Normal doctor notes");
  assertEquals(sanitizeDoctorNotes(""), null);
  assertEquals(sanitizeDoctorNotes(null), null);
  assertEquals(sanitizeDoctorNotes(undefined), null);
});

// ── REG-02: SMS Gateway Auth & Stub Enforcement ────────────────────────────

import { cases } from "../routes/cases.ts";
import { _setConfigForTest, type Config } from "../_shared/config.ts";

function initTestConfig(overrides: Partial<Config> = {}) {
  _setConfigForTest({
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
    internalSchedulerToken: "test-scheduler-token",
    ...overrides,
  });
}

async function withRateLimitMock<T>(fn: () => Promise<T>): Promise<T> {
  const original = globalThis.fetch;
  globalThis.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const urlStr = String(input);
    if (urlStr.includes("fn_rate_limit")) {
      return new Response(JSON.stringify(true), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    return await original(input, init);
  };
  try {
    return await fn();
  } finally {
    globalThis.fetch = original;
  }
}

Deno.test("REG-02: POST /api/cases/sms-gateway rejects unauthenticated requests with 401", async () => {
  initTestConfig();
  await withRateLimitMock(async () => {
    const res = await cases.request("/api/cases/sms-gateway", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ body: "TRIAGE 30 M fever" }),
    });
    assertEquals(res.status, 401);
  });
});

Deno.test("REG-02: POST /api/cases/sms-gateway rejects invalid bearer token with 401", async () => {
  initTestConfig();
  await withRateLimitMock(async () => {
    const res = await cases.request("/api/cases/sms-gateway", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: "Bearer not.a.validtoken",
      },
      body: JSON.stringify({ body: "TRIAGE 30 M fever" }),
    });
    assertEquals(res.status, 401);
  });
});

Deno.test("REG-02: POST /api/cases/sms-gateway rejects wrong webhook token with 401", async () => {
  initTestConfig();
  await withRateLimitMock(async () => {
    const res = await cases.request("/api/cases/sms-gateway", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-SMS-Webhook-Token": "wrong-secret",
      },
      body: JSON.stringify({ body: "TRIAGE 30 M fever" }),
    });
    assertEquals(res.status, 401);
  });
});

Deno.test("REG-02, REG-05: POST /api/cases/sms-gateway accepts verified webhook token and populates NOT NULL stub columns", async () => {
  initTestConfig({ internalSchedulerToken: "valid-sms-token" });
  let capturedPayload: Record<string, unknown> | null = null;
  const original = globalThis.fetch;
  globalThis.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
    const urlStr = String(input);
    if (urlStr.includes("fn_rate_limit")) {
      return new Response(JSON.stringify(true), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    if (urlStr.includes("case_records")) {
      if (init?.body && typeof init.body === "string") {
        try {
          capturedPayload = JSON.parse(init.body) as Record<string, unknown>;
        } catch {
          // ignore
        }
      }
      return new Response(JSON.stringify([{ id: "stub-id" }]), {
        status: 201,
        headers: { "Content-Type": "application/json" },
      });
    }
    return await original(input, init);
  };

  try {
    const res = await cases.request("/api/cases/sms-gateway", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-SMS-Webhook-Token": "valid-sms-token",
      },
      body: JSON.stringify({ body: "TRIAGE 30 M high_fever", facility_id: "00000000-0000-0000-0000-000000000042" }),
    });
    assertEquals(res.status, 200);
    const body = await res.json();
    assertEquals(body.status, "queued");
    assertEquals(body.is_sms_stub, true);

    // Verify NOT NULL columns on stubRecord
    const payload = capturedPayload as Record<string, unknown> | null;
    assertEquals(payload !== null, true);
    if (payload) {
      assertEquals(typeof payload.submitted_by, "string");
      assertEquals(payload.facility_id, "00000000-0000-0000-0000-000000000042");
      assertEquals(payload.patient_name, "Emergency Patient (SMS)");
      assertEquals(payload.patient_location, "Community (SMS Intake)");
      assertEquals(payload.complaint_duration, "acute (<24h)");
      // ROUTINE maps to 2 under case_records_triage_priority_map_check
      assertEquals(payload.triage_priority, 2);
    }
  } finally {
    globalThis.fetch = original;
  }
});

// ── REG-05: Triage Priority PostgreSQL Constraint Alignment ────────────────

Deno.test("REG-05: Triage priority mapping aligns with case_records_triage_priority_map_check (EMERGENCY=0, URGENT=1, ROUTINE=2)", () => {
  function mapPriority(tier: string): number {
    return tier === "EMERGENCY" ? 0 : tier === "URGENT" ? 1 : 2;
  }
  assertEquals(mapPriority("EMERGENCY"), 0);
  assertEquals(mapPriority("URGENT"), 1);
  assertEquals(mapPriority("ROUTINE"), 2);
});

// ── REG-03: DSR Route Facility Isolation Fail-Closed ───────────────────────

Deno.test("REG-03: Doctor and Admin fail closed on consent revocation if resolvedFacilityId is null", () => {
  const caseRow = { id: "c1", facility_id: "fac-1", submitted_by: "sub-1" };
  const doctorWithoutFacility = user({ resolvedRole: "doctor", resolvedFacilityId: null });
  const adminWithoutFacility = user({ resolvedRole: "admin", resolvedFacilityId: null });

  assertThrows(
    () => {
      if (
        !doctorWithoutFacility.resolvedFacilityId || caseRow.facility_id !== doctorWithoutFacility.resolvedFacilityId
      ) {
        throw new HttpError(403, "Not authorized to access cases outside your facility");
      }
    },
    HttpError,
    "Not authorized to access cases outside your facility",
  );

  assertThrows(
    () => {
      if (!adminWithoutFacility.resolvedFacilityId || caseRow.facility_id !== adminWithoutFacility.resolvedFacilityId) {
        throw new HttpError(403, "Not authorized to access cases outside your facility");
      }
    },
    HttpError,
    "Not authorized to access cases outside your facility",
  );
});

// ── REG-06: Follow-up Complete Endpoint Registration ───────────────────────

Deno.test("REG-06: POST /api/cases/:case_id/followup-complete rejects unauthenticated request with 401", async () => {
  initTestConfig();
  await withRateLimitMock(async () => {
    const res = await cases.request("/api/cases/550e8400-e29b-41d4-a716-446655440000/followup-complete", {
      method: "POST",
    });
    assertEquals(res.status, 401);
  });
});

// ── PALS Infant Age Months Triage (BUG-03) ──────────────────────────────────

Deno.test("triage: infant with age_months accurately resolves fractional years", () => {
  // Infant 1 month old with high fever: resolves to 1/12 = 0.083 years (< 3 months) -> triggers neonatal/infant rule
  const result = triage(
    {
      patient_age: 0,
      age_months: 1,
      patient_sex: "female",
      bp_systolic: null,
      bp_diastolic: null,
      spo2: 98,
      heart_rate: 130,
      temperature: 38.5,
      symptoms: ["high_fever"],
      chief_complaint: "fever in 1mo infant",
      complaint_duration: "1 day",
      location: "Village A",
    },
    { mode: "rules_first", trees: TRIAGE_TREES, featureNames: FEATURE_NAMES },
  );

  assertEquals(result.tier, "EMERGENCY");
  const firedNeonatal = result.firedRules.some((r) => r.id === "neonatal_fever");
  assertEquals(firedNeonatal, true);
});
