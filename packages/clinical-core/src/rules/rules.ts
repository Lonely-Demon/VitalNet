// Deterministic override rules — the layer that ALWAYS wins over both the
// aggregate NEWS2/qSOFA scorer (engine.ts) and the advisory ML model
// (treeEvaluator.ts). Ported from backend/app/ml/classifier.py's
// _safety_net_check (extreme-presentation overrides) and the pregnancy rule
// added in DECISIONS §30. Every rule below is unconditional: if it fires,
// the tier is EMERGENCY, full stop — see engine.ts's "floors only raise,
// overrides always win" invariant.

import type { Symptom } from "../schema.js";

export interface FiredRule {
  id: string;
  citation: string;
  detail: string;
}

export interface OverrideInput {
  patient_age: number;
  age_months?: number | null;
  bp_systolic: number | null;
  bp_diastolic: number | null;
  spo2: number | null;
  heart_rate: number | null;
  temperature: number | null;
  symptoms: readonly string[];
  is_pregnant?: boolean | null;
}

/**
 * Resolves effective age in years, accounting for infant age specified in months.
 * Formula: fractional years (age_months / 12) when patient_age < 2 && age_months != null.
 */
export function resolveEffectiveAge(
  patient_age?: number | null,
  age_months?: number | null,
): number | null {
  if (patient_age !== null && patient_age !== undefined && patient_age < 2 && age_months !== null && age_months !== undefined) {
    return age_months / 12;
  }
  if (patient_age !== null && patient_age !== undefined) {
    return Number(patient_age);
  }
  if (age_months !== null && age_months !== undefined) {
    return age_months / 12;
  }
  return null;
}

const CRITICAL_SYMPTOMS_OVERRIDE = new Set<Symptom>([
  "altered_consciousness",
  "seizure",
  "severe_bleeding",
  "swelling_face_throat",
]);

const HYPERTENSIVE_NEURO = new Set<Symptom>([
  "severe_headache",
  "weakness_one_side",
  "difficulty_speaking",
  "altered_consciousness",
]);

/** Severe features of preeclampsia this app can actually observe (ACOG
 * Practice Bulletin 222) — used only alongside is_pregnant + a
 * preeclampsia-range BP reading. */
const PREECLAMPSIA_SEVERE_SYMPTOMS = new Set<Symptom>(["severe_headache", "severe_abdominal_pain"]);

/** 'altered_consciousness' -> 'altered consciousness', comma-joined, sorted. */
function readable(codes: Iterable<string>): string {
  return [...codes]
    .map((s) => s.replace(/_/g, " "))
    .sort()
    .join(", ");
}

/** Heart rate extreme emergency thresholds (WHO / PALS bradycardia & severe tachycardia) */
function hrEmergencyThreshold(ageYears: number): { low: number; high: number } {
  if (ageYears < 0.25) return { low: 30, high: 220 };  // Neonate (<3 mo)
  if (ageYears < 1)    return { low: 30, high: 200 };  // Infant (3-12 mo)
  if (ageYears < 3)    return { low: 30, high: 180 };  // Toddler (1-3 yr)
  if (ageYears < 5)    return { low: 30, high: 170 };  // Preschool (3-5 yr)
  if (ageYears < 12)   return { low: 30, high: 160 };  // School age (5-12 yr)
  if (ageYears < 18)   return { low: 35, high: 150 };  // Adolescent (12-18 yr)
  return { low: 35, high: 170 };                       // Adult (>18 yr)
}

/** Systolic BP extreme emergency thresholds (PALS 5th percentile hypotension / crisis) */
function bpEmergencyThreshold(ageYears: number): { low: number; high: number } {
  if (ageYears < 0.08) return { low: 60, high: 220 };  // Neonate (<1 mo)
  if (ageYears < 1)    return { low: 70, high: 220 };  // Infant (1-12 mo)
  if (ageYears < 5)    return { low: 75, high: 220 };  // Toddler/Preschool (1-5 yr)
  if (ageYears < 10)   return { low: 80, high: 220 };  // Child (5-10 yr)
  if (ageYears < 18)   return { low: 85, high: 220 };  // Adolescent (10-18 yr)
  return { low: 90, high: 220 };                       // Adult (>18 yr)
}

/** Body temperature extreme emergency thresholds */
function tempEmergencyThreshold(ageYears: number): { low: number; high: number } {
  if (ageYears < 5) return { low: 33.0, high: 41.0 };
  return { low: 33.0, high: 41.5 };
}

