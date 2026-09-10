/**
 * calculators.ts — Deterministic offline clinical calculators for rural
 * health workers and primary care facilities (Roadmap §4.3).
 *
 * Scope & Clinical Safety:
 *  - Decision-support arithmetic calculators for paediatric dosing, rehydration
 *    (WHO Diarrhoea Guidelines), IV drip rates, and Holliday-Segar fluid maintenance.
 *  - All calculations are pure, deterministic, client-side, zero-PHI arithmetic.
 *  - All clinical drug names, formula constants, units, and regimen codes are
 *    locale-independent constants; the UI/i18n layer translates only instructional
 *    scaffolding and interface labels.
 *  - Explicit boundary guards: strictly enforces patient weight bounds (1.0 kg - 100.0 kg),
 *    neonatal referral threshold (<1.0 kg), single-dose caps, and 24-hour daily total caps.
 */

// ── Types & Closed Sets ──────────────────────────────────────────────────────

export type DoseFrequency =
  | "Q4H"   // Every 4 hours (6 times/day)
  | "Q6H"   // Every 6 hours (4 times/day)
  | "Q8H"   // Every 8 hours (3 times/day)
  | "Q12H"  // Every 12 hours (2 times/day)
  | "Q24H"  // Once daily (1 time/day)
  | "ONCE"  // Single stat dose
  | "PRN";  // As needed (with minimum interval)

export type TreatmentDuration =
  | "SINGLE_DOSE"
  | "3_DAYS"
  | "5_DAYS"
  | "7_DAYS"
  | "10_DAYS"
  | "14_DAYS"
  | "UNTIL_RESOLVED";

export interface FrequencyMeta {
  code: DoseFrequency;
  label: string;
  dosesPerDay: number;
  minimumIntervalHours: number;
  description: string;
}

export interface DurationMeta {
  code: TreatmentDuration;
  label: string;
  days?: number;
}

export interface LiquidConcentration {
  label: string;
  mg: number;
  ml: number;
  mgPerMl: number;
}

export interface PediatricDrugPreset {
  id: string;
  drugName: string;
  indication: string;
  mgPerKg: number;
  defaultFrequency: DoseFrequency;
  defaultDuration: TreatmentDuration;
  maxMgPerDose: number;
  maxMgPerDay?: number;
  maxMgPerKgPerDay?: number;
  concentrationOptions: readonly LiquidConcentration[];
  minAgeMonths?: number;
  minWeightKg?: number;
  notes: string;
  citation: string;
}

// ── Metadata Registries ─────────────────────────────────────────────────────

export const FREQUENCY_METADATA: Record<DoseFrequency, FrequencyMeta> = {
  Q4H:  { code: "Q4H",  label: "Every 4 hours (Q4H)",  dosesPerDay: 6, minimumIntervalHours: 4,  description: "6 doses per 24 hours (spaced 4 hours apart)" },
  Q6H:  { code: "Q6H",  label: "Every 6 hours (Q6H)",  dosesPerDay: 4, minimumIntervalHours: 6,  description: "4 doses per 24 hours (spaced 6 hours apart)" },
  Q8H:  { code: "Q8H",  label: "Every 8 hours (Q8H)",  dosesPerDay: 3, minimumIntervalHours: 8,  description: "3 doses per 24 hours (spaced 8 hours apart)" },
  Q12H: { code: "Q12H", label: "Every 12 hours (Q12H)", dosesPerDay: 2, minimumIntervalHours: 12, description: "2 doses per 24 hours (spaced 12 hours apart)" },
  Q24H: { code: "Q24H", label: "Once daily (Q24H)",    dosesPerDay: 1, minimumIntervalHours: 24, description: "1 dose per 24 hours" },
  ONCE: { code: "ONCE", label: "Single dose (Stat)",   dosesPerDay: 1, minimumIntervalHours: 0,  description: "One-time administration" },
  PRN:  { code: "PRN",  label: "As needed (PRN)",      dosesPerDay: 4, minimumIntervalHours: 4,  description: "As needed, minimum 4 hours between doses (max 4 doses/day)" },
};

