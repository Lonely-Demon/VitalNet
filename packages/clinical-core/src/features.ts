// 43-feature clinical feature engineering — ported from
// backend/app/ml/clinical_features.py::ClinicalFeatureEngineer (itself
// already 1:1 mirrored as frontend/src/utils/triageClassifier.js::
// buildFeatureMap before this migration). Used ONLY to build the advisory
// ML model's input vector (see treeEvaluator.ts, triage.ts) — the
// authoritative tier decision comes from rules/engine.ts, not this.

export interface FeatureFormInput {
  // Always a real number at the schema level (schema.ts requires it) —
  // matches EngineInput/OverrideInput's patient_age exactly so
  // TriageFormInput (triage.ts) can extend both without conflict.
  patient_age: number;
  patient_sex: "male" | "female" | "other" | null;
  bp_systolic: number | null;
  bp_diastolic: number | null;
  spo2: number | null;
  heart_rate: number | null;
  temperature: number | null;
  symptoms: readonly string[];
  chief_complaint: string | null;
  complaint_duration: string | null;
  location: string | null;
  known_conditions: string | null;
  /** Training/test-fixture-only field (mirrors ClinicalFeatureEngineer's
   * reference_month param). A real intake submission never sets it, so
   * live triage always falls back to the real current month. */
  _reference_month?: number;
}

export type FeatureMap = Record<string, number>;

const HIGH_RISK_COMPLAINTS = new Set([
  "chest pain",
  "chest tightness",
  "difficulty breathing",
  "breathlessness",
  "altered consciousness",
  "confusion",
  "severe bleeding",
  "seizure",
  "unconscious",
]);

const TRAUMA_INDICATORS = new Set(["injury", "trauma", "fall", "accident", "hit", "cut", "burned", "fracture", "wound"]);

const OBSTETRIC_COMPLAINTS = new Set(["pregnancy", "pregnant", "delivery", "labor", "bleeding", "contractions", "baby", "birth"]);

const CRITICAL_SYMPTOMS = [
  "chest_pain",
  "breathlessness",
  "altered_consciousness",
  "severe_bleeding",
  "seizure",
  "high_fever",
] as const;

const SYMPTOM_SEVERITY_WEIGHTS: Record<string, number> = {
  altered_consciousness: 4.0,
  severe_bleeding: 4.0,
  seizure: 4.0,
  chest_pain: 3.0,
  breathlessness: 3.0,
  high_fever: 2.0,
};

function containsAny(text: string, termSet: ReadonlySet<string>): boolean {
  const lower = text.toLowerCase();
  for (const term of termSet) {
    if (lower.includes(term)) return true;
  }
  return false;
}

/**
 * Compute the clinical feature map from IntakeForm-shaped data. Key names
 * MUST match the trained model's feature names exactly — the assembly
 * ORDER is handled separately by orderFeatureVector() using
 * features_config.json, so key order in the returned object is not
 * load-bearing.
 */