/**
 * Extreme-presentation safety-net overrides. Returns a FiredRule (→ always
 * EMERGENCY) or null if none fired. Evaluates all override rules to maintain
 * complete audit fidelity (VN-2026-08-C6-02).
 */
export function checkOverrides(form: OverrideInput): FiredRule | null {
  const allFired: FiredRule[] = [];
  const symptoms = new Set(form.symptoms);
  const hits = [...symptoms].filter((s) => CRITICAL_SYMPTOMS_OVERRIDE.has(s as Symptom));
  if (hits.length) {
    allFired.push({
      id: "critical_symptom_override",
      citation: "NEWS2 'any red parameter' principle extended to symptoms with no safe vital-sign proxy",
      detail: `Critical symptom present: ${readable(hits)}`,
    });
  }

  const effectiveAge = resolveEffectiveAge(form.patient_age, form.age_months);
  const age = effectiveAge ?? form.patient_age;
  const { temperature: temp } = form;
  if (age < 0.25 && temp !== null && temp >= 38.0) {
    allFired.push({
      id: "neonatal_fever",
      citation: "Neonatal fever (<3 months, temp >=38.0C) is a medical emergency regardless of other signs",
      detail: `Neonatal fever (age ${Math.round(age * 12)} months, temperature ${temp}C)`,
    });
  }

  const { spo2, heart_rate: hr, bp_systolic: bpSys } = form;
  if (spo2 !== null && spo2 < 85) {
    allFired.push({
      id: "extreme_spo2",
      citation: "NEWS2 scale 1: SpO2 <91 is red-flag territory; <85 is unambiguous critical hypoxia",
      detail: `Critically low oxygen saturation (${spo2}%)`,
    });
  }

  if (hr !== null) {
    const hrBounds = hrEmergencyThreshold(age);
    if (hr < hrBounds.low || hr > hrBounds.high) {
      allFired.push({
        id: "extreme_hr",
        citation: "Age-stratified extreme heart rate per WHO/PALS guidelines",
        detail: `Extreme heart rate for age ${age.toFixed(1)}yr (${hr} bpm, normal bounds ${hrBounds.low}-${hrBounds.high})`,
      });
    }
  }

  if (bpSys !== null) {
    const bpBounds = bpEmergencyThreshold(age);
    if (bpSys < bpBounds.low || bpSys > bpBounds.high) {
      allFired.push({
        id: "extreme_bp",
        citation: "Age-stratified systolic BP outside physiologically stable range (PALS 5th percentile / crisis)",
        detail: `Extreme systolic blood pressure for age ${age.toFixed(1)}yr (${bpSys} mmHg, bounds ${bpBounds.low}-${bpBounds.high})`,
      });
    }
  }

  if (bpSys !== null && bpSys >= 180) {
    const neuro = [...symptoms].filter((s) => HYPERTENSIVE_NEURO.has(s as Symptom));
    if (neuro.length) {
      allFired.push({
        id: "hypertensive_neuro_emergency",
        citation: "Hypertensive crisis (SBP >=180) + neurological symptom(s) — possible hypertensive encephalopathy/stroke",
        detail: `Hypertensive crisis (systolic BP ${bpSys} mmHg) with neurological symptom(s): ${readable(neuro)} — possible hypertensive encephalopathy/stroke`,
      });
    }
  }

  if (temp !== null) {
    const tempBounds = tempEmergencyThreshold(age);
    if (temp < tempBounds.low || temp > tempBounds.high) {
      allFired.push({
        id: "extreme_temp",
        citation: "Extreme hyper/hypothermia outside physiologically stable range",
        detail: `Extreme body temperature (${temp}C)`,
      });
    }
  }

  if (form.is_pregnant) {
    const bpDia = form.bp_diastolic;
    if (bpSys !== null && bpDia !== null) {
      if (bpSys >= 160 || bpDia >= 110) {
        allFired.push({
          id: "preeclampsia_severe_bp",
          citation: "ACOG Practice Bulletin 222: severe hypertension in pregnancy (BP >=160/110) is a severe feature on its own",
          detail: `Severe hypertension in pregnancy (BP ${bpSys}/${bpDia} mmHg) - possible severe preeclampsia`,
        });
      }
      if (bpSys >= 140 || bpDia >= 90) {
        const hit = [...symptoms].filter((s) => PREECLAMPSIA_SEVERE_SYMPTOMS.has(s as Symptom));
        if (hit.length) {
          allFired.push({
            id: "preeclampsia_with_severe_feature",
            citation: "ACOG Practice Bulletin 222: BP >=140/90 with a severe feature (severe headache, epigastric pain) meets severe preeclampsia criteria",
            detail: `Hypertension in pregnancy (BP ${bpSys}/${bpDia} mmHg) with severe feature(s): ${readable(hit)} - possible preeclampsia with severe features`,
          });
        }
      }
    }
  }

  if (allFired.length === 0) return null;
  if (allFired.length === 1) return allFired[0]!;

  return {
    id: allFired.map((r) => r.id).join("+"),
    citation: allFired[0]!.citation,
    detail: allFired.map((r) => r.detail).join("; "),
  };
}