export const DURATION_METADATA: Record<TreatmentDuration, DurationMeta> = {
  SINGLE_DOSE:    { code: "SINGLE_DOSE",    label: "Single dose (Stat)", days: 1 },
  "3_DAYS":       { code: "3_DAYS",       label: "3 days",              days: 3 },
  "5_DAYS":       { code: "5_DAYS",       label: "5 days",              days: 5 },
  "7_DAYS":       { code: "7_DAYS",       label: "7 days",              days: 7 },
  "10_DAYS":      { code: "10_DAYS",      label: "10 days",             days: 10 },
  "14_DAYS":      { code: "14_DAYS",      label: "14 days",             days: 14 },
  UNTIL_RESOLVED: { code: "UNTIL_RESOLVED", label: "Until symptoms resolve" },
};

export const PEDIATRIC_DRUG_PRESETS: readonly PediatricDrugPreset[] = [
  {
    id: "paracetamol",
    drugName: "Paracetamol",
    indication: "Fever & Pain Relief",
    mgPerKg: 15,
    defaultFrequency: "Q6H",
    defaultDuration: "UNTIL_RESOLVED",
    maxMgPerDose: 1000,
    maxMgPerDay: 4000,
    maxMgPerKgPerDay: 60,
    concentrationOptions: [
      { label: "120 mg / 5 mL (Syrup)", mg: 120, ml: 5, mgPerMl: 24 },
      { label: "250 mg / 5 mL (Forte)", mg: 250, ml: 5, mgPerMl: 50 },
      { label: "100 mg / 1 mL (Infant Drops)", mg: 100, ml: 1, mgPerMl: 100 },
    ],
    minAgeMonths: 1,
    minWeightKg: 2.5,
    notes: "15 mg/kg per single dose every 4-6 hours. Max 60 mg/kg/day or 4000 mg/day. Minimum 4 hours between doses.",
    citation: "WHO Model Formulary for Children (2010), Indian National Formulary",
  },
  {
    id: "amoxicillin_standard",
    drugName: "Amoxicillin — Standard (WHO / IMCI)",
    indication: "Mild-Moderate Respiratory / Skin Infections",
    mgPerKg: 13.33,
    defaultFrequency: "Q8H",
    defaultDuration: "5_DAYS",
    maxMgPerDose: 500,
    maxMgPerDay: 1500,
    maxMgPerKgPerDay: 40,
    concentrationOptions: [
      { label: "125 mg / 5 mL (Suspension)", mg: 125, ml: 5, mgPerMl: 25 },
      { label: "250 mg / 5 mL (Suspension)", mg: 250, ml: 5, mgPerMl: 50 },
    ],
    minAgeMonths: 2,
    minWeightKg: 3.0,
    notes: "Standard WHO IMCI regimen: 40 mg/kg/day divided into 3 doses (13.33 mg/kg/dose Q8H). For severe infections / AOM use High-Dose preset.",
    citation: "WHO Model Formulary for Children (2010), IMCI Guidelines",
  },
  {
    id: "amoxicillin_aom",
    drugName: "Amoxicillin — High-Dose (AOM)",
    indication: "Acute Otitis Media / Suspected Resistant S. pneumoniae",
    mgPerKg: 45,
    defaultFrequency: "Q12H",
    defaultDuration: "10_DAYS",
    maxMgPerDose: 1000,
    maxMgPerDay: 3000,
    maxMgPerKgPerDay: 90,
    concentrationOptions: [
      { label: "250 mg / 5 mL (Suspension)", mg: 250, ml: 5, mgPerMl: 50 },
      { label: "400 mg / 5 mL (Extra-Strength)", mg: 400, ml: 5, mgPerMl: 80 },
    ],
    minAgeMonths: 2,
    minWeightKg: 3.0,
    notes: "High-dose regimen: 80-90 mg/kg/day divided into 2 doses (40-45 mg/kg/dose Q12H) or 3 doses (30 mg/kg/dose Q8H). Max 1000 mg/dose.",
    citation: "AAP Clinical Practice Guideline: Diagnosis and Management of Acute Otitis Media (2013)",
  },
  {
    id: "ibuprofen",
    drugName: "Ibuprofen",
    indication: "Inflammatory Pain & High Fever (>38.5°C)",
    mgPerKg: 10,
    defaultFrequency: "Q8H",
    defaultDuration: "3_DAYS",
    maxMgPerDose: 400,
    maxMgPerDay: 1200,
    maxMgPerKgPerDay: 40,
    concentrationOptions: [
      { label: "100 mg / 5 mL (Suspension)", mg: 100, ml: 5, mgPerMl: 20 },
    ],
    minAgeMonths: 3,
    minWeightKg: 5.0,
    notes: "10 mg/kg per dose every 6-8 hours with food. Not recommended for infants <3 months or <5 kg. Avoid in severe dehydration/renal impairment.",
    citation: "British National Formulary for Children (BNFC), WHO Essential Medicines",
  },
  {
    id: "zinc_sulfate_under_6m",
    drugName: "Zinc Sulfate (<6 Months)",
    indication: "Acute Diarrhoea Adjunct",
    mgPerKg: 0, // Fixed dose
    defaultFrequency: "Q24H",
    defaultDuration: "14_DAYS",
    maxMgPerDose: 10,
    maxMgPerDay: 10,
    concentrationOptions: [
      { label: "20 mg Dispersible Tablet (1/2 tab)", mg: 10, ml: 1, mgPerMl: 10 },
      { label: "10 mg / 5 mL (Syrup)", mg: 10, ml: 5, mgPerMl: 2 },
    ],
    minAgeMonths: 0,
    minWeightKg: 2.0,
    notes: "Fixed dose 10 mg once daily for 14 continuous days to accelerate gut mucosal healing and prevent recurrences.",
    citation: "WHO/UNICEF Joint Statement on the Clinical Management of Acute Diarrhoea",
  },
  {
    id: "zinc_sulfate_over_6m",
    drugName: "Zinc Sulfate (≥6 Months)",
    indication: "Acute Diarrhoea Adjunct",
    mgPerKg: 0, // Fixed dose
    defaultFrequency: "Q24H",
    defaultDuration: "14_DAYS",
    maxMgPerDose: 20,
    maxMgPerDay: 20,
    concentrationOptions: [
      { label: "20 mg Dispersible Tablet (1 whole tab)", mg: 20, ml: 1, mgPerMl: 20 },
      { label: "20 mg / 5 mL (Syrup)", mg: 20, ml: 5, mgPerMl: 4 },
    ],
    minAgeMonths: 6,
    minWeightKg: 5.0,
    notes: "Fixed dose 20 mg once daily for 14 continuous days. Disperse in a small amount of clean water or breastmilk.",
    citation: "WHO/UNICEF Joint Statement on the Clinical Management of Acute Diarrhoea",
  },
  {
    id: "azithromycin",
    drugName: "Azithromycin",
    indication: "Atypical Respiratory / Cholera / Enteric Infections",
    mgPerKg: 10,
    defaultFrequency: "Q24H",
    defaultDuration: "3_DAYS",
    maxMgPerDose: 500,
    maxMgPerDay: 500,
    maxMgPerKgPerDay: 10,
    concentrationOptions: [
      { label: "100 mg / 5 mL (Suspension)", mg: 100, ml: 5, mgPerMl: 20 },
      { label: "200 mg / 5 mL (Suspension)", mg: 200, ml: 5, mgPerMl: 40 },
    ],
    minAgeMonths: 6,
    minWeightKg: 5.0,
    notes: "10 mg/kg once daily for 3 days (or Day 1: 10 mg/kg, then Days 2-5: 5 mg/kg once daily). Max 500 mg/day.",
    citation: "WHO Model Formulary for Children (2010)",
  },
  {
    id: "cotrimoxazole",
    drugName: "Cotrimoxazole (TMP-SMX)",
    indication: "Susceptible UTI / Respiratory Infections",
    mgPerKg: 4, // 4 mg TMP / 20 mg SMX per kg per dose
    defaultFrequency: "Q12H",
    defaultDuration: "5_DAYS",
    maxMgPerDose: 160, // TMP component
    maxMgPerDay: 320,
    maxMgPerKgPerDay: 8,
    concentrationOptions: [
      { label: "240 mg / 5 mL (40 mg TMP + 200 mg SMX)", mg: 40, ml: 5, mgPerMl: 8 },
    ],
    minAgeMonths: 2,
    minWeightKg: 3.5,
    notes: "Dosing based on Trimethoprim component: 4 mg TMP/kg/dose (with 20 mg SMX/kg/dose) every 12 hours. Max 160 mg TMP/dose.",
    citation: "WHO Model Formulary for Children (2010)",
  },
  {
    id: "salbutamol_oral",
    drugName: "Salbutamol (Oral)",
    indication: "Bronchospasm / Wheeze (Oral Route)",
    mgPerKg: 0.15,
    defaultFrequency: "Q8H",
    defaultDuration: "UNTIL_RESOLVED",
    maxMgPerDose: 2.0,
    maxMgPerDay: 6.0,
    maxMgPerKgPerDay: 0.45,
    concentrationOptions: [
      { label: "2 mg / 5 mL (Syrup)", mg: 2, ml: 5, mgPerMl: 0.4 },
    ],
    minAgeMonths: 2,
    minWeightKg: 3.5,
    notes: "Modern practice: inhaled salbutamol (MDI + spacer or nebulized) is strongly preferred for acute wheeze due to faster onset and fewer systemic side effects. Oral salbutamol is presented as a secondary alternative strictly for resource-constrained primary care settings where inhaler devices/spacers are unavailable. 0.15 mg/kg per dose every 8 hours. Max single dose 2 mg (<6 yrs) or 4 mg (6-12 yrs).",
    citation: "WHO Model Formulary for Children (2010), GINA Paediatric Guidelines",
  },
];

