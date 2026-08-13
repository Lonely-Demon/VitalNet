// Ported from backend/tests/test_supervisor_routes.py
import { assertEquals } from "@std/assert";
import { aggregateTeamMetrics, type TeamMetricsRow } from "../_shared/teamMetrics.ts";

function row(
  uid: string,
  tier: string,
  opts: { needsReview?: boolean; contraindication?: boolean; deterioration?: boolean; name?: string } = {},
): TeamMetricsRow {
  return {
    submitted_by: uid,
    full_name: opts.name ?? "Asha One",
    triage_level: tier,
    needs_review: opts.needsReview ?? false,
    contraindication_flags: opts.contraindication ? ["x"] : [],
    deterioration_alert: opts.deterioration ?? false,
  };
}

Deno.test("empty rows returns empty list", () => {
  assertEquals(aggregateTeamMetrics([]), []);
});

Deno.test("rows grouped by worker", () => {
  const rows = [
    row("u1", "ROUTINE", { name: "Asha One" }),
    row("u1", "URGENT", { name: "Asha One" }),
    row("u2", "EMERGENCY", { name: "Asha Two" }),
  ];
  const result = aggregateTeamMetrics(rows);
  const byId = new Map(result.map((w) => [w.user_id, w]));

  assertEquals(byId.get("u1")?.submission_count, 2);
  assertEquals(byId.get("u1")?.full_name, "Asha One");
  assertEquals(byId.get("u1")?.tier_distribution, { ROUTINE: 1, URGENT: 1, EMERGENCY: 0 });
  assertEquals(byId.get("u2")?.submission_count, 1);
  assertEquals(byId.get("u2")?.tier_distribution, { ROUTINE: 0, URGENT: 0, EMERGENCY: 1 });
});

Deno.test("rates computed correctly", () => {
  const rows = [
    row("u1", "EMERGENCY", { needsReview: true, contraindication: true, deterioration: true }),
    row("u1", "ROUTINE"),
    row("u1", "ROUTINE"),
    row("u1", "ROUTINE"),
  ];
  const [w] = aggregateTeamMetrics(rows);

  assertEquals(w?.submission_count, 4);
  assertEquals(w?.needs_review_count, 1);
  assertEquals(w?.needs_review_rate, 0.25);
  assertEquals(w?.contraindication_flag_rate, 0.25);
  assertEquals(w?.deterioration_alert_rate, 0.25);
});

Deno.test("rows with no submitted_by are skipped", () => {
  const rows: TeamMetricsRow[] = [
    {
      submitted_by: null,
      full_name: "x",
      triage_level: "ROUTINE",
      needs_review: false,
      contraindication_flags: [],
      deterioration_alert: false,
    },
  ];
  assertEquals(aggregateTeamMetrics(rows), []);
});

Deno.test("unknown full_name defaults to Unknown", () => {
  const rows: TeamMetricsRow[] = [
    {
      submitted_by: "u1",
      full_name: null,
      triage_level: "ROUTINE",
      needs_review: false,
      contraindication_flags: [],
      deterioration_alert: false,
    },
  ];
  const [w] = aggregateTeamMetrics(rows);
  assertEquals(w?.full_name, "Unknown");
});

Deno.test("result sorted by submission count descending", () => {
  const rows = [
    row("low", "ROUTINE", { name: "Low Volume" }),
    row("high", "ROUTINE", { name: "High Volume" }),
    row("high", "ROUTINE", { name: "High Volume" }),
    row("high", "ROUTINE", { name: "High Volume" }),
  ];
  const result = aggregateTeamMetrics(rows);
  assertEquals(result.map((w) => w.user_id), ["high", "low"]);
});
