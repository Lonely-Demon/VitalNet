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

export { assignTier, resolveEffectiveAge, type Tier, type EngineInput, type EngineResult } from "./rules/engine.js";

export {
  buildFeatureMap,
  orderFeatureVector,
  getUnmeasuredFeatureSet,
  type FeatureFormInput,
  type FeatureMap,
} from "./features.js";

export {
  evaluateTrees,
  explainPrediction,
  evaluateNodeTernary,
  traverseTreeTernary,
  computeSaabasAttributions,
  assessFeatureCompleteness,
  assessCompleteness,
  CORE_VITALS,
  type TreeJson,
  type TreeNode,
  type EvaluationResult,
  type FeatureAttribution,
  type ExplainOptions,
  type NodeEvaluationResult,
  type FeatureCompletenessStatus,
  type CompletenessState,
  type FeatureCompletenessResult,
} from "./treeEvaluator.js";

export {
  checkContraindications,
  CONTRAINDICATION_RULES,
  type ContraindicationRule,
  type ContraindicationInput,
} from "./contraindications.js";

export {
  generatePatientKey,
  generateUnbiasedPatientKey,
  normalizePatientKey,
  deriveDeterministicPatientKey,
  deriveAbhaKey,
  buildIndicPhoneticSkeleton,
  ALPHABET,
  MAX_UNBIASED_BYTE,
  PATIENT_KEY_FORMAT_RE,
} from "./patientKey.js";

export {
  parseAbhaQr,
  parseAbhaQrPayload,
  parsePatientQrPayload,
  type ParsedAbhaQr,
  type ParsedQrIdentity,
} from "./abhaScanner.js";

export {
  encodeEmergencySms,
  encodeEmergencySmsFrame,
  decodeEmergencySms,
  decodeEmergencySmsFrame,
  computeCrc24,
  uuidToBytes,
  bytesToUuid,
  base64UrlEncode,
  base64UrlDecode,
  type SmsFrameInput,
  type DecodedSmsFrame,
} from "./smsCodec.js";

export {
  triage,
  DEFAULT_TRIAGE_MODE,
  type TriageMode,
  type TriageFormInput,
  type TriageOptions,
  type TriageResult,
  type ModelOpinion,
} from "./triage.js";

export {
  calculateWeightBasedDose,
  calculateOrsVolume,
  calculateIvDripRate,
  calculateMaintenanceFluid,
  PEDIATRIC_DRUG_PRESETS,
  ASHA_SCOPE_DRUG_IDS,
  FREQUENCY_METADATA,
  DURATION_METADATA,
  type DoseFrequency,
  type TreatmentDuration,
  type FrequencyMeta,
  type DurationMeta,
  type LiquidConcentration,
  type PediatricDrugPreset,
  type WeightDoseInput,
  type WeightDoseResult,
  type DehydrationPlan,
  type OrsPlanInput,
  type OrsPlanResult,
  type DropFactor,
  type IvDripRateInput,
  type IvDripRateResult,
  type MaintenanceFluidBreakdown,
  type MaintenanceFluidResult,
} from "./calculators.js";