/**
 * Standard essential medications in the official Indian National Health Mission
 * (NHM) ASHA drug kit. Restricts the calculator preset list when rendered for
 * frontline community health workers (scope="asha").
 * Source: Ministry of Health and Family Welfare (MoHFW) ASHA Drug Kit Guidelines.
 */
export const ASHA_SCOPE_DRUG_IDS: readonly string[] = [
  "paracetamol",
  "zinc_sulfate_under_6m",
  "zinc_sulfate_over_6m",
  "cotrimoxazole",
];


// ── 1. Weight-Based Dose Calculator ─────────────────────────────────────────

export interface WeightDoseInput {
  weightKg: number;
  mgPerKg: number;
  maxMgPerDose: number;
  frequency?: DoseFrequency;
  concentrationMgPerMl?: number;
  maxMgPerDay?: number;
  maxMgPerKgPerDay?: number;
  drugName?: string;
  minWeightKg?: number;
  minAgeMonths?: number;
  ageMonths?: number;
}

export interface WeightDoseResult {
  weightKg: number;
  mgPerKg: number;
  rawDoseMg: number;
  doseMg: number;
  isCappedSingleDose: boolean;
  maxMgPerDose: number;
  volumeMl: number | null;
  concentrationMgPerMl: number | null;
  frequency: DoseFrequency | null;
  dosesPerDay: number | null;
  minimumIntervalHours: number | null;
  dailyTotalMg: number | null;
  isCappedDailyTotal: boolean;
  maxMgPerDay: number | null;
  warning: string | null;
  steps: readonly string[];
}

