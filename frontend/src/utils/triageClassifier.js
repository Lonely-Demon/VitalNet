// frontend/src/utils/triageClassifier.js
//
// Client-side (offline) triage using the ClinicalFeatureEngineer's 45-feature
// pipeline (ported from backend/app/ml/clinical_features.py) plus a pure-JS
// evaluation of the trained tree ensemble — NO onnxruntime-web WASM.
//
// Why no ONNX runtime: the model is a gradient-boosted tree ensemble, which
// evaluates in a few thousand float comparisons. Shipping a general ~12 MB WASM
// inference engine to precache and cold-compile for that is pure overhead on the
// 2 GB-class Android tablets and metered rural links this app targets. Instead
// the model is exported as compact JSON (/models/triage_trees.json, ~1 MB, gzips
// far smaller) and walked by treeEvaluator.js. Predictions are argmax-identical
// to the server, enforced by a golden-vector parity test.
//
// Layered design (mirrors backend/app/ml/classifier.py, so offline == online):
//   1. Deterministic safety net → EMERGENCY for extreme presentations, even for
//      inputs the model never saw ("classify under any circumstances").
//   2. The tree model for everything else.
//   3. A NEWS2 concerning-vital floor: never leave a concerning vital as ROUTINE.
//   4. If the tree JSON can't load at all, rules-only triage still returns a
//      safe result — triage never fails.

import { evaluateTrees } from './treeEvaluator.js'
import { safetyNetCheck, news2ConcerningVital } from './clinicalRules.js'

const TREES_PATH = '/models/triage_trees.json'
const FEATURES_CONFIG_PATH = '/models/features_config.json'
const TRIAGE_LABELS = ['ROUTINE', 'URGENT', 'EMERGENCY']

// Abstention thresholds — mirror classifier.py (LOW_CONFIDENCE_PROBA/MARGIN).
const LOW_CONFIDENCE_PROBA = 0.55
const LOW_CONFIDENCE_MARGIN = 0.15

// ---------------------------------------------------------------------------
// Model loading (compact tree JSON + canonical feature order)
// ---------------------------------------------------------------------------

let _treeJson = null
let _featureNames = null   // canonical feature order, fetched from features_config.json
let _loadPromise = null

/**
 * Load and cache the tree ensemble JSON + the feature-order manifest. Called
 * once (warmup) — not per submission. Resets its promise on failure so a later
 * call retries. Fetching feature order from features_config.json (not a
 * hard-coded array) means a backend feature-set change can never silently
 * desync this file from the trained model.
 */
export async function loadModel() {
  if (_treeJson && _featureNames) return _treeJson
  if (_loadPromise) return _loadPromise

  _loadPromise = Promise.all([
    fetch(TREES_PATH).then((r) => {
      if (!r.ok) throw new Error(`triage_trees.json fetch failed: ${r.status}`)
      return r.json()
    }),
    fetch(FEATURES_CONFIG_PATH).then((r) => {
      if (!r.ok) throw new Error(`features_config.json fetch failed: ${r.status}`)
      return r.json()
    }),
  ]).then(([trees, config]) => {
    _treeJson = trees
    _featureNames = config.feature_names
    _loadPromise = null
    console.log(`[VitalNet] Offline triage model loaded (${config.num_features}-feature, v${config.model_version}, pure-JS)`)
    return trees
  }).catch((err) => {
    _loadPromise = null
    console.error('[VitalNet] Offline model load failed (rules-only fallback will be used):', err)
    throw err
  })

  return _loadPromise
}

/**
 * Prefetch + a dummy evaluation so the first real offline submission is instant.
 * Guarded against concurrent calls (React strict mode double-invokes effects).
 */
let _warmupPromise = null
export async function warmupModel() {
  if (_warmupPromise) return _warmupPromise
  _warmupPromise = (async () => {
    const trees = await loadModel()
    evaluateTrees(trees, new Array(_featureNames.length).fill(0))
    console.log('[VitalNet] Offline triage warmup complete')
  })()
  try {
    await _warmupPromise
  } catch (err) {
    _warmupPromise = null // allow retry on failure
    throw err
  }
  return _warmupPromise
}

// ---------------------------------------------------------------------------
// Clinical feature engineering (port of backend/clinical_features.py)
// ---------------------------------------------------------------------------

const HIGH_RISK_COMPLAINTS = new Set([
  'chest pain', 'chest tightness', 'difficulty breathing',
  'breathlessness', 'altered consciousness', 'confusion',
  'severe bleeding', 'seizure', 'unconscious',
])

