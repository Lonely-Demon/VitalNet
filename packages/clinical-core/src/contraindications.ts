// Medication/condition/symptom contraindication flags. Ported from
// backend/app/ml/contraindications.py::RULES (previously hand-mirrored a
// second time as frontend/src/utils/clinicalRules.js::CONTRAINDICATION_RULES).
//
// Scope: free-text keyword matching against a small curated list — NOT a
// general drug-interaction database. Never changes the triage tier; the
// caller folds any flag into a needs_review signal.

export interface ContraindicationRule {
  id: string;
  medicationTerms: readonly string[];
  conditionTerms?: readonly string[];
  symptomCodes?: readonly string[];
  maxHeartRate?: number;
  message: string;
}

export const CONTRAINDICATION_RULES: readonly ContraindicationRule[] = [
  {
    id: "nsaid_renal",
    medicationTerms: ["ibuprofen", "diclofenac", "naproxen", "nsaid", "mefenamic", "aceclofenac"],
    conditionTerms: ["kidney", "renal", "ckd", "dialysis"],
    message: "NSAID use with known kidney/renal disease — NSAIDs can worsen renal function; verify before recommending.",
  },
  {
    id: "ace_arb_renal",
    medicationTerms: ["enalapril", "lisinopril", "ramipril", "captopril", "losartan", "telmisartan", "olmesartan", "ace inhibitor"],
    conditionTerms: ["kidney", "renal", "ckd", "dialysis"],
    message: "ACE inhibitor/ARB with known kidney disease — risk of hyperkalemia or worsening renal function; verify before recommending.",
  },
  {
    id: "metformin_vomiting",
    medicationTerms: ["metformin", "glucophage"],
    symptomCodes: ["persistent_vomiting"],
    message: "Metformin with persistent vomiting — risk of dehydration-related lactic acidosis; verify before continuing metformin.",
  },
  {
    id: "anticoagulant_bleeding",
    medicationTerms: ["warfarin", "acitrom", "dabigatran", "apixaban", "rivaroxaban", "heparin", "anticoagulant"],
    symptomCodes: ["severe_bleeding"],
    message: "Anticoagulant use with active severe bleeding — bleeding risk is compounded; flag for urgent clinical attention.",
  },
  {
    id: "beta_blocker_bradycardia",
    medicationTerms: ["atenolol", "metoprolol", "propranolol", "bisoprolol", "beta blocker", "beta-blocker"],
    maxHeartRate: 55,
    message: "Beta-blocker use with a low heart rate — may indicate excessive beta-blockade; verify before further heart-rate-lowering treatment.",
  },
  {
    id: "hypoglycemia_agent_altered_consciousness",
    medicationTerms: ["insulin", "glimepiride", "glipizide", "glyburide", "gliclazide", "sulfonylurea"],
    symptomCodes: ["altered_consciousness"],
    message: "Insulin/sulfonylurea use with altered consciousness — consider hypoglycemia; verify blood glucose before assuming another cause.",
  },
];

export interface ContraindicationInput {
  current_medications: string | null;
  known_conditions: string | null;
  symptoms: readonly string[];
  heart_rate: number | null;
}

/** Returns an array of human-readable contraindication flags (possibly
 * empty). Never changes the triage tier. */
export function checkContraindications(form: ContraindicationInput): string[] {
  const medications = (form.current_medications || "").toLowerCase();
  if (!medications) return [];

  const conditions = (form.known_conditions || "").toLowerCase();
  const symptoms = new Set(form.symptoms || []);
  const heartRate = form.heart_rate;

  const flags: string[] = [];
  for (const rule of CONTRAINDICATION_RULES) {
    if (!rule.medicationTerms.some((term) => medications.includes(term))) continue;

    const conditionHit = Boolean(rule.conditionTerms) && rule.conditionTerms!.some((term) => conditions.includes(term));
    const symptomHit = Boolean(rule.symptomCodes) && rule.symptomCodes!.some((code) => symptoms.has(code));
    const heartRateHit = rule.maxHeartRate !== undefined && heartRate !== null && heartRate < rule.maxHeartRate;

    if (conditionHit || symptomHit || heartRateHit) flags.push(rule.message);
  }
  return flags;
}
