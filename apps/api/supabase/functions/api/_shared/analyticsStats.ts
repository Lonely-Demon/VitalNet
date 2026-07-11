// Pure aggregation logic ported from analytics_routes.py — kept separate
// from the route handlers (which do the DB I/O) so the math is testable
// without a live database, same pattern as ears.ts/teamMetrics.ts.

// ── /summary ─────────────────────────────────────────────────────────────────

export interface TriageDistribution {
  ROUTINE: number;
  URGENT: number;
  EMERGENCY: number;
}

export function buildTriageDistribution(rows: Array<{ triage_level: string | null }>): TriageDistribution {
  const dist: TriageDistribution = { ROUTINE: 0, URGENT: 0, EMERGENCY: 0 };
  for (const row of rows) {
    const level = row.triage_level;
    if (level === "ROUTINE" || level === "URGENT" || level === "EMERGENCY") {
      dist[level] += 1;
    }
  }
  return dist;
}

/** created_at is an ISO timestamp; grouped by its YYYY-MM-DD prefix, same
 * slicing convention used throughout this codebase for "day bucket". */
export function buildDailyVolume(rows: Array<{ created_at: string }>): Record<string, number> {
  const daily: Record<string, number> = {};
  for (const row of rows) {
    const day = row.created_at.slice(0, 10);
    daily[day] = (daily[day] ?? 0) + 1;
  }
  return daily;
}

export interface AshaWorkerRow {
  submitted_by: string | null;
  profiles: { full_name: string | null } | null;
}

export interface TopAshaWorker {
  name: string;
  count: number;
}

export function topAshaWorkers(rows: AshaWorkerRow[], limit = 5): TopAshaWorker[] {
  const counts = new Map<string, { name: string; count: number }>();
  for (const row of rows) {
    const uid = row.submitted_by;
    if (!uid) continue;
    const name = row.profiles?.full_name ?? "Unknown";
    const key = `${uid}::${name}`;
    const existing = counts.get(key);
    if (existing) {
      existing.count += 1;
    } else {
      counts.set(key, { name, count: 1 });
    }
  }
  return [...counts.values()].sort((a, b) => b.count - a.count).slice(0, limit);
}

// ── /emergency-rate ────────────────────────────────────────────────────────

/**
 * Matches Python's `datetime.strftime("%Y-W%W")`: Monday-based week
 * number, zero-padded, where all days before the year's first Monday are
 * week 0 (NOT ISO 8601 week numbering, which uses %V and different
 * year-boundary rules — this must match %W exactly since it's a grouping
 * key, not just a display string). Operates in UTC, matching created_at's
 * timezone-aware ISO strings.
 */
export function pythonStyleWeekKey(isoDate: string): string {
  const dt = new Date(isoDate);
  const year = dt.getUTCFullYear();
  const jan1 = Date.UTC(year, 0, 1);
  const jan1Weekday = new Date(jan1).getUTCDay() === 0 ? 6 : new Date(jan1).getUTCDay() - 1; // Monday=0..Sunday=6
  const daysBeforeFirstMonday = (7 - jan1Weekday) % 7;
  const firstMondayYday = 1 + daysBeforeFirstMonday; // 1-indexed day-of-year

  const ydayMs = Date.UTC(dt.getUTCFullYear(), dt.getUTCMonth(), dt.getUTCDate()) - jan1;
  const yday = Math.round(ydayMs / 86_400_000) + 1; // 1-indexed

  const week = yday < firstMondayYday ? 0 : Math.floor((yday - firstMondayYday) / 7) + 1;
  return `${year}-W${String(week).padStart(2, "0")}`;
}

export interface EmergencyRateWeek {
  week: string;
  total: number;
  emergency: number;
  rate: number;
}

export function buildEmergencyRateByWeek(
  rows: Array<{ triage_level: string | null; created_at: string }>,
): EmergencyRateWeek[] {
  const weeks = new Map<string, { total: number; emergency: number }>();
  for (const row of rows) {
    const key = pythonStyleWeekKey(row.created_at);
    let w = weeks.get(key);
    if (!w) {
      w = { total: 0, emergency: 0 };
      weeks.set(key, w);
    }
    w.total += 1;
    if (row.triage_level === "EMERGENCY") w.emergency += 1;
  }

  return [...weeks.entries()]
    .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
    .map(([week, v]) => ({
      week,
      total: v.total,
      emergency: v.emergency,
      rate: v.total ? Math.round((v.emergency / v.total) * 1000) / 1000 : 0,
    }));
}

// ── /response-times ───────────────────────────────────────────────────────

export const OVERDUE_THRESHOLDS_MIN: Record<string, number> = {
  EMERGENCY: 15,
  URGENT: 120,
  ROUTINE: 24 * 60,
};

/** Python's round() uses round-half-to-even ("banker's rounding"); JS's
 * Math.round() always rounds .5 up. They disagree at exact .5 boundaries
 * (e.g. round(4.5): Python -> 4, Math.round -> 5) — real divergence hit by
 * percentile()'s idx computation whenever pct/100*(n-1) lands on .5
 * exactly (e.g. p50 of an even-length list), not just a theoretical edge
 * case. */
function pythonRound(x: number): number {
  const floor = Math.floor(x);
  const diff = x - floor;
  if (diff < 0.5) return floor;
  if (diff > 0.5) return floor + 1;
  return floor % 2 === 0 ? floor : floor + 1;
}

/** Nearest-rank percentile over an already-sorted list. pct in [0, 100]. */
export function percentile(sortedValues: number[], pct: number): number {
  if (sortedValues.length === 0) return 0.0;
  const idx = Math.min(sortedValues.length - 1, Math.max(0, pythonRound((pct / 100) * (sortedValues.length - 1))));
  return sortedValues[idx]!;
}

