// Ported verbatim from supervisor_routes.py::_aggregate_team_metrics.
// Groups fn_team_metrics rows (phase28_security_definer_fns.sql) by
// submitted_by into per-worker aggregates: submission count,
// needs_review/contraindication/deterioration rates, and triage-tier
// distribution. Pure function so it's testable without a live database.

export interface TeamMetricsRow {
  submitted_by: string | null;
  full_name: string | null;
  triage_level: string | null;
  needs_review: boolean | null;
  contraindication_flags: unknown[] | null;
  deterioration_alert: boolean | null;
}

export interface WorkerAggregate {
  user_id: string;
  full_name: string;
  submission_count: number;
  needs_review_count: number;
  contraindication_flag_count: number;
  deterioration_alert_count: number;
  tier_distribution: { ROUTINE: number; URGENT: number; EMERGENCY: number };
  needs_review_rate: number | null;
  contraindication_flag_rate: number | null;
  deterioration_alert_rate: number | null;
}

function rate(count: number, total: number): number | null {
  return total ? Math.round((count / total) * 1000) / 1000 : null;
}

export function aggregateTeamMetrics(rows: TeamMetricsRow[]): WorkerAggregate[] {
  interface Accum {
    userId: string;
    fullName: string;
    submissionCount: number;
    needsReviewCount: number;
    contraindicationFlagCount: number;
    deteriorationAlertCount: number;
    tierDistribution: { ROUTINE: number; URGENT: number; EMERGENCY: number };
  }

  const workers = new Map<string, Accum>();

  for (const row of rows) {
    const uid = row.submitted_by;
    if (!uid) continue;

    let w = workers.get(uid);
    if (!w) {
      w = {
        userId: uid,
        fullName: row.full_name || "Unknown",
        submissionCount: 0,
        needsReviewCount: 0,
        contraindicationFlagCount: 0,
        deteriorationAlertCount: 0,
        tierDistribution: { ROUTINE: 0, URGENT: 0, EMERGENCY: 0 },
      };
      workers.set(uid, w);
    }

    w.submissionCount += 1;
    if (row.needs_review) w.needsReviewCount += 1;
    if (row.contraindication_flags && row.contraindication_flags.length > 0) w.contraindicationFlagCount += 1;
    if (row.deterioration_alert) w.deteriorationAlertCount += 1;
    const tier = row.triage_level;
    if (tier === "ROUTINE" || tier === "URGENT" || tier === "EMERGENCY") {
      w.tierDistribution[tier] += 1;
    }
  }

  const result: WorkerAggregate[] = [];
  for (const w of workers.values()) {
    const total = w.submissionCount;
    result.push({
      user_id: w.userId,
      full_name: w.fullName,
      submission_count: w.submissionCount,
      needs_review_count: w.needsReviewCount,
      contraindication_flag_count: w.contraindicationFlagCount,
      deterioration_alert_count: w.deteriorationAlertCount,
      tier_distribution: w.tierDistribution,
      needs_review_rate: rate(w.needsReviewCount, total),
      contraindication_flag_rate: rate(w.contraindicationFlagCount, total),
      deterioration_alert_rate: rate(w.deteriorationAlertCount, total),
    });
  }

  result.sort((a, b) => b.submission_count - a.submission_count);
  return result;
}
