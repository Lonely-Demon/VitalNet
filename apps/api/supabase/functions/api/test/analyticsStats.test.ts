import { assertEquals } from "@std/assert";
import {
  buildDailyVolume,
  buildEmergencyRateByWeek,
  buildMlAgreement,
  buildResponseTimes,
  buildTriageDistribution,
  percentile,
  pythonStyleWeekKey,
  topAshaWorkers,
} from "../_shared/analyticsStats.ts";

// ── buildTriageDistribution ─────────────────────────────────────────────────

Deno.test("buildTriageDistribution: counts each tier, ignores unknown levels", () => {
  const dist = buildTriageDistribution([
    { triage_level: "ROUTINE" },
    { triage_level: "ROUTINE" },
    { triage_level: "URGENT" },
    { triage_level: "EMERGENCY" },
    { triage_level: null },
  ]);
  assertEquals(dist, { ROUTINE: 2, URGENT: 1, EMERGENCY: 1 });
});

// ── buildDailyVolume ─────────────────────────────────────────────────────────

Deno.test("buildDailyVolume: groups by YYYY-MM-DD", () => {
  const daily = buildDailyVolume([
    { created_at: "2026-07-01T10:00:00Z" },
    { created_at: "2026-07-01T14:00:00Z" },
    { created_at: "2026-07-02T09:00:00Z" },
  ]);
  assertEquals(daily, { "2026-07-01": 2, "2026-07-02": 1 });
});

// ── topAshaWorkers ────────────────────────────────────────────────────────────

Deno.test("topAshaWorkers: sorted descending, limited, unknown name handled", () => {
  const result = topAshaWorkers([
    { submitted_by: "u1", profiles: { full_name: "Asha One" } },
    { submitted_by: "u1", profiles: { full_name: "Asha One" } },
    { submitted_by: "u2", profiles: null },
    { submitted_by: null, profiles: { full_name: "Ignored" } },
  ]);
  assertEquals(result, [
    { name: "Asha One", count: 2 },
    { name: "Unknown", count: 1 },
  ]);
});

Deno.test("topAshaWorkers: limited to `limit`", () => {
  const rows = Array.from({ length: 10 }, (_, i) => ({
    submitted_by: `u${i}`,
    profiles: { full_name: `Worker ${i}` },
  }));
  assertEquals(topAshaWorkers(rows, 5).length, 5);
});

// ── pythonStyleWeekKey ────────────────────────────────────────────────────────
// Reference values generated directly from Python's datetime.strftime("%Y-W%W").

Deno.test("pythonStyleWeekKey matches Python's %Y-W%W for reference dates", () => {
  const cases: Array<[string, string]> = [
    ["2026-01-01T10:00:00+00:00", "2026-W00"],
    ["2026-01-04T10:00:00+00:00", "2026-W00"],
    ["2026-01-05T10:00:00+00:00", "2026-W01"],
    ["2026-01-11T10:00:00+00:00", "2026-W01"],
    ["2026-02-15T10:00:00+00:00", "2026-W06"],
    ["2026-12-28T10:00:00+00:00", "2026-W52"],
    ["2026-12-31T10:00:00+00:00", "2026-W52"],
    ["2024-01-01T10:00:00+00:00", "2024-W01"],
    ["2027-01-01T10:00:00+00:00", "2027-W00"],
  ];
  for (const [input, expected] of cases) {
    assertEquals(pythonStyleWeekKey(input), expected, `for ${input}`);
  }
});

// ── buildEmergencyRateByWeek ───────────────────────────────────────────────────

Deno.test("buildEmergencyRateByWeek: groups, computes rate, sorted by week", () => {
  const result = buildEmergencyRateByWeek([
    { triage_level: "EMERGENCY", created_at: "2026-01-05T10:00:00+00:00" },
    { triage_level: "ROUTINE", created_at: "2026-01-05T11:00:00+00:00" },
    { triage_level: "ROUTINE", created_at: "2026-01-01T10:00:00+00:00" },
  ]);
  assertEquals(result, [
    { week: "2026-W00", total: 1, emergency: 0, rate: 0 },
    { week: "2026-W01", total: 2, emergency: 1, rate: 0.5 },
  ]);
});

// ── percentile ────────────────────────────────────────────────────────────────

