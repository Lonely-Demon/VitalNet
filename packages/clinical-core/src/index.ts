// @vitalnet/clinical-core — public API. See README.md for the package's
// purpose and design invariants.

export {
  intakeFormSchema,
  validateIntakeForm,
  stripControlChars,
  ALLOWED_SYMPTOMS,
  ALLOWED_SYMPTOMS_SET,
  MAX_SYMPTOMS,
  PATIENT_KEY_RE,
  type IntakeForm,
  type Symptom,
} from "./schema.js";

export {
  bandScore,
  spo2Score,
  bpSysScore,
  tempScore,
  adultHrScore,
  pediatricHrScore,
  pediatricBpScore,
  pediatricTempScore,
  news2LikeScore,
  qsofaScore,
  SPO2_BANDS,
  BP_SYS_BANDS,
  TEMP_BANDS,
  ADULT_HR_BANDS,
  type Band,
  type News2Result,
} from "./rules/bands.js";

export { checkOverrides, news2ConcerningVital, type FiredRule, type OverrideInput } from "./rules/rules.js";

export { assignTier, type Tier, type EngineInput, type EngineResult } from "./rules/engine.js";

export { buildFeatureMap, orderFeatureVector, type FeatureFormInput, type FeatureMap } from "./features.js";

export {
  evaluateTrees,
  explainPrediction,
  type TreeJson,
  type TreeNode,
  type EvaluationResult,
  type FeatureAttribution,
} from "./treeEvaluator.js";

export { checkContraindications, CONTRAINDICATION_RULES, type ContraindicationRule, type ContraindicationInput } from "./contraindications.js";

export { generatePatientKey, normalizePatientKey, PATIENT_KEY_FORMAT_RE } from "./patientKey.js";

export {
  triage,
  DEFAULT_TRIAGE_MODE,
  type TriageMode,
  type TriageFormInput,
  type TriageOptions,
  type TriageResult,
  type ModelOpinion,
} from "./triage.js";