const TRAUMA_INDICATORS = new Set([
  'injury', 'trauma', 'fall', 'accident', 'hit', 'cut',
  'burned', 'fracture', 'wound',
])

const OBSTETRIC_COMPLAINTS = new Set([
  'pregnancy', 'pregnant', 'delivery', 'labor', 'bleeding',
  'contractions', 'baby', 'birth',
])

const CRITICAL_SYMPTOMS = [
  'chest_pain', 'breathlessness', 'altered_consciousness',
  'severe_bleeding', 'seizure', 'high_fever',
]

const SYMPTOM_SEVERITY_WEIGHTS = {
  altered_consciousness: 4.0,
  severe_bleeding: 4.0,
  seizure: 4.0,
  chest_pain: 3.0,
  breathlessness: 3.0,
  high_fever: 2.0,
}

/** Clamp value between lo and hi */
function clamp(val, lo, hi) {
  return Math.max(lo, Math.min(hi, val))
}

/** Check if any term in a set appears in a string */
function containsAny(text, termSet) {
  const lower = text.toLowerCase()
  for (const term of termSet) {
    if (lower.includes(term)) return true
  }
  return false
}

/**
 * Compute the clinical feature map from IntakeForm data.
 * Key names MUST match the Python ClinicalFeatureEngineer output keys
 * exactly — the assembly ORDER is handled separately by
 * orderFeatureVector() using features_config.json, so key order in the
 * returned object here does not need to match the model's input order.
 */