export function buildFeatureMap(formData: FeatureFormInput): FeatureMap {
  const symptoms = formData.symptoms || [];
  const age = formData.patient_age ?? -1;
  const sex = formData.patient_sex === "male" ? 1 : 0;
  const bpSys = formData.bp_systolic ?? -1;
  const bpDia = formData.bp_diastolic ?? -1;
  const spo2 = formData.spo2 ?? -1;
  const hr = formData.heart_rate ?? -1;
  const temp = formData.temperature ?? -1;
  const complaint = (formData.chief_complaint || "").toLowerCase();
  const duration = (formData.complaint_duration || "").toLowerCase();
  const location = (formData.location || "").toLowerCase();
  const conditions = (formData.known_conditions || "").toLowerCase();

  const safeBpSys = bpSys > 0 ? bpSys : 120;
  const safeBpDia = bpDia > 0 ? bpDia : 80;
  const safeHr = hr > 0 ? hr : 75;
  const safeSpo2 = spo2 > 0 ? spo2 : 97;
  const safeTemp = temp > 0 ? temp : 37.0;
  const safeAge = age > 0 ? age : 40;
  // Only defaults age to 40 when the field is truly absent, NOT when it's a
  // real 0 (a newborn) — matches the corresponding Python `.get(..., 40)`
  // pattern exactly (a naive falsy-clamp here misclassifies real newborns
  // as 40-year-old adults for every age-gated risk score below).
  const ageOrDefault = formData.patient_age === null || formData.patient_age === undefined ? 40 : formData.patient_age;

  const chestPain = symptoms.includes("chest_pain") ? 1 : 0;
  const breathlessness = symptoms.includes("breathlessness") ? 1 : 0;
  const alteredConsciousness = symptoms.includes("altered_consciousness") ? 1 : 0;
  const severeBleeding = symptoms.includes("severe_bleeding") ? 1 : 0;
  const seizure = symptoms.includes("seizure") ? 1 : 0;
  const highFever = symptoms.includes("high_fever") ? 1 : 0;
  const symptomCount = CRITICAL_SYMPTOMS.filter((s) => symptoms.includes(s)).length;

  // Vital sign derived features — gated on the SAFE (already-defaulted)
  // values, matching the Python source exactly.
  const pulsePressure = safeBpSys > 0 && safeBpDia > 0 ? safeBpSys - safeBpDia : 40;
  const meanArterialPressure = safeBpSys > 0 && safeBpDia > 0 ? (safeBpSys + 2 * safeBpDia) / 3 : 93;
  const shockIndex = safeBpSys > 0 && safeHr > 0 ? safeHr / safeBpSys : 0.6;
  const spo2AgeRatio = safeSpo2 > 0 && safeAge > 0 ? safeSpo2 / Math.max(safeAge, 1) : 2.4;
  const tempDeviation = safeTemp > 0 ? Math.abs(safeTemp - 37.0) : 0.0;

  let cardiacRisk = 0;
  if (ageOrDefault > 65) cardiacRisk += 2;
  else if (ageOrDefault > 45) cardiacRisk += 1;
  if (safeBpSys > 160) cardiacRisk += 2;
  if (safeHr > 100 || safeHr < 60) cardiacRisk += 1.5;
  if (chestPain) cardiacRisk += 3;
  if (breathlessness) cardiacRisk += 1.5;
  cardiacRisk = Math.min(cardiacRisk, 10);

  let respDistress = 0;
  if (safeSpo2 < 90) respDistress += 4;
  else if (safeSpo2 < 94) respDistress += 2;
  if (safeHr > 110) respDistress += 1.5;
  if (breathlessness) respDistress += 3;

  let hemodynamic = 0;
  if (safeBpSys < 90) hemodynamic += 4;
  else if (safeBpSys > 180) hemodynamic += 2;
  if (safeHr > 130) hemodynamic += 3;
  else if (safeHr < 50) hemodynamic += 2;
  if (safeBpSys > 0) {
    const si = safeHr / safeBpSys;
    if (si > 1.0) hemodynamic += 3;
    else if (si > 0.8) hemodynamic += 1.5;
  }

  let sepsisRisk = 0;
  if (safeTemp > 38.0 || safeTemp < 36.0) sepsisRisk += 1;
  if (safeBpSys < 100) sepsisRisk += 2;
  if (safeHr > 90) sepsisRisk += 1;
  if (alteredConsciousness) sepsisRisk += 2;
  if (highFever) sepsisRisk += 1.5;

  let pediatricAdj = 0;
  if (ageOrDefault < 18) {
    if (ageOrDefault < 2) {
      if (safeHr > 160 || safeHr < 100) pediatricAdj += 2;
    } else if (ageOrDefault < 6) {
      if (safeHr > 140 || safeHr < 80) pediatricAdj += 1.5;
    } else if (ageOrDefault < 12) {
      if (safeHr > 120 || safeHr < 70) pediatricAdj += 1;
    }
    if (safeTemp > 38.5) pediatricAdj += 2;
  }

  let geriatricAdj = 0;
  if (ageOrDefault >= 65) {
    if (safeTemp < 36.5) geriatricAdj += 1.5;
    if (safeBpSys < 100) geriatricAdj += 2;
    if (ageOrDefault > 80) geriatricAdj += 1;
  }

  let pregnancyAdj = 0;
  if (formData.patient_sex === "female" && ageOrDefault >= 15 && ageOrDefault <= 45) {
    if (conditions.includes("pregnan") || conditions.includes("expecting")) pregnancyAdj += 1;
    if (containsAny(complaint, OBSTETRIC_COMPLAINTS)) pregnancyAdj += 2;
  }

  const cardiopulmonaryCluster = chestPain * breathlessness;
  const neurologicalCluster = alteredConsciousness * seizure;
  const hemorrhagicCluster = severeBleeding * (safeBpSys < 90 ? 1 : 0);
  const infectiousCluster = highFever * symptoms.length;

  let symptomSeverity = 0;
  for (const s of symptoms) {
    symptomSeverity += SYMPTOM_SEVERITY_WEIGHTS[s] ?? 1.0;
  }
  symptomSeverity = Math.min(symptomSeverity, 15);

  let durationRisk = 1.5;
  if (duration.includes("less than 1 hour") || duration.includes("< 1 hour")) durationRisk = 3.0;
  else if (duration.includes("1") && duration.includes("6 hour")) durationRisk = 2.5;
  else if (duration.includes("6") && duration.includes("24 hour")) durationRisk = 2.0;
  else if (duration.includes("1") && duration.includes("3 day")) durationRisk = 1.5;
  else if (duration.includes("more than 3 day") || duration.includes("> 3 day")) durationRisk = 1.0;

  let complaintRisk = 1.0;
  if (containsAny(complaint, HIGH_RISK_COMPLAINTS)) complaintRisk = 4.0;
  else if (containsAny(complaint, TRAUMA_INDICATORS)) complaintRisk = 3.0;

  let comorbidityMult = 1.0;
  if (conditions) {
    const highRiskConditions = ["diabetes", "heart", "cardiac", "hypertension", "kidney", "renal", "copd", "asthma", "cancer", "stroke", "liver"];
    let riskCount = 0;
    for (const c of highRiskConditions) {
      if (conditions.includes(c)) riskCount++;
    }
    comorbidityMult = Math.min(1.0 + riskCount * 0.5, 3.0);
  }

  let pediatricFeverRisk = 0;
  if (ageOrDefault < 18) {
    if (ageOrDefault < 0.25 && safeTemp > 38.0) pediatricFeverRisk += 4;
    else if (ageOrDefault < 2 && safeTemp > 39.0) pediatricFeverRisk += 3;
    else if (safeTemp > 40.0) pediatricFeverRisk += 2;
    if (highFever) pediatricFeverRisk += 1;
  }

  let elderlyFallRisk = 0;
  if (ageOrDefault >= 65) {
    if (ageOrDefault > 75) elderlyFallRisk += 1;
    if (ageOrDefault > 85) elderlyFallRisk += 2;
    const fallKeywords = ["fall", "fell", "slip", "trip", "dizzy", "weakness"];
    if (fallKeywords.some((k) => complaint.includes(k))) elderlyFallRisk += 3;
  }

  let adultCardiacRisk = 0;
  if (ageOrDefault >= 18 && ageOrDefault <= 65) {
    adultCardiacRisk = cardiacRisk * 0.8;
  }

  let obstetricRisk = 0;
  if (formData.patient_sex === "female" && ageOrDefault >= 15 && ageOrDefault <= 45) {
    for (const term of OBSTETRIC_COMPLAINTS) {
      if (complaint.includes(term)) {
        obstetricRisk += 2;
        break;
      }
    }
    if (complaint.includes("bleeding")) obstetricRisk += 1.5;
  }

  let traumaSeverity = 0;
  for (const term of TRAUMA_INDICATORS) {
    if (complaint.includes(term)) {
      traumaSeverity += 2;
      break;
    }
  }
  if (safeBpSys < 90) traumaSeverity += 3;
  if (safeHr > 120) traumaSeverity += 2;

  let mentalHealthCrisis = 0;
  const mhTerms = ["suicid", "depress", "anxiety", "panic", "psycho", "mental", "confused", "agitat", "violent"];
  for (const term of mhTerms) {
    if (complaint.includes(term)) {
      mentalHealthCrisis += 2;
      break;
    }
  }
  if (alteredConsciousness) mentalHealthCrisis += 1;

  // time_of_day_risk and epidemic_alert_level were removed (DECISIONS §23):
  // both were constant across the entire training set, so the tree ensemble
  // could never learn a split on either.
  const month = formData._reference_month ?? new Date().getMonth() + 1; // 1-indexed
  let seasonalRisk = 1.0;
  if ([6, 7, 8, 9].includes(month)) seasonalRisk = 1.3; // India's monsoon — dengue/malaria/leptospirosis surge
  else if ([5, 10].includes(month)) seasonalRisk = 1.1; // pre-/post-monsoon shoulder months

  const ruralTerms = ["village", "rural", "remote", "tribal"];
  const urbanTerms = ["city", "town", "urban", "metro"];
  const ruralOrTribal = ruralTerms.some((t) => location.includes(t));
  const geographicRisk = ruralOrTribal ? 1.2 : 1.0;

  let healthcareAccessibility = 0.7;
  if (ruralOrTribal) healthcareAccessibility = 0.5;
  else if (urbanTerms.some((t) => location.includes(t))) healthcareAccessibility = 1.0;

  return {
    age,
    sex,
    bp_systolic: bpSys,
    bp_diastolic: bpDia,
    spo2,
    heart_rate: hr,
    temperature: temp,
    symptom_count: symptomCount,
    chest_pain: chestPain,
    breathlessness,
    altered_consciousness: alteredConsciousness,
    severe_bleeding: severeBleeding,
    seizure,
    high_fever: highFever,
    pulse_pressure: pulsePressure,
    mean_arterial_pressure: meanArterialPressure,
    shock_index: shockIndex,
    spo2_age_ratio: spo2AgeRatio,
    temp_deviation: tempDeviation,
    cardiac_risk_score: cardiacRisk,
    respiratory_distress_score: respDistress,
    hemodynamic_instability: hemodynamic,
    sepsis_risk_score: sepsisRisk,
    pediatric_adjustment: pediatricAdj,
    geriatric_adjustment: geriatricAdj,
    pregnancy_adjustment: pregnancyAdj,
    cardiopulmonary_cluster: cardiopulmonaryCluster,
    neurological_cluster: neurologicalCluster,
    hemorrhagic_cluster: hemorrhagicCluster,
    infectious_cluster: infectiousCluster,
    symptom_severity_score: symptomSeverity,
    symptom_duration_risk: durationRisk,
    chief_complaint_risk: complaintRisk,
    comorbidity_multiplier: comorbidityMult,
    pediatric_fever_risk: pediatricFeverRisk,
    elderly_fall_risk: elderlyFallRisk,
    adult_cardiac_risk: adultCardiacRisk,
    obstetric_emergency_risk: obstetricRisk,
    trauma_severity_score: traumaSeverity,
    mental_health_crisis: mentalHealthCrisis,
    seasonal_risk: seasonalRisk,
    geographic_risk: geographicRisk,
    healthcare_accessibility: healthcareAccessibility,
  };
}

/** Assemble the ordered plain-number array using the canonical feature
 * order from features_config.json. */
export function orderFeatureVector(featureMap: FeatureMap, featureNames: readonly string[]): number[] {
  return featureNames.map((name) => {
    const v = featureMap[name];
    return typeof v === "number" ? v : 0;
  });
}