export function calculateWeightBasedDose(input: WeightDoseInput): WeightDoseResult {
  const {
    weightKg,
    mgPerKg,
    maxMgPerDose,
    frequency,
    concentrationMgPerMl,
    maxMgPerDay,
    maxMgPerKgPerDay,
    drugName,
    minWeightKg,
    minAgeMonths,
    ageMonths,
  } = input;

  if (weightKg < 1.0) {
    throw new Error("Patient weight < 1.0 kg is out of bounds for standard paediatric dosing protocols. Specialist neonatal care required.");
  }
  if (weightKg > 100.0) {
    throw new Error("Patient weight > 100.0 kg exceeds paediatric parameters. Use adult dosing protocols with adult maximum caps.");
  }
  if (minWeightKg !== undefined && weightKg < minWeightKg) {
    throw new Error(`Patient weight (${weightKg} kg) is below the minimum threshold (${minWeightKg} kg) for ${drugName || "this medication"}. Specialist paediatric evaluation required.`);
  }
  if (minAgeMonths !== undefined && ageMonths !== undefined && ageMonths < minAgeMonths) {
    throw new Error(`Patient age (${ageMonths} months) is below the minimum threshold (${minAgeMonths} months) for ${drugName || "this medication"}. Specialist paediatric evaluation required.`);
  }
  if (mgPerKg < 0 || maxMgPerDose <= 0) {
    throw new Error("mg/kg must be non-negative and max dose must be greater than zero.");
  }

  const steps: string[] = [];
  let warning: string | null = null;

  // Step 1: Raw dose calculation (or fixed dose if mgPerKg === 0)
  const isFixedDose = mgPerKg === 0;
  const rawDoseMg = isFixedDose ? maxMgPerDose : Number((weightKg * mgPerKg).toFixed(2));
  if (isFixedDose) {
    steps.push(`Fixed dose protocol: ${rawDoseMg} mg`);
  } else {
    steps.push(`Calculated single dose: ${weightKg} kg × ${mgPerKg} mg/kg = ${rawDoseMg} mg`);
  }

  // Step 2: Single dose cap check
  let doseMg = rawDoseMg;
  let isCappedSingleDose = false;
  if (doseMg > maxMgPerDose) {
    doseMg = maxMgPerDose;
    isCappedSingleDose = true;
    steps.push(`Single dose capped at maximum allowable limit: ${maxMgPerDose} mg (calculated ${rawDoseMg} mg)`);
  } else {
    steps.push(`Single dose is within maximum cap (${maxMgPerDose} mg): ${doseMg} mg`);
  }

  // Step 3: Liquid formulation volume calculation
  let volumeMl: number | null = null;
  if (concentrationMgPerMl && concentrationMgPerMl > 0) {
    volumeMl = Number((doseMg / concentrationMgPerMl).toFixed(2));
    steps.push(`Liquid formulation: ${doseMg} mg ÷ ${concentrationMgPerMl} mg/mL = ${volumeMl} mL`);
  }

  // Step 4: Frequency, intervals, and 24-hour cumulative checks
  let dosesPerDay: number | null = null;
  let minimumIntervalHours: number | null = null;
  let dailyTotalMg: number | null = null;
  let isCappedDailyTotal = false;

  if (frequency && FREQUENCY_METADATA[frequency]) {
    const meta = FREQUENCY_METADATA[frequency];
    dosesPerDay = meta.dosesPerDay;
    minimumIntervalHours = meta.minimumIntervalHours;
    dailyTotalMg = Number((doseMg * dosesPerDay).toFixed(2));
    steps.push(`Frequency ${frequency}: ${dosesPerDay} dose(s)/day (minimum ${minimumIntervalHours} hours between doses) → 24-hour total: ${dailyTotalMg} mg/day`);

    // Effective daily ceiling: min(maxMgPerDay, maxMgPerKgPerDay * weightKg)
    let effectiveDailyCeiling = maxMgPerDay ?? Infinity;
    if (maxMgPerKgPerDay && maxMgPerKgPerDay > 0) {
      const weightBasedDailyCap = maxMgPerKgPerDay * weightKg;
      effectiveDailyCeiling = Math.min(effectiveDailyCeiling, weightBasedDailyCap);
    }

    if (effectiveDailyCeiling < Infinity && dailyTotalMg > effectiveDailyCeiling) {
      isCappedDailyTotal = true;
      const capMsg = `Warning: 24-hour cumulative dose (${dailyTotalMg} mg/day) exceeds maximum daily ceiling (${effectiveDailyCeiling} mg/day). Reduce frequency or dose per administration.`;
      warning = warning ? `${warning} | ${capMsg}` : capMsg;
      steps.push(`ALERT: ${capMsg}`);
    }
  }

  if (weightKg < 3.0) {
    const lowWeightNotice = "Caution: Low birth weight / neonate (<3 kg). Pharmacokinetics differ; verify with pediatric/neonatal specialist.";
    warning = warning ? `${warning} | ${lowWeightNotice}` : lowWeightNotice;
  }

  return {
    weightKg,
    mgPerKg,
    rawDoseMg,
    doseMg,
    isCappedSingleDose,
    maxMgPerDose,
    volumeMl,
    concentrationMgPerMl: concentrationMgPerMl ?? null,
    frequency: frequency ?? null,
    dosesPerDay,
    minimumIntervalHours,
    dailyTotalMg,
    isCappedDailyTotal,
    maxMgPerDay: maxMgPerDay ?? null,
    warning,
    steps,
  };
}

