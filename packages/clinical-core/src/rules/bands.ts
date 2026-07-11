// NEWS2 (Royal College of Physicians, 2017) / qSOFA (Sepsis-3, Singer et al.
// 2016) / PALS (Pediatric Advanced Life Support, APLS/PALS reference ranges)
// -informed vital-sign scoring. Promoted from what was previously a
// training-label-only scorer (backend/scripts/train_classifier.py) into the
// PRIMARY, inference-time triage decision — see engine.ts and DECISIONS §33.
//
// Every scoring function here is deterministic and pure. A missing (None)
// vital scores 0 — you cannot penalise a measurement that was never taken;
// this is the common rural reality (no BP cuff / pulse oximeter).

export type Band = readonly [lo: number, hi: number, score: number];

/** bands: ascending (lo, hi, score) triples covering -Infinity..Infinity.
 * Falling outside every defined band scores 3 (treat as most severe). */
export function bandScore(value: number | null, bands: readonly Band[]): number {
  if (value === null) return 0;
  for (const [lo, hi, score] of bands) {
    if (lo <= value && value < hi) return score;
  }
  return 3;
}

/** NEWS2 SpO2 scale 1 bands (Royal College of Physicians, 2017). */
export const SPO2_BANDS: readonly Band[] = [
  [-1, 91, 3],
  [91, 93, 2],
  [93, 95, 1],
  [95, 1000, 0],
];

/**
 * NEWS2's own systolic-BP band treats the entire 111-219 range as "0"
 * because NEWS2 targets acute deterioration, where hypotension is the
 * dangerous direction. That underweights hypertensive crisis (a real,
 * distinct emergency pathway — hypertensive encephalopathy/stroke risk)
 * this app must also catch, so the upper band is tightened here relative to
 * plain NEWS2.
 */
export const BP_SYS_BANDS: readonly Band[] = [
  [-1, 91, 3],
  [91, 101, 2],
  [101, 111, 1],
  [111, 180, 0],
  [180, 200, 2],
  [200, 10000, 3],
];

export const TEMP_BANDS: readonly Band[] = [
  [-1, 35.1, 3],
  [35.1, 36.1, 1],
  [36.1, 38.1, 0],
  [38.1, 39.1, 1],
  [39.1, 100, 2],
];

export const ADULT_HR_BANDS: readonly Band[] = [
  [-1, 41, 3],
  [41, 51, 1],
  [51, 91, 0],
  [91, 111, 1],
  [111, 131, 2],
  [131, 1000, 3],
];

export function spo2Score(spo2: number | null): number {
  return bandScore(spo2, SPO2_BANDS);
}

export function bpSysScore(bpSys: number | null): number {
  return bandScore(bpSys, BP_SYS_BANDS);
}

export function tempScore(temp: number | null): number {
  return bandScore(temp, TEMP_BANDS);
}

export function adultHrScore(hr: number | null): number {
  return bandScore(hr, ADULT_HR_BANDS);
}

/** Age-banded HR normal ranges — standard APLS/PALS reference ranges. */
export function pediatricHrScore(age: number, hr: number | null): number {
  if (hr === null) return 0;
  let normal: [number, number];
  let mild: [number, number];
  if (age < 1) {
    normal = [100, 160];
    mild = [90, 180];
  } else if (age < 2) {
    normal = [90, 150];
    mild = [80, 170];
  } else if (age < 5) {
    normal = [80, 140];
    mild = [70, 160];
  } else if (age < 12) {
    normal = [70, 120];
    mild = [60, 140];
  } else {
    return adultHrScore(hr);
  }
  if (normal[0] <= hr && hr <= normal[1]) return 0;
  if (mild[0] <= hr && hr <= mild[1]) return 1;
  return 3; // outside the "mild" band entirely — significant tachy/bradycardia for age
}

/**
 * Age-banded systolic-BP scoring. A normal infant's systolic BP (~80-95) is
 * "hypotensive" by adult bands, so scoring it with bpSysScore labels a
 * perfectly healthy infant EMERGENCY (the documented over-triage fixed in
 * ML v3.1.0 / DECISIONS §31). Thresholds use the standard PALS
 * 5th-percentile hypotension definition:
 *   neonate (<1mo):  SBP < 60
 *   infant (1-12mo): SBP < 70
 *   child (1-<12yr): SBP < 70 + 2*age
 * Adolescents (>=12) fall back to the adult bands (adult hypotension applies).
 */
export function pediatricBpScore(age: number, bpSys: number | null): number {
  if (bpSys === null) return 0;
  if (age >= 12) return bpSysScore(bpSys);
  const hypo = age < 1 / 12 ? 60 : age < 1 ? 70 : 70 + 2 * age;
  if (bpSys < hypo) return 3; // frank hypotension for age
  if (bpSys < hypo + 8) return 2; // borderline-low for age
  if (bpSys < hypo + 15) return 1;
  if (bpSys >= 140) return 2; // paediatric hypertension is genuinely concerning
  return 0;
}

/** Fever in infants is weighted more heavily — neonatal fever is a medical
 * emergency even without other signs (see rules.ts::isNeonatalFever). */
export function pediatricTempScore(age: number, temp: number | null): number {
  if (temp === null) return 0;
  if (age < 0.25) return temp >= 38.0 ? 3 : tempScore(temp); // < 3 months
  if (age < 2) return temp >= 39.0 ? 2 : tempScore(temp);
  return tempScore(temp);
}

export interface News2Result {
  aggregate: number;
  worstSingle: number;
  spo2Score: number;
  bpScore: number;
  tempScore: number;
  hrScore: number;
}

/** Aggregate 0-15+ vital-derangement score. Age-adjusted for paediatrics. */
export function news2LikeScore(
  age: number,
  bpSys: number | null,
  hr: number | null,
  spo2: number | null,
  temp: number | null,
): News2Result {
  const spo2S = spo2Score(spo2);
  const bpS = age < 18 ? pediatricBpScore(age, bpSys) : bpSysScore(bpSys);
  let tempS = age < 18 ? pediatricTempScore(age, temp) : tempScore(temp);
  const hrS = age < 18 ? pediatricHrScore(age, hr) : adultHrScore(hr);

  // Elderly patients often mount a blunted fever response — a "normal"
  // temperature in a frail elderly patient with other derangement is not
  // reassuring the way it is in a young adult.
  if (age >= 65 && temp !== null && temp < 36.5) {
    tempS = Math.max(tempS, 1);
  }

  return {
    aggregate: spo2S + bpS + tempS + hrS,
    worstSingle: Math.max(spo2S, bpS, tempS, hrS),
    spo2Score: spo2S,
    bpScore: bpS,
    tempScore: tempS,
    hrScore: hrS,
  };
}

/**
 * Simplified qSOFA (respiratory rate is not collected by VitalNet's intake
 * form, so this uses the two available qSOFA criteria). qSOFA is validated
 * for ADULTS; SBP<=100 is normal for a young child, so the hypotension
 * criterion is only applied at age>=12 (altered mentation is concerning at
 * any age).
 */
export function qsofaScore(bpSys: number | null, alteredConsciousness: boolean, age: number): number {
  let score = 0;
  if (age >= 12 && bpSys !== null && bpSys <= 100) score += 1;
  if (alteredConsciousness) score += 1;
  return score;
}