function median(sortedValues: number[]): number {
  const n = sortedValues.length;
  if (n === 0) return 0;
  const mid = Math.floor(n / 2);
  return n % 2 === 0 ? (sortedValues[mid - 1]! + sortedValues[mid]!) / 2 : sortedValues[mid]!;
}

function round1(n: number): number {
  return Math.round(n * 10) / 10;
}

export interface ResponseTimesRow {
  triage_level: string | null;
  created_at: string;
  reviewed_at: string | null;
}

export interface TierResponseTimes {
  count_reviewed: number;
  median_minutes: number | null;
  p90_minutes: number | null;
  overdue_count: number;
  overdue_threshold_minutes: number;
}

export function buildResponseTimes(
  rows: ResponseTimesRow[],
  now: Date,
): Record<"ROUTINE" | "URGENT" | "EMERGENCY", TierResponseTimes> {
  const tiers = ["ROUTINE", "URGENT", "EMERGENCY"] as const;
  const minutesByTier: Record<string, number[]> = { ROUTINE: [], URGENT: [], EMERGENCY: [] };
  const overdueByTier: Record<string, number> = { ROUTINE: 0, URGENT: 0, EMERGENCY: 0 };

  for (const row of rows) {
    const tier = row.triage_level;
    if (tier !== "ROUTINE" && tier !== "URGENT" && tier !== "EMERGENCY") continue;
    const created = new Date(row.created_at);
    const thresholdMin = OVERDUE_THRESHOLDS_MIN[tier]!;

    if (row.reviewed_at) {
      const reviewed = new Date(row.reviewed_at);
      minutesByTier[tier]!.push((reviewed.getTime() - created.getTime()) / 60_000);
    } else if ((now.getTime() - created.getTime()) / 60_000 > thresholdMin) {
      overdueByTier[tier]! += 1;
    }
  }

  const result = {} as Record<"ROUTINE" | "URGENT" | "EMERGENCY", TierResponseTimes>;
  for (const tier of tiers) {
    const sorted = [...minutesByTier[tier]!].sort((a, b) => a - b);
    result[tier] = {
      count_reviewed: sorted.length,
      median_minutes: sorted.length ? round1(median(sorted)) : null,
      p90_minutes: sorted.length ? round1(percentile(sorted, 90)) : null,
      overdue_count: overdueByTier[tier]!,
      overdue_threshold_minutes: OVERDUE_THRESHOLDS_MIN[tier]!,
    };
  }
  return result;
}

// ── /ml-agreement ────────────────────────────────────────────────────────
// Round 6 rebuild plan, Phase 4: repointed from triage_level (the ORIGINAL
// triage decision, ML-authoritative pre-migration) to model_tier (the
// advisory model's own opinion, populated only once rules_first submissions
// exist — phase29_events_and_advisory_model.sql). Now that triage_level is
// the deterministic rules engine's decision, comparing IT against outcomes
// would measure "are the rules correct", a different and separately
// important question from this endpoint's actual purpose: is the advisory
// model, which currently has zero say in triage_level, accurate enough that
// promoting it back to (partial) authority would ever be worth considering.
// That promotion decision is exactly what this endpoint exists to inform —
// see DECISIONS §33.
//
// Ground truth is case_outcomes.actual_severity only (a doctor's triage
// override, case_records.overridden_triage, is a second real-world-signal
// source the plan flags as a future input to this same gate — not folded in
// here; it needs a UNION against cases with an override but no recorded
// outcome yet, which needs live-DB verification before shipping, not a
// blind merge).
//
// Cases with no advisory model opinion (model_tier IS NULL — no tree bundle
// was supplied, or the case predates this migration) are excluded rather
// than counted as disagreement: null means "no opinion to grade", not "the
// model was wrong".

export interface MlAgreementRow {
  actual_severity: string | null;
  case_records: { model_tier: string | null; facility_id: string | null } | null;
}

export interface MlAgreementResult {
  overall_agreement_rate: number | null;
  overall_count: number;
  by_tier: Record<"ROUTINE" | "URGENT" | "EMERGENCY", { agreement_rate: number | null; count: number }>;
}

function rate(agree: number, total: number): number | null {
  return total ? Math.round((agree / total) * 1000) / 1000 : null;
}

export function buildMlAgreement(rows: MlAgreementRow[]): MlAgreementResult {
  const tiers = ["ROUTINE", "URGENT", "EMERGENCY"] as const;
  const byTier: Record<string, { total: number; agree: number }> = {
    ROUTINE: { total: 0, agree: 0 },
    URGENT: { total: 0, agree: 0 },
    EMERGENCY: { total: 0, agree: 0 },
  };
  let overallTotal = 0;
  let overallAgree = 0;

  for (const row of rows) {
    const modelTier = row.case_records?.model_tier ?? null;
    const actual = row.actual_severity;
    if (modelTier !== "ROUTINE" && modelTier !== "URGENT" && modelTier !== "EMERGENCY") continue;
    byTier[modelTier]!.total += 1;
    overallTotal += 1;
    if (actual === modelTier) {
      byTier[modelTier]!.agree += 1;
      overallAgree += 1;
    }
  }

  const byTierResult = {} as MlAgreementResult["by_tier"];
  for (const tier of tiers) {
    byTierResult[tier] = { agreement_rate: rate(byTier[tier]!.agree, byTier[tier]!.total), count: byTier[tier]!.total };
  }

  return {
    overall_agreement_rate: rate(overallAgree, overallTotal),
    overall_count: overallTotal,
    by_tier: byTierResult,
  };
}