Deno.test("percentile: empty array returns 0", () => {
  assertEquals(percentile([], 90), 0);
});

Deno.test("percentile: nearest-rank over a sorted list", () => {
  const sorted = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10];
  assertEquals(percentile(sorted, 90), 9);
  assertEquals(percentile(sorted, 50), 5);
  assertEquals(percentile(sorted, 0), 1);
});

Deno.test("percentile: matches Python's round-half-to-even at exact .5 index boundaries", () => {
  // idx = pct/100*(n-1): for n=10, pct=50 -> idx=4.5 exactly (round-to-even
  // -> 4, matching Python's round(4.5)==4, not Math.round's 5).
  assertEquals(percentile([1, 2, 3, 4, 5, 6, 7, 8, 9, 10], 50), 5); // idx 4 (0-indexed) -> value 5
  // n=12, pct=50 -> idx=50/100*11=5.5 exactly -> round-to-even -> 6 (5 is
  // odd, rounds up), matching Python's round(5.5)==6.
  const twelve = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 110, 120];
  assertEquals(percentile(twelve, 50), 70); // idx 6 (0-indexed) -> value 70
});

// ── buildResponseTimes ────────────────────────────────────────────────────────

Deno.test("buildResponseTimes: computes median/p90 for reviewed cases", () => {
  const now = new Date("2026-07-11T00:00:00Z");
  const rows = [
    { triage_level: "EMERGENCY", created_at: "2026-07-10T00:00:00Z", reviewed_at: "2026-07-10T00:10:00Z" },
    { triage_level: "EMERGENCY", created_at: "2026-07-10T01:00:00Z", reviewed_at: "2026-07-10T01:20:00Z" },
  ];
  const result = buildResponseTimes(rows, now);
  assertEquals(result.EMERGENCY.count_reviewed, 2);
  assertEquals(result.EMERGENCY.median_minutes, 15);
  assertEquals(result.EMERGENCY.overdue_count, 0);
});

Deno.test("buildResponseTimes: unreviewed case past threshold counts as overdue", () => {
  const now = new Date("2026-07-11T00:00:00Z");
  const rows = [
    // EMERGENCY threshold is 15 minutes; created 1 hour before `now`, never reviewed.
    { triage_level: "EMERGENCY", created_at: "2026-07-10T23:00:00Z", reviewed_at: null },
  ];
  const result = buildResponseTimes(rows, now);
  assertEquals(result.EMERGENCY.overdue_count, 1);
  assertEquals(result.EMERGENCY.count_reviewed, 0);
  assertEquals(result.EMERGENCY.median_minutes, null);
});

Deno.test("buildResponseTimes: unreviewed case within threshold is neither counted nor overdue", () => {
  const now = new Date("2026-07-11T00:00:00Z");
  const rows = [{ triage_level: "URGENT", created_at: "2026-07-10T23:55:00Z", reviewed_at: null }];
  const result = buildResponseTimes(rows, now);
  assertEquals(result.URGENT.overdue_count, 0);
  assertEquals(result.URGENT.count_reviewed, 0);
});

// ── buildMlAgreement ──────────────────────────────────────────────────────────

Deno.test("buildMlAgreement: computes per-tier and overall agreement rate", () => {
  const result = buildMlAgreement([
    { actual_severity: "EMERGENCY", case_records: { triage_level: "EMERGENCY", facility_id: "f1" } },
    { actual_severity: "URGENT", case_records: { triage_level: "EMERGENCY", facility_id: "f1" } },
    { actual_severity: "ROUTINE", case_records: { triage_level: "ROUTINE", facility_id: "f1" } },
  ]);
  assertEquals(result.overall_count, 3);
  assertEquals(result.overall_agreement_rate, 0.667);
  assertEquals(result.by_tier.EMERGENCY, { agreement_rate: 0.5, count: 2 });
  assertEquals(result.by_tier.ROUTINE, { agreement_rate: 1, count: 1 });
  assertEquals(result.by_tier.URGENT, { agreement_rate: null, count: 0 });
});

Deno.test("buildMlAgreement: no rows returns null rates, zero counts", () => {
  const result = buildMlAgreement([]);
  assertEquals(result.overall_agreement_rate, null);
  assertEquals(result.overall_count, 0);
});