export function buildFeatureMap(formData) {
  const symptoms = formData.symptoms || []
  const age = formData.patient_age ?? -1
  const sex = formData.patient_sex === 'male' ? 1 : 0
  const bpSys = formData.bp_systolic ?? -1
  const bpDia = formData.bp_diastolic ?? -1
  const spo2 = formData.spo2 ?? -1
  const hr = formData.heart_rate ?? -1
  const temp = formData.temperature ?? -1
  const complaint = (formData.chief_complaint || '').toLowerCase()
  const duration = (formData.complaint_duration || '').toLowerCase()
  const location = (formData.location || '').toLowerCase()
  const conditions = (formData.known_conditions || '').toLowerCase()

  // Use fallbacks for derived features (same as Python)
  const safeBpSys = bpSys > 0 ? bpSys : 120
  const safeBpDia = bpDia > 0 ? bpDia : 80
  const safeHr = hr > 0 ? hr : 75
  const safeSpo2 = spo2 > 0 ? spo2 : 97
  const safeTemp = temp > 0 ? temp : 37.0
  const safeAge = age > 0 ? age : 40
  // Python's risk-scoring helper methods default age via `.get('patient_age',
  // 40)` — only when the field is truly absent, NOT when it's a real 0 (a
  // newborn). `safeAge` clamps any non-positive value to 40, which silently
  // reclassified real newborns as 40-year-old adults for every age-gated risk
  // score below (caught by the JS/Python feature-parity test). Use this for
  // every age comparison Python makes via that pattern; safeAge is kept only
  // for spo2_age_ratio, whose Python source uses the clamp-on-falsy form.
  const ageOrDefault = (formData.patient_age === null || formData.patient_age === undefined)
    ? 40
    : formData.patient_age

  // Symptom flags
  const chestPain = symptoms.includes('chest_pain') ? 1 : 0
  const breathlessness = symptoms.includes('breathlessness') ? 1 : 0
  const alteredConsciousness = symptoms.includes('altered_consciousness') ? 1 : 0
  const severeBleeding = symptoms.includes('severe_bleeding') ? 1 : 0
  const seizure = symptoms.includes('seizure') ? 1 : 0
  const highFever = symptoms.includes('high_fever') ? 1 : 0
  const symptomCount = CRITICAL_SYMPTOMS.filter(s => symptoms.includes(s)).length

  // --- 14 basic features ---
  // (indices 0-13)

  // --- Vital sign derived features (12) ---
  // Gated on the SAFE (already-defaulted) values, matching Python exactly —
  // clinical_features.py's bp_sys/bp_dia are `raw_data.get(...) or <default>`
  // before this check, so the condition there is effectively always true;
  // gating on the raw (possibly -1/missing) value here made this branch
  // diverge from Python whenever a vital was missing (parity-test caught it).
  const pulsePressure = (safeBpSys > 0 && safeBpDia > 0) ? safeBpSys - safeBpDia : 40
  const meanArterialPressure = (safeBpSys > 0 && safeBpDia > 0) ? (safeBpSys + 2 * safeBpDia) / 3 : 93
  const shockIndex = (safeBpSys > 0 && safeHr > 0) ? safeHr / safeBpSys : 0.6
  const spo2AgeRatio = (safeSpo2 > 0 && safeAge > 0) ? safeSpo2 / Math.max(safeAge, 1) : 2.4
  const tempDeviation = safeTemp > 0 ? Math.abs(safeTemp - 37.0) : 0.0

  // Cardiac risk score
  let cardiacRisk = 0
  if (ageOrDefault > 65) cardiacRisk += 2
  else if (ageOrDefault > 45) cardiacRisk += 1
  if (safeBpSys > 160) cardiacRisk += 2
  if (safeHr > 100 || safeHr < 60) cardiacRisk += 1.5
  if (chestPain) cardiacRisk += 3
  if (breathlessness) cardiacRisk += 1.5
  cardiacRisk = Math.min(cardiacRisk, 10)

  // Respiratory distress score
  let respDistress = 0
  if (safeSpo2 < 90) respDistress += 4
  else if (safeSpo2 < 94) respDistress += 2
  if (safeHr > 110) respDistress += 1.5
  if (breathlessness) respDistress += 3

  // Hemodynamic instability
  let hemodynamic = 0
  if (safeBpSys < 90) hemodynamic += 4
  else if (safeBpSys > 180) hemodynamic += 2
  if (safeHr > 130) hemodynamic += 3
  else if (safeHr < 50) hemodynamic += 2
  if (safeBpSys > 0) {
    const si = safeHr / safeBpSys
    if (si > 1.0) hemodynamic += 3
    else if (si > 0.8) hemodynamic += 1.5
  }

  // Sepsis risk (qSOFA-like)
  let sepsisRisk = 0
  if (safeTemp > 38.0 || safeTemp < 36.0) sepsisRisk += 1
  if (safeBpSys < 100) sepsisRisk += 2
  if (safeHr > 90) sepsisRisk += 1
  if (alteredConsciousness) sepsisRisk += 2
  if (highFever) sepsisRisk += 1.5

  // Pediatric adjustment
  let pediatricAdj = 0
  if (ageOrDefault < 18) {
    if (ageOrDefault < 2) {
      if (safeHr > 160 || safeHr < 100) pediatricAdj += 2
    } else if (ageOrDefault < 6) {
      if (safeHr > 140 || safeHr < 80) pediatricAdj += 1.5
    } else if (ageOrDefault < 12) {
      if (safeHr > 120 || safeHr < 70) pediatricAdj += 1
    }
    if (safeTemp > 38.5) pediatricAdj += 2
  }

  // Geriatric adjustment
  let geriatricAdj = 0
  if (ageOrDefault >= 65) {
    if (safeTemp < 36.5) geriatricAdj += 1.5
    if (safeBpSys < 100) geriatricAdj += 2
    if (ageOrDefault > 80) geriatricAdj += 1
  }

  // Pregnancy adjustment
  let pregnancyAdj = 0
  if (formData.patient_sex === 'female' && ageOrDefault >= 15 && ageOrDefault <= 45) {
    if (conditions.includes('pregnan') || conditions.includes('expecting')) pregnancyAdj += 1
    if (containsAny(complaint, OBSTETRIC_COMPLAINTS)) pregnancyAdj += 2
  }

  // --- Symptom interaction features (8) ---
  const cardiopulmonaryCluster = chestPain * breathlessness
  const neurologicalCluster = alteredConsciousness * seizure
  const hemorrhagicCluster = severeBleeding * (safeBpSys < 90 ? 1 : 0)
  const infectiousCluster = highFever * symptoms.length

  // Symptom severity score
  let symptomSeverity = 0
  for (const s of symptoms) {
    symptomSeverity += SYMPTOM_SEVERITY_WEIGHTS[s] || 1.0
  }
  symptomSeverity = Math.min(symptomSeverity, 15)

  // Duration risk
  let durationRisk = 1.5 // default
  if (duration.includes('less than 1 hour') || duration.includes('< 1 hour')) durationRisk = 3.0
  else if (duration.includes('1') && duration.includes('6 hour')) durationRisk = 2.5
  else if (duration.includes('6') && duration.includes('24 hour')) durationRisk = 2.0
  else if (duration.includes('1') && duration.includes('3 day')) durationRisk = 1.5
  else if (duration.includes('more than 3 day') || duration.includes('> 3 day')) durationRisk = 1.0

  // Chief complaint risk
  let complaintRisk = 1.0
  if (containsAny(complaint, HIGH_RISK_COMPLAINTS)) complaintRisk = 4.0
  else if (containsAny(complaint, TRAUMA_INDICATORS)) complaintRisk = 3.0

  // Comorbidity multiplier
  let comorbidityMult = 1.0
  if (conditions) {
    const highRiskConditions = ['diabetes', 'heart', 'cardiac', 'hypertension', 'kidney', 'renal',
      'copd', 'asthma', 'cancer', 'stroke', 'liver']
    let riskCount = 0
    for (const c of highRiskConditions) {
      if (conditions.includes(c)) riskCount++
    }
    comorbidityMult = Math.min(1.0 + riskCount * 0.5, 3.0)
  }

  // --- Age-specific features (6) ---
  // Pediatric fever risk
  let pediatricFeverRisk = 0
  if (ageOrDefault < 18) {
    if (ageOrDefault < 0.25 && safeTemp > 38.0) pediatricFeverRisk += 4
    else if (ageOrDefault < 2 && safeTemp > 39.0) pediatricFeverRisk += 3
    else if (safeTemp > 40.0) pediatricFeverRisk += 2
    if (highFever) pediatricFeverRisk += 1
  }

  // Elderly fall risk
  let elderlyFallRisk = 0
  if (ageOrDefault >= 65) {
    if (ageOrDefault > 75) elderlyFallRisk += 1
    if (ageOrDefault > 85) elderlyFallRisk += 2
    const fallKeywords = ['fall', 'fell', 'slip', 'trip', 'dizzy', 'weakness']
    if (fallKeywords.some(k => complaint.includes(k))) elderlyFallRisk += 3
  }

  // Adult cardiac risk
  let adultCardiacRisk = 0
  if (ageOrDefault >= 18 && ageOrDefault <= 65) {
    adultCardiacRisk = cardiacRisk * 0.8
  }

  // Obstetric emergency risk
  let obstetricRisk = 0
  if (formData.patient_sex === 'female' && ageOrDefault >= 15 && ageOrDefault <= 45) {
    for (const term of OBSTETRIC_COMPLAINTS) {
      if (complaint.includes(term)) { obstetricRisk += 2; break }
    }
    if (complaint.includes('bleeding')) obstetricRisk += 1.5
  }

  // Trauma severity
  let traumaSeverity = 0
  for (const term of TRAUMA_INDICATORS) {
    if (complaint.includes(term)) { traumaSeverity += 2; break }
  }
  if (safeBpSys < 90) traumaSeverity += 3
  if (safeHr > 120) traumaSeverity += 2

  // Mental health crisis
  let mentalHealthCrisis = 0
  const mhTerms = ['suicid', 'depress', 'anxiety', 'panic', 'psycho', 'mental', 'confused', 'agitat', 'violent']
  for (const term of mhTerms) {
    if (complaint.includes(term)) { mentalHealthCrisis += 2; break }
  }
  if (alteredConsciousness) mentalHealthCrisis += 1

  // --- Contextual features (5) ---
  const hour = new Date().getHours()
  let timeOfDayRisk = 1.0
  if (hour >= 22 || hour <= 6) timeOfDayRisk = 1.5
  else if (hour >= 18 && hour <= 22) timeOfDayRisk = 1.2

  const month = new Date().getMonth() + 1 // 1-indexed
  let seasonalRisk = 1.0
  if ([12, 1, 2].includes(month)) seasonalRisk = 1.3
  else if ([6, 7, 8].includes(month)) seasonalRisk = 1.2

  const geographicRisk = 1.0 // placeholder
  const epidemicAlertLevel = 0.0 // placeholder

  let healthcareAccessibility = 0.7 // default
  const ruralTerms = ['village', 'rural', 'remote', 'tribal']
  const urbanTerms = ['city', 'town', 'urban', 'metro']
  if (ruralTerms.some(t => location.includes(t))) healthcareAccessibility = 0.5
  else if (urbanTerms.some(t => location.includes(t))) healthcareAccessibility = 1.0

  // --- Feature map, keyed by the same names ClinicalFeatureEngineer uses ---
  // Values are assembled into the final vector using the canonical order
  // fetched from features_config.json (see loadModel()) — NOT the order
  // they're listed here, so this object's key order is not load-bearing.
  return {
    age, sex, bp_systolic: bpSys, bp_diastolic: bpDia, spo2, heart_rate: hr,
    temperature: temp, symptom_count: symptomCount,
    chest_pain: chestPain, breathlessness, altered_consciousness: alteredConsciousness,
    severe_bleeding: severeBleeding, seizure, high_fever: highFever,
    pulse_pressure: pulsePressure, mean_arterial_pressure: meanArterialPressure,
    shock_index: shockIndex, spo2_age_ratio: spo2AgeRatio, temp_deviation: tempDeviation,
    cardiac_risk_score: cardiacRisk, respiratory_distress_score: respDistress,
    hemodynamic_instability: hemodynamic, sepsis_risk_score: sepsisRisk,
    pediatric_adjustment: pediatricAdj, geriatric_adjustment: geriatricAdj,
    pregnancy_adjustment: pregnancyAdj,
    cardiopulmonary_cluster: cardiopulmonaryCluster, neurological_cluster: neurologicalCluster,
    hemorrhagic_cluster: hemorrhagicCluster, infectious_cluster: infectiousCluster,
    symptom_severity_score: symptomSeverity, symptom_duration_risk: durationRisk,
    chief_complaint_risk: complaintRisk, comorbidity_multiplier: comorbidityMult,
    pediatric_fever_risk: pediatricFeverRisk, elderly_fall_risk: elderlyFallRisk,
    adult_cardiac_risk: adultCardiacRisk, obstetric_emergency_risk: obstetricRisk,
    trauma_severity_score: traumaSeverity, mental_health_crisis: mentalHealthCrisis,
    time_of_day_risk: timeOfDayRisk, seasonal_risk: seasonalRisk,
    geographic_risk: geographicRisk, epidemic_alert_level: epidemicAlertLevel,
    healthcare_accessibility: healthcareAccessibility,
  }
}