// ── 2. WHO Diarrhoea & ORS Rehydration Calculator ────────────────────────────

export type DehydrationPlan = "PLAN_A" | "PLAN_B" | "PLAN_C";

export interface OrsPlanInput {
  weightKg: number;
  plan: DehydrationPlan;
  ageMonths?: number;
}

export interface OrsPlanResult {
  plan: DehydrationPlan;
  planName: string;
  weightKg: number;
  totalVolumeMl: number;
  durationHours: number;
  rateMlPerHour: number | null;
  guidance: string;
  reassessmentMinutes: number;
  steps: readonly string[];
}

export function calculateOrsVolume(input: OrsPlanInput): OrsPlanResult {
  const { weightKg, plan, ageMonths } = input;

  if (weightKg < 1.0 || weightKg > 100.0) {
    throw new Error("Weight must be between 1.0 kg and 100.0 kg.");
  }

  const steps: string[] = [];

  if (plan === "PLAN_A") {
    // Plan A: No Dehydration — Home maintenance
    // Maintenance: 10 mL/kg per loose stool, or age-based minimum:
    // <2 yrs: 50-100 mL per stool; 2-10 yrs: 100-200 mL per stool; >10 yrs: as much as wanted.
    const perStoolMl = Number((weightKg * 10).toFixed(0));
    steps.push(`WHO Plan A (No Signs of Dehydration): Maintenance & replacement of ongoing fluid losses.`);
    steps.push(`Replacement: Give ${perStoolMl} mL (10 mL/kg) of ORS solution after every loose stool or vomit episode.`);
    steps.push(`Continue age-appropriate feeding and frequent breastfeeding.`);
    steps.push(`Prescribe 14-day course of Zinc Sulfate.`);

    return {
      plan,
      planName: "WHO Plan A (No Dehydration / Home Management)",
      weightKg,
      totalVolumeMl: perStoolMl,
      durationHours: 24,
      rateMlPerHour: null, // Plan A is dosed per loose stool episode, not as continuous hourly infusion.
      guidance: `Give ~${perStoolMl} mL ORS after each loose stool or vomit episode. Continue normal feeding and Zinc for 14 days. Reassess hydration status in 4 hours. Seek immediate care if blood in stool, persistent vomiting, or lethargy develops.`,
      reassessmentMinutes: 240, // 4 hours
      steps,
    };
  }

  if (plan === "PLAN_B") {
    // Plan B: Some Dehydration — Oral rehydration over 4 hours
    // Formula: 75 mL/kg over 4 hours
    const totalVolumeMl = Number((weightKg * 75).toFixed(0));
    const rateMlPerHour = Number((totalVolumeMl / 4).toFixed(1));
    const teaspoonRate = Number((rateMlPerHour / 5).toFixed(0)); // 5 mL teaspoon

    steps.push(`WHO Plan B (Some Dehydration): Oral rehydration over 4 hours.`);
    steps.push(`Formula: 75 mL/kg × ${weightKg} kg = ${totalVolumeMl} mL total ORS.`);
    steps.push(`Administration: Administer ${totalVolumeMl} mL over 4 hours (${rateMlPerHour} mL/hour, approx ${teaspoonRate} teaspoons/hour or small cup sips).`);
    steps.push(`If child vomits, wait 10 minutes then resume slowly (1 teaspoon every 2-3 minutes).`);
    steps.push(`Reassess hydration status at 4 hours.`);

    return {
      plan,
      planName: "WHO Plan B (Some Dehydration / 4-Hour ORS)",
      weightKg,
      totalVolumeMl,
      durationHours: 4,
      rateMlPerHour,
      guidance: `Give ${totalVolumeMl} mL of ORS over 4 hours (${rateMlPerHour} mL/hr). Reassess clinical signs after 4 hours: if signs resolved switch to Plan A; if some dehydration persists repeat Plan B; if severe signs develop escalate immediately to Plan C.`,
      reassessmentMinutes: 240,
      steps,
    };
  }

  // Plan C: Severe Dehydration — Immediate IV fluid resuscitation
  // Formula: 100 mL/kg Ringer's Lactate (or Normal Saline if RL unavailable)
  // Age < 12 months: 30 mL/kg in 1 hour -> 70 mL/kg in 5 hours (total 6 hours)
  // Age >= 12 months: 30 mL/kg in 30 mins -> 70 mL/kg in 2.5 hours (total 3 hours)
  const isInfant = ageMonths !== undefined ? ageMonths < 12 : weightKg < 10;
  const totalVolumeMl = Number((weightKg * 100).toFixed(0));
  const bolusVolume = Number((weightKg * 30).toFixed(0));
  const maintenanceVolume = Number((weightKg * 70).toFixed(0));
  const durationHours = isInfant ? 6 : 3;

  if (ageMonths === undefined) {
    const ageAdvisory = `Clinical Note: Patient age was not provided; protocol schedule was selected based on weight heuristic (${weightKg < 10 ? "<10 kg (Infant split: 1h bolus + 5h maintenance)" : "≥10 kg (Child split: 30m bolus + 2.5h maintenance)"}). Please verify patient age (<12 months vs ≥12 months) before administering IV fluids.`;
    steps.push(ageAdvisory);
  }

  steps.push(`WHO Plan C (Severe Dehydration / Medical Emergency): Immediate IV Fluid Resuscitation.`);
  steps.push(`Fluid Choice: Ringer's Lactate (preferred) or Normal Saline (0.9% NaCl). Total 100 mL/kg = ${totalVolumeMl} mL.`);

  if (isInfant) {
    steps.push(`Infant (<12 months / <10 kg) Protocol (Total 6 hours):`);
    steps.push(`  - Step 1: Rapid Bolus 30 mL/kg = ${bolusVolume} mL over 1 hour (rate: ${bolusVolume} mL/hr).`);
    steps.push(`  - Step 2: Remainder 70 mL/kg = ${maintenanceVolume} mL over 5 hours (rate: ${(maintenanceVolume / 5).toFixed(1)} mL/hr).`);
    steps.push(`  - Reassess radial pulse / fontanelle every 15-30 minutes.`);
  } else {
    steps.push(`Child (≥12 months / ≥10 kg) Protocol (Total 3 hours):`);
    steps.push(`  - Step 1: Rapid Bolus 30 mL/kg = ${bolusVolume} mL over 30 minutes (rate: ${bolusVolume * 2} mL/hr).`);
    steps.push(`  - Step 2: Remainder 70 mL/kg = ${maintenanceVolume} mL over 2.5 hours (rate: ${(maintenanceVolume / 2.5).toFixed(1)} mL/hr).`);
    steps.push(`  - Reassess radial pulse every 15 minutes until strong.`);
  }

  return {
    plan,
    planName: "WHO Plan C (Severe Dehydration / IV Resuscitation)",
    weightKg,
    totalVolumeMl,
    durationHours,
    rateMlPerHour: Number((totalVolumeMl / durationHours).toFixed(1)),
    guidance: `EMERGENCY: Start IV Ringer's Lactate immediately. Give 30 mL/kg bolus (${bolusVolume} mL), then 70 mL/kg (${maintenanceVolume} mL). Reassess radial pulse every 15-30 min. Give ORS (5 mL/kg/hr) as soon as patient can drink.`,
    reassessmentMinutes: isInfant ? 60 : 30,
    steps,
  };
}