/**
 * NEWS2 "concerning single vital" floor thresholds — a concerning-but-not-
 * extreme single vital (NEWS2 score >= 2 territory) can never be left as
 * ROUTINE. In the rules-first engine this is largely subsumed by the
 * aggregate scorer's own aggregate>=2 threshold (bands.ts::news2LikeScore),
 * but is kept as an explicit, independently-citable floor for auditability
 * and as a redundant backstop — see engine.ts.
 */
export function news2ConcerningVital(form: OverrideInput): FiredRule | null {
  const { spo2, bp_systolic: bpSys, heart_rate: hr, temperature: temp } = form;

  if (spo2 !== null && spo2 <= 92) {
    return { id: "news2_floor_spo2", citation: "NEWS2 scale 1 SpO2 <=92 scores 2+", detail: `low oxygen saturation (${spo2}%)` };
  }
  if (bpSys !== null && (bpSys <= 100 || bpSys >= 180)) {
    return {
      id: "news2_floor_bp",
      citation: "NEWS2-adjacent systolic-BP band scoring 2+",
      detail: `concerning systolic blood pressure (${bpSys} mmHg)`,
    };
  }
  if (hr !== null && (hr <= 40 || hr >= 120)) {
    return { id: "news2_floor_hr", citation: "NEWS2 HR band scoring 2+", detail: `concerning heart rate (${hr} bpm)` };
  }
  if (temp !== null && (temp <= 35.0 || temp >= 39.1)) {
    return { id: "news2_floor_temp", citation: "NEWS2 temperature band scoring 2+", detail: `concerning temperature (${temp}C)` };
  }
  return null;
}

/**
 * Pediatric Glasgow Coma Scale (pGCS) calculator (BUG-39).
 * Computes eye (1-4), verbal (1-5), and motor (1-6) scores.
 * Maximum score is 15. Guards against division by zero when calculating ratios/percentages.
 */
export interface PediatricGcsResult {
  eye: number;
  verbal: number;
  motor: number;
  totalScore: number;
  maxScore: number;
  scoreRatio: number;
  tier: "EMERGENCY" | "URGENT" | "ROUTINE";
  isComa: boolean;
  citation: string;
}

export function calculatePediatricGcs(
  eye: number,
  verbal: number,
  motor: number,
  maxScore: number = 15
): PediatricGcsResult {
  // Validate and clamp inputs
  const safeEye = Number.isFinite(eye) ? Math.max(1, Math.min(4, Math.round(eye))) : 1;
  const safeVerbal = Number.isFinite(verbal) ? Math.max(1, Math.min(5, Math.round(verbal))) : 1;
  const safeMotor = Number.isFinite(motor) ? Math.max(1, Math.min(6, Math.round(motor))) : 1;

  const totalScore = safeEye + safeVerbal + safeMotor;

  // Guard against division by zero (BUG-39): if maxScore <= 0 or not finite, fallback safely to standard 15
  const safeMax = Number.isFinite(maxScore) && maxScore > 0 ? maxScore : 15;
  const scoreRatio = Number((totalScore / safeMax).toFixed(4));

  // Clinical interpretation per PALS:
  // pGCS <= 8: Severe impairment / Coma -> EMERGENCY
  // pGCS 9-12: Moderate impairment -> URGENT
  // pGCS 13-15: Mild or normal -> ROUTINE
  let tier: "EMERGENCY" | "URGENT" | "ROUTINE" = "ROUTINE";
  if (totalScore <= 8) {
    tier = "EMERGENCY";
  } else if (totalScore <= 12) {
    tier = "URGENT";
  }

  return {
    eye: safeEye,
    verbal: safeVerbal,
    motor: safeMotor,
    totalScore,
    maxScore: safeMax,
    scoreRatio,
    tier,
    isComa: totalScore <= 8,
    citation: "Paediatric Glasgow Coma Scale (Simpson & Reilly 1982 / PALS Guidelines)",
  };
}

