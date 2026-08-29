// Ported from backend/tests/test_outbreak_routes.py — the same cases,
// against the TS port of _compute_ears_signals.
import { assertEquals } from "@std/assert";
import { computeEarsSignals, type EarsRow, MIN_FLOOR } from "../_shared/ears.ts";

const TODAY = "2026-07-05";
const FAC = "fac-1";

function row(day: string, symptom: string, facilityId = FAC): EarsRow {
  return { facility_id: facilityId, symptoms: [symptom], created_at: day + "T10:00:00Z" };
}

function repeat<T>(item: T, n: number): T[] {
  return Array.from({ length: n }, () => item);
}

function dayNDaysBeforeToday(n: number): string {
  const d = new Date(TODAY + "T00:00:00Z");
  d.setUTCDate(d.getUTCDate() - n);
  return d.toISOString().slice(0, 10);
}

Deno.test("no rows returns no signals", () => {
  assertEquals(computeEarsSignals([], TODAY), []);
});

Deno.test("below floor never flags even with zero baseline", () => {
  const rows = repeat(row(TODAY, "high_fever"), MIN_FLOOR - 1);
  assertEquals(computeEarsSignals(rows, TODAY), []);
});

Deno.test("stable baseline matching today does not flag", () => {
  let rows: EarsRow[] = [];
  for (let n = 1; n <= 7; n++) {
    rows = rows.concat(repeat(row(dayNDaysBeforeToday(n), "high_fever"), 3));
  }
  rows = rows.concat(repeat(row(TODAY, "high_fever"), 3));
  assertEquals(computeEarsSignals(rows, TODAY), []);
});

Deno.test("sharp spike above baseline flags", () => {
  let rows: EarsRow[] = [];
  for (let n = 1; n <= 7; n++) {
    rows = rows.concat(repeat(row(dayNDaysBeforeToday(n), "high_fever"), 2));
  }
  rows = rows.concat(repeat(row(TODAY, "high_fever"), 20));
  const signals = computeEarsSignals(rows, TODAY);
  assertEquals(signals.length, 1);
  assertEquals(signals[0]?.symptom, "high_fever");
  assertEquals(signals[0]?.facility_id, FAC);
  assertEquals(signals[0]?.today_count, 20);
});

Deno.test("zero baseline with floor met flags", () => {
  const rows = repeat(row(TODAY, "persistent_vomiting"), MIN_FLOOR);
  const signals = computeEarsSignals(rows, TODAY);
  assertEquals(signals.length, 1);
  assertEquals(signals[0]?.baseline_mean, 0);
  assertEquals(signals[0]?.baseline_stddev, 0);
});

Deno.test("high variance baseline requires larger spike to flag", () => {
  let rows: EarsRow[] = [];
  const noisyCounts = [0, 0, 0, 0, 0, 0, 10];
  for (let i = 0; i < 7; i++) {
    const n = i + 1;
    const count = noisyCounts[i]!;
    rows = rows.concat(repeat(row(dayNDaysBeforeToday(n), "chest_pain"), count));
  }
  rows = rows.concat(repeat(row(TODAY, "chest_pain"), 4));
  assertEquals(computeEarsSignals(rows, TODAY), []);
});

Deno.test("different facilities and symptoms scored independently", () => {
  let rows: EarsRow[] = [];
  for (let n = 1; n <= 7; n++) {
    rows = rows.concat(repeat(row(dayNDaysBeforeToday(n), "high_fever", "fac-A"), 1));
    rows = rows.concat(repeat(row(dayNDaysBeforeToday(n), "chest_pain", "fac-B"), 1));
  }
  rows = rows.concat(repeat(row(TODAY, "high_fever", "fac-A"), 15));
  rows = rows.concat(repeat(row(TODAY, "chest_pain", "fac-B"), 1));
  const signals = computeEarsSignals(rows, TODAY);
  assertEquals(signals.length, 1);
  assertEquals(signals[0]?.facility_id, "fac-A");
  assertEquals(signals[0]?.symptom, "high_fever");
});

Deno.test("rows missing facility_id are skipped", () => {
  const rows = repeat<EarsRow>({ facility_id: null, symptoms: ["high_fever"], created_at: TODAY + "T10:00:00Z" }, 5);
  assertEquals(computeEarsSignals(rows, TODAY), []);
});

Deno.test("case with multiple symptoms contributes to each", () => {
  const rows = repeat<EarsRow>(
    { facility_id: FAC, symptoms: ["high_fever", "severe_headache"], created_at: TODAY + "T10:00:00Z" },
    MIN_FLOOR,
  );
  const signals = computeEarsSignals(rows, TODAY);
  const symptomsFlagged = new Set(signals.map((s) => s.symptom));
  assertEquals(symptomsFlagged, new Set(["high_fever", "severe_headache"]));
});