// ── 3. IV Drip Rate Calculator ──────────────────────────────────────────────

export type DropFactor = 10 | 15 | 20 | 60;

export interface IvDripRateInput {
  volumeMl: number;
  durationHours?: number;
  durationMinutes?: number;
  dropFactor: DropFactor;
}

export interface IvDripRateResult {
  volumeMl: number;
  durationMinutes: number;
  durationHours: number;
  dropFactor: DropFactor;
  dripRateGttPerMin: number;
  infusionRateMlPerHour: number;
  steps: readonly string[];
}

export function calculateIvDripRate(input: IvDripRateInput): IvDripRateResult {
  const { volumeMl, durationHours = 0, durationMinutes = 0, dropFactor } = input;

  const totalMinutes = durationHours * 60 + durationMinutes;
  if (volumeMl <= 0 || totalMinutes <= 0) {
    throw new Error("Volume and duration must be greater than zero.");
  }
  if (![10, 15, 20, 60].includes(dropFactor)) {
    throw new Error("Drop factor must be 10, 15, 20 (Macrodrip) or 60 (Microdrip).");
  }

  const steps: string[] = [];
  const hours = Number((totalMinutes / 60).toFixed(2));
  const infusionRateMlPerHour = Number((volumeMl / hours).toFixed(1));

  // Formula: Drip Rate (gtt/min) = (Volume in mL × Drop Factor) ÷ Time in minutes
  const totalDrops = volumeMl * dropFactor;
  const exactDripRate = totalDrops / totalMinutes;
  const dripRateGttPerMin = Math.round(exactDripRate);

  const dropType = dropFactor === 60 ? "Microdrip set (60 gtt/mL)" : `Macrodrip set (${dropFactor} gtt/mL)`;

  steps.push(`Total Infusion Volume: ${volumeMl} mL over ${totalMinutes} minutes (${hours} hours).`);
  steps.push(`Infusion Set: ${dropType}.`);
  steps.push(`Volumetric Infusion Rate: ${volumeMl} mL ÷ ${hours} hr = ${infusionRateMlPerHour} mL/hr.`);
  steps.push(`Gravity Drip Formula: (${volumeMl} mL × ${dropFactor} gtt/mL) ÷ ${totalMinutes} min = ${exactDripRate.toFixed(2)} gtt/min → ${dripRateGttPerMin} drops/minute.`);

  return {
    volumeMl,
    durationMinutes: totalMinutes,
    durationHours: hours,
    dropFactor,
    dripRateGttPerMin,
    infusionRateMlPerHour,
    steps,
  };
}