/**
 * Assemble the ordered plain-number array using the canonical feature order
 * fetched from features_config.json. Throws if the feature order hasn't loaded.
 */
function orderFeatureVector(featureMap) {
  if (!_featureNames) {
    throw new Error('Feature order not loaded yet — call loadModel() before running inference')
  }
  return _featureNames.map((name) => {
    const v = featureMap[name]
    return typeof v === 'number' ? v : 0
  })
}

// ---------------------------------------------------------------------------
// Inference — layered, mirrors backend/app/ml/classifier.py::predict_triage
// ---------------------------------------------------------------------------

/**
 * Run offline triage on form data. Always returns a result — never throws for
 * well-formed input, even if the tree model failed to load (rules-only
 * fallback). Shape:
 *   { triageLevel, confidence, lowConfidence, isLocal: true,
 *     safetyNet, news2Floor, modelUnavailable }
 */
export async function runTriage(formData) {
  // Layer 1 — deterministic safety net. Works with no model at all.
  const safetyReason = safetyNetCheck(formData)
  if (safetyReason) {
    return {
      triageLevel: 'EMERGENCY',
      confidence: 1,
      lowConfidence: false,
      isLocal: true,
      safetyNet: true,
      news2Floor: false,
      modelUnavailable: false,
    }
  }

  // Layer 2 — trained tree model (fall back to rules if it can't load).
  let triageLevel = 'ROUTINE'
  let confidence = null
  let lowConfidence = false
  let modelUnavailable = false

  try {
    const trees = await loadModel()
    const featureVector = orderFeatureVector(buildFeatureMap(formData))
    const { classIndex, probabilities } = evaluateTrees(trees, featureVector)
    triageLevel = TRIAGE_LABELS[classIndex] ?? 'ROUTINE'
    confidence = probabilities[classIndex]
    const sorted = [...probabilities].sort((a, b) => b - a)
    const margin = sorted.length > 1 ? sorted[0] - sorted[1] : 1
    lowConfidence = confidence < LOW_CONFIDENCE_PROBA || margin < LOW_CONFIDENCE_MARGIN
  } catch {
    // Model unavailable — rules-only fallback. Never fail to triage.
    modelUnavailable = true
    triageLevel = 'ROUTINE'
  }

  // Layer 3 — NEWS2 concerning-vital floor: never leave a concerning vital as ROUTINE.
  let news2Floor = false
  if (triageLevel === 'ROUTINE' && news2ConcerningVital(formData)) {
    triageLevel = 'URGENT'
    lowConfidence = false
    news2Floor = true
  }

  return {
    triageLevel,
    confidence,
    lowConfidence,
    isLocal: true,
    safetyNet: false,
    news2Floor,
    modelUnavailable,
  }
}