/**
 * Normalizes symptom duration and arrival timestamps (BUG-40).
 * Disallows negative duration (clamping to 0) and handles future timestamps
 * gracefully by clamping to current/reference time.
 */
export interface NormalizedSymptomDuration {
  durationMinutes: number;
  durationHours: number;
  durationDays: number;
  rawDuration: string | number;
  isNegativeAdjusted: boolean;
  isFutureTimestampAdjusted: boolean;
  standardizedText: string;
}

export function normalizeSymptomDuration(
  durationInput?: string | number | null,
  timestampInput?: string | number | Date | null,
  referenceTimeMs: number = Date.now()
): NormalizedSymptomDuration {
  let durationMinutes = 0;
  let isNegative = false;
  let isFuture = false;
  const rawDuration = durationInput ?? "";

  // 1. Process timestampInput if provided
  if (timestampInput !== null && timestampInput !== undefined && timestampInput !== "") {
    let tMs: number;
    if (timestampInput instanceof Date) {
      tMs = timestampInput.getTime();
    } else if (typeof timestampInput === "number") {
      tMs = timestampInput;
    } else {
      tMs = Date.parse(String(timestampInput));
    }

    if (Number.isFinite(tMs)) {
      if (tMs > referenceTimeMs) {
        // Future timestamp detected: handle gracefully (clamp to reference time)
        isFuture = true;
        durationMinutes = 0;
      } else {
        const diffMs = referenceTimeMs - tMs;
        durationMinutes = Math.max(0, Math.round(diffMs / (60 * 1000)));
      }
    }
  }

  // 2. If durationInput is provided, parse it
  if (durationInput !== null && durationInput !== undefined && durationInput !== "") {
    if (typeof durationInput === "number") {
      if (!Number.isFinite(durationInput) || durationInput <= 0) {
        isNegative = durationInput < 0;
        durationMinutes = 0;
      } else {
        // Assume hours if plain numeric
        durationMinutes = Math.round(durationInput * 60);
      }
    } else {
      const trimmed = String(durationInput).trim().toLowerCase();
      // Look for negative patterns like "-5 hours", "-2d"
      if (trimmed.startsWith("-") || trimmed.includes("negative")) {
        isNegative = true;
        durationMinutes = 0;
      } else {
        const match = trimmed.match(/^(\d+(?:\.\d+)?)\s*(d|day|days|h|hr|hrs|hour|hours|m|min|mins|minute|minutes|w|week|weeks|mo|month|months)?/i);
        if (match && match[1]) {
          const val = parseFloat(match[1]);
          const unit = (match[2] || "h").toLowerCase();
          if (unit.startsWith("d")) {
            durationMinutes = Math.round(val * 24 * 60);
          } else if (unit.startsWith("m") && !unit.startsWith("mo")) {
            durationMinutes = Math.round(val);
          } else if (unit.startsWith("w")) {
            durationMinutes = Math.round(val * 7 * 24 * 60);
          } else if (unit.startsWith("mo")) {
            durationMinutes = Math.round(val * 30 * 24 * 60);
          } else {
            // Default hours
            durationMinutes = Math.round(val * 60);
          }
        }
      }
    }
  }

  // Ensure durationMinutes is never negative
  if (durationMinutes < 0) {
    isNegative = true;
    durationMinutes = 0;
  }

  const durationHours = Number((durationMinutes / 60).toFixed(2));
  const durationDays = Number((durationMinutes / (24 * 60)).toFixed(2));

  let standardizedText = "";
  if (durationMinutes === 0) {
    standardizedText = "acute (< 1 hour)";
  } else if (durationMinutes < 60) {
    standardizedText = `${durationMinutes} minute(s)`;
  } else if (durationHours < 48) {
    standardizedText = `${durationHours} hour(s)`;
  } else {
    standardizedText = `${durationDays} day(s)`;
  }

  return {
    durationMinutes,
    durationHours,
    durationDays,
    rawDuration,
    isNegativeAdjusted: isNegative,
    isFutureTimestampAdjusted: isFuture,
    standardizedText,
  };
}
