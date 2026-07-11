// Tests for _shared/cases.ts — the shared case-authorization and
// formatting helpers introduced in Phase 4 (Tranche B). authorizeCaseRowAccess
// is the direct TS port of cases.py's _authorize_case_row_access, the
// single most safety-critical piece of this file (every case read/write
// endpoint depends on it) — ported from the same 3-way role check
// backend/tests/test_admin_authz.py guards on the Python side.
import { assertEquals, assertThrows } from "@std/assert";
import {
  authorizeCaseRowAccess,
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
