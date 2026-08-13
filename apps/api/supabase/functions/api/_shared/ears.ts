// Ported from outbreak_routes.py's _compute_ears_signals: the CDC EARS
// C1 method (DECISIONS.md #26) - a 7-day trailing baseline mean and
// SAMPLE standard deviation (Bessel's correction, matching Python's
// statistics.stdev, NOT population stddev), flagging today's count when
// it exceeds baseline_mean + 3*baseline_stddev, gated by a minimum floor
// so a jump from 0 to 1 case in a tiny population is never flagged.
// Informational aid for a human to review, not a validated public-health
// surveillance system.

export interface EarsRow {
  facility_id: string | null;
  symptoms: string[] | null;
  created_at: string | null;
}

export interface EarsSignal {
  facility_id: string;
  symptom: string;
  today_count: number;
  baseline_mean: number;
  baseline_stddev: number;
  threshold: number;
}

export const BASELINE_DAYS = 7;
export const MIN_FLOOR = 3;
export const Z_MULTIPLIER = 3;

function dayBucket(createdAt: string): string {
  return createdAt.slice(0, 10);
}

function mean(values: number[]): number {
  return values.reduce((a, b) => a + b, 0) / values.length;
}

/** Sample standard deviation (n-1 denominator) - matches Python's statistics.stdev. */
function sampleStdev(values: number[]): number {
  if (values.length <= 1) return 0.0;
  const m = mean(values);
  const variance = values.reduce((sum, v) => sum + (v - m) ** 2, 0) / (values.length - 1);
  return Math.sqrt(variance);
}

function round2(n: number): number {
  return Math.round(n * 100) / 100;
}

interface Bucket {
  facilityId: string;
  symptom: string;
  dayCounts: Map<string, number>;
}

/** `today` is a YYYY-MM-DD date string. `rows` must span at least BASELINE_DAYS+1 trailing days. */
export function computeEarsSignals(rows: EarsRow[], today: string): EarsSignal[] {
  const buckets: Bucket[] = [];
  const bucketIndex = new Map<string, Map<string, Bucket>>();

  for (const row of rows) {
    const facilityId = row.facility_id;
    const day = row.created_at ? dayBucket(row.created_at) : "";
    if (!facilityId || !day) continue;

    let bySymptom = bucketIndex.get(facilityId);
    if (!bySymptom) {
      bySymptom = new Map();
      bucketIndex.set(facilityId, bySymptom);
    }

    for (const symptom of row.symptoms ?? []) {
      let bucket = bySymptom.get(symptom);
      if (!bucket) {
        bucket = { facilityId, symptom, dayCounts: new Map() };
        bySymptom.set(symptom, bucket);
        buckets.push(bucket);
      }
      bucket.dayCounts.set(day, (bucket.dayCounts.get(day) ?? 0) + 1);
    }
  }

  const todayDate = new Date(today + "T00:00:00Z");
  const baselineDays: string[] = [];
  for (let i = 1; i <= BASELINE_DAYS; i++) {
    const d = new Date(todayDate);
    d.setUTCDate(d.getUTCDate() - i);
    baselineDays.push(d.toISOString().slice(0, 10));
  }

  const signals: EarsSignal[] = [];
  for (const bucket of buckets) {
    const todayCount = bucket.dayCounts.get(today) ?? 0;
    if (todayCount < MIN_FLOOR) continue;

    const baselineCounts = baselineDays.map((d) => bucket.dayCounts.get(d) ?? 0);
    const baselineMean = mean(baselineCounts);
    const baselineStddev = sampleStdev(baselineCounts);
    const threshold = baselineMean + Z_MULTIPLIER * baselineStddev;

    if (todayCount > threshold) {
      signals.push({
        facility_id: bucket.facilityId,
        symptom: bucket.symptom,
        today_count: todayCount,
        baseline_mean: round2(baselineMean),
        baseline_stddev: round2(baselineStddev),
        threshold: round2(threshold),
      });
    }
  }

  signals.sort((a, b) => b.today_count - a.today_count);
  return signals;
}