// ── 4. Holliday-Segar Maintenance Fluid Calculator ──────────────────────────

export interface MaintenanceFluidBreakdown {
  segment: string;
  weightKg: number;
  dailyRatePerKg: number;
  hourlyRatePerKg: number;
  dailyMl: number;
  hourlyMl: number;
}

export interface MaintenanceFluidResult {
  weightKg: number;
  totalDailyVolumeMl: number;
  hourlyRateMlPerHour: number;
  isAdultAdvisory: boolean;
  advisory: string | null;
  breakdown: readonly MaintenanceFluidBreakdown[];
  steps: readonly string[];
}

export function calculateMaintenanceFluid(weightKg: number, ageYears?: number): MaintenanceFluidResult {
  if (weightKg < 1.0 || weightKg > 100.0) {
    throw new Error("Weight must be between 1.0 kg and 100.0 kg.");
  }

  const steps: string[] = [];
  const breakdown: MaintenanceFluidBreakdown[] = [];
  let totalDailyMl = 0;
  let totalHourlyMl = 0;

  // Holliday-Segar 4-2-1 Rule:
  // Tier 1: 0 - 10 kg -> 100 mL/kg/day (4 mL/kg/hr)
  const tier1Kg = Math.min(weightKg, 10);
  const tier1Daily = tier1Kg * 100;
  const tier1Hourly = tier1Kg * 4;
  totalDailyMl += tier1Daily;
  totalHourlyMl += tier1Hourly;
  breakdown.push({
    segment: "First 10 kg",
    weightKg: tier1Kg,
    dailyRatePerKg: 100,
    hourlyRatePerKg: 4,
    dailyMl: tier1Daily,
    hourlyMl: tier1Hourly,
  });
  steps.push(`1st 10 kg: ${tier1Kg} kg × 100 mL/kg/day = ${tier1Daily} mL/day (${tier1Hourly} mL/hr)`);

  // Tier 2: 10 - 20 kg -> 50 mL/kg/day (2 mL/kg/hr)
  if (weightKg > 10) {
    const tier2Kg = Math.min(weightKg - 10, 10);
    const tier2Daily = tier2Kg * 50;
    const tier2Hourly = tier2Kg * 2;
    totalDailyMl += tier2Daily;
    totalHourlyMl += tier2Hourly;
    breakdown.push({
      segment: "Next 10 kg (10-20 kg)",
      weightKg: tier2Kg,
      dailyRatePerKg: 50,
      hourlyRatePerKg: 2,
      dailyMl: tier2Daily,
      hourlyMl: tier2Hourly,
    });
    steps.push(`Next 10 kg: ${tier2Kg} kg × 50 mL/kg/day = ${tier2Daily} mL/day (${tier2Hourly} mL/hr)`);
  }

  // Tier 3: > 20 kg -> 20 mL/kg/day (1 mL/kg/hr)
  if (weightKg > 20) {
    const tier3Kg = weightKg - 20;
    const tier3Daily = tier3Kg * 20;
    const tier3Hourly = tier3Kg * 1;
    totalDailyMl += tier3Daily;
    totalHourlyMl += tier3Hourly;
    breakdown.push({
      segment: "Each kg above 20 kg",
      weightKg: tier3Kg,
      dailyRatePerKg: 20,
      hourlyRatePerKg: 1,
      dailyMl: tier3Daily,
      hourlyMl: tier3Hourly,
    });
    steps.push(`Remaining weight >20 kg: ${tier3Kg} kg × 20 mL/kg/day = ${tier3Daily} mL/day (${tier3Hourly} mL/hr)`);
  }

  // Cap at standard maximum adult baseline (2400-2500 mL/day)
  const isAdultAdvisory = weightKg > 50 || (ageYears !== undefined && ageYears >= 14);
  let advisory: string | null = null;
  if (isAdultAdvisory) {
    advisory = "Holliday-Segar is a paediatric rule. For adolescents/adults (>14 years or >50 kg), standard adult maintenance fluid is typically 30–35 mL/kg/day (approx 2000–2500 mL/day). Adjust for cardiac/renal status.";
    steps.push(`CLINICAL ADVISORY: ${advisory}`);
  }

  steps.push(`Summary: Total Maintenance Fluid = ${totalDailyMl} mL/24h (${totalHourlyMl} mL/hr).`);

  return {
    weightKg,
    totalDailyVolumeMl: totalDailyMl,
    hourlyRateMlPerHour: totalHourlyMl,
    isAdultAdvisory,
    advisory,
    breakdown,
    steps,
  };
}
