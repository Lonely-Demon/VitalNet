// Ported from outbreak_routes.py's _compute_ears_signals: the CDC EARS
// C2 method (DECISIONS.md #26, ADR §54) — a 7-day trailing baseline mean and
// SAMPLE standard deviation (Bessel's correction, matching Python's
// statistics.stdev, NOT population stddev), with a 2-day guard band [t-9 .. t-3]
// to prevent outbreak ramp-up self-masking, and Empirical Bayes Poisson
// variance floor sigma_eff = max(s, sqrt(max(mu, 0.25)), 0.50).
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
  effective_sigma: number;
  threshold: number;
  z_score: number;
}

export const BASELINE_DAYS = 7;
export const GUARD_BAND_DAYS = 2;
export const MIN_FLOOR = 3;
export const MIN_STDDEV_FLOOR = 0.5;
export const Z_MULTIPLIER = 3;

/**
 * Converts ISO UTC timestamp to Indian Standard Time (UTC+05:30) date string YYYY-MM-DD
 */
export function toIstDayBucket(isoTimestamp: string): string {
  const date = new Date(isoTimestamp);
  if (isNaN(date.getTime())) {
    return isoTimestamp.slice(0, 10);
  }
  // Offset by +5 hours 30 minutes in milliseconds (19800000 ms)
  const istTime = new Date(date.getTime() + 5.5 * 3600 * 1000);
  return istTime.toISOString().slice(0, 10);
}

function mean(values: number[]): number {
  if (values.length === 0) return 0.0;
  return values.reduce((a, b) => a + b, 0) / values.length;
}

/** Sample standard deviation (n-1 denominator) — matches Python's statistics.stdev. */
function sampleStdev(values: number[]): number {
  if (values.length <= 1) return 0.0;
  const m = mean(values);
  const variance = values.reduce((sum, v) => sum + (v - m) ** 2, 0) / (values.length - 1);
  return Math.sqrt(variance);
}

export function computeSampleStats(values: number[]): { mean: number; stdDev: number } {
  const n = values.length;
  if (n === 0) return { mean: 0, stdDev: 0 };
  const m = mean(values);
  const stdDev = sampleStdev(values);
  return { mean: m, stdDev };
}

export function computeEarsC2Signal(
  dailyHistory: number[],
  todayCount: number,
  options: { useGuardBand?: boolean; minStdDevFloor?: number } = {},
) {
  const useGuardBand = options.useGuardBand !== false;
  const historyLen = dailyHistory.length;

  let baselineWindow: number[];
  let effectiveGuardBand = 0;

  if (useGuardBand && historyLen >= BASELINE_DAYS + GUARD_BAND_DAYS) {
    // Window [t-9 .. t-3] (skipping t-2 and t-1)
    const startIdx = historyLen - (BASELINE_DAYS + GUARD_BAND_DAYS);
    const endIdx = historyLen - GUARD_BAND_DAYS;
    baselineWindow = dailyHistory.slice(startIdx, endIdx);
    effectiveGuardBand = GUARD_BAND_DAYS;
  } else {
    // Fallback window [t-7 .. t-1] (skipping 0 days)
    const startIdx = Math.max(0, historyLen - BASELINE_DAYS);
    baselineWindow = dailyHistory.slice(startIdx, historyLen);
    effectiveGuardBand = 0;
  }

  const { mean: baselineMean, stdDev: sSample } = computeSampleStats(baselineWindow);

  // Empirical Bayes Poisson-bounded variance floor
  const poissonStdDev = Math.sqrt(Math.max(baselineMean, 0.25));
  const minFloor = options.minStdDevFloor ?? MIN_STDDEV_FLOOR;
  const effSigma = Math.max(sSample, poissonStdDev, minFloor);

  // Eligibility condition: todayCount >= 3
  const isEligible = todayCount >= MIN_FLOOR;

  // Standard threshold
  const threshold = baselineMean + Z_MULTIPLIER * sSample;

  // Signal condition
  const isOutbreak = isEligible && todayCount > threshold;

  // Stabilized z-score
  const zScore = Math.round(((todayCount - baselineMean) / effSigma) * 100) / 100;

  return {
    todayCount,
    baselineMean: round2(baselineMean),
    baselineStdDev: round2(sSample),
    effectiveSigma: round2(effSigma),
    threshold: round2(threshold),
    zScore,
    isOutbreak,
    isEligible,
    effectiveGuardBand,
    baselineWindow,
  };
}

function round2(n: number): number {
  return Math.round(n * 100) / 100;
}

interface Bucket {
  facilityId: string;
  symptom: string;
  dayCounts: Map<string, number>;
}

/** `today` is a YYYY-MM-DD date string. `rows` spans history rows. */
export function computeEarsSignals(rows: EarsRow[], today: string, useGuardBand = true): EarsSignal[] {
  const buckets: Bucket[] = [];
  const bucketIndex = new Map<string, Map<string, Bucket>>();
  let earliestDate: Date | null = null;

  for (const row of rows) {
    const facilityId = row.facility_id;
    const day = row.created_at ? toIstDayBucket(row.created_at) : "";
    if (!facilityId || !day) continue;

    const d = new Date(day + "T00:00:00Z");
    if (!isNaN(d.getTime())) {
      if (!earliestDate || d < earliestDate) {
        earliestDate = d;
      }
    }

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
  const historyLenDays = earliestDate
    ? Math.round((todayDate.getTime() - earliestDate.getTime()) / (24 * 3600 * 1000))
    : 0;

  const effectiveGuard = (useGuardBand && historyLenDays >= BASELINE_DAYS + GUARD_BAND_DAYS) ? GUARD_BAND_DAYS : 0;

  const baselineDays: string[] = [];
  const startOffset = effectiveGuard === GUARD_BAND_DAYS ? 1 + GUARD_BAND_DAYS : 1;
  const endOffset = effectiveGuard === GUARD_BAND_DAYS ? BASELINE_DAYS + GUARD_BAND_DAYS : BASELINE_DAYS;

  for (let i = startOffset; i <= endOffset; i++) {
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
    const poissonStddev = Math.sqrt(Math.max(baselineMean, 0.25));
    const effSigma = Math.max(baselineStddev, poissonStddev, MIN_STDDEV_FLOOR);
    const threshold = baselineMean + Z_MULTIPLIER * baselineStddev;

    if (todayCount > threshold) {
      const zScore = round2((todayCount - baselineMean) / effSigma);
      signals.push({
        facility_id: bucket.facilityId,
        symptom: bucket.symptom,
        today_count: todayCount,
        baseline_mean: round2(baselineMean),
        baseline_stddev: round2(baselineStddev),
        effective_sigma: round2(effSigma),
        threshold: round2(threshold),
        z_score: zScore,
      });
    }
  }

  signals.sort((a, b) => b.today_count - a.today_count);
  return signals;
}
