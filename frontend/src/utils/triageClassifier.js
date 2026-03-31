// frontend/src/utils/triageClassifier.js
//
// Client-side ONNX triage inference using the enhanced 45-feature model.
// Ports backend/clinical_features.py ClinicalFeatureEngineer to JavaScript.
//
import {
  CONFIDENCE_FLOOR,
  EXPECTED_ONNX_SHA256,
  FEATURE_SCHEMA_VERSION,
  MODEL_VERSION,
  RED_FLAG_RULES,
  SYMPTOM_NORMALIZATION_MAP,
  UNCERTAINTY_FLOOR,
} from './modelContract'

// ONNX Runtime will be loaded dynamically to avoid loading for non-ASHA users
let ort = null
let ortInitializationPromise = null

async function initializeOnnxRuntime() {
  if (ortInitializationPromise) {
    return ortInitializationPromise
  }
  
  ortInitializationPromise = (async () => {
    if (ort) return ort
    
    // Dynamic import to avoid loading for non-ASHA users
    ort = await import('onnxruntime-web')
    
    // Disable multi-threading — requires COOP/COEP headers that Vite dev server
    // and many production hosts don't set. Single-threaded WASM is fast enough
    // for a 45-feature model inference (<10 ms).
    ort.env.wasm.numThreads = 1
    return ort
  })()
  
  return ortInitializationPromise
}

const MODEL_PATH = '/models/triage_classifier.onnx'
const TRIAGE_LABELS = ['ROUTINE', 'URGENT', 'EMERGENCY']
const NUM_FEATURES = 45
const UNKNOWN_LABEL_MESSAGE = 'Unknown model label index — requiring human review'

// ---------------------------------------------------------------------------
// Session management
// ---------------------------------------------------------------------------

function normalizeSymptom(symptom) {
  const raw = String(symptom || '').trim().toLowerCase()
  if (!raw) return ''

  const cleaned = raw
    .replaceAll('_', ' ')
    .replaceAll('/', ' ')
    .replaceAll('-', ' ')
    .replace(/[^a-z0-9 ]+/g, '')
    .replace(/\s+/g, ' ')
    .trim()

  return SYMPTOM_NORMALIZATION_MAP[cleaned] || cleaned.replaceAll(' ', '_')
}

function normalizeSymptoms(symptoms) {
  const list = Array.isArray(symptoms) ? symptoms : []
  const seen = new Set()
  const normalized = []

  for (const symptom of list) {
    const canonical = normalizeSymptom(symptom)
    if (canonical && !seen.has(canonical)) {
      normalized.push(canonical)
      seen.add(canonical)
    }
  }

  return normalized
}

function coerceNumeric(value, fallback) {
  if (value === '' || value == null) return fallback
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : fallback
}

function assessRedFlags(formData, symptoms) {
  const complaint = String(formData.chief_complaint || '').toLowerCase()
  const matched = []

  for (const [ruleName, rule] of Object.entries(RED_FLAG_RULES)) {
    const symptomHit = rule.symptoms.some((symptom) => symptoms.includes(symptom))
    const complaintHit = rule.complaintTerms.some((term) => complaint.includes(term))
    if (symptomHit || complaintHit) matched.push(ruleName)
  }

  return {
    redFlags: matched,
    mustEscalate: matched.length > 0,
  }
}

/**
 * Load and cache the ONNX session.
 * Called once on ASHA panel mount — not on every submission.
 * Retries on failure (resets _loadPromise so next call retries).
 */
let _session = null
let _loadPromise = null
let _modelHash = null

export async function loadModel() {
  if (_session) return _session
  if (_loadPromise) return _loadPromise

  _loadPromise = initializeOnnxRuntime().then(loadedOrt => {
    return loadedOrt.InferenceSession.create(MODEL_PATH, {
      executionProviders: ['wasm'],
      graphOptimizationLevel: 'all',
    })
  }).then((session) => {
    _session = session
    _modelHash = EXPECTED_ONNX_SHA256
    _loadPromise = null
    console.log('[VitalNet] ONNX model loaded (enhanced 45-feature)')
    return session
  }).catch((err) => {
    // Reset so next call can retry
    _loadPromise = null
    console.error('[VitalNet] ONNX model load failed:', err)
    throw err
  })
  
  return _loadPromise
}

/**
 * Warm up the model with a dummy inference pass.
 * Eliminates first-submission latency.
 * Guarded against concurrent calls (React strict mode calls useEffect twice).
 */
let _warmupPromise = null
export async function warmupModel() {
  if (_warmupPromise) return _warmupPromise
  _warmupPromise = (async () => {
    const session = await loadModel()
    const dummyInput = new Float32Array(NUM_FEATURES).fill(0)
    await initializeOnnxRuntime().then(loadedOrt => {
      const tensor = new loadedOrt.Tensor('float32', dummyInput, [1, NUM_FEATURES])
      return session.run({ float_input: tensor })
    })
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
 * Build the full 45-feature Float32Array from IntakeForm data.
 * Feature order MUST match the Python ClinicalFeatureEngineer exactly.
 */
function buildFeatureVector(formData) {
  const symptoms = normalizeSymptoms(formData.symptoms || [])
  const age = coerceNumeric(formData.patient_age, 0)
  const sex = formData.patient_sex === 'male' ? 1 : formData.patient_sex === 'female' ? 0 : -1
  const bpSys = coerceNumeric(formData.bp_systolic, 110)
  const bpDia = coerceNumeric(formData.bp_diastolic, 70)
  const spo2 = coerceNumeric(formData.spo2, 94)
  const hr = coerceNumeric(formData.heart_rate, 88)
  const temp = coerceNumeric(formData.temperature, 37.2)
  const complaint = (formData.chief_complaint || '').toLowerCase()
  const duration = (formData.complaint_duration || '').toLowerCase()
  const location = (formData.location || '').toLowerCase()
  const conditions = (formData.known_conditions || '').toLowerCase()

  // Use fallbacks for derived features (same as Python)
  const safeBpSys = bpSys > 0 ? bpSys : 110
  const safeBpDia = bpDia > 0 ? bpDia : 70
  const safeHr = hr > 0 ? hr : 88
  const safeSpo2 = spo2 > 0 ? spo2 : 94
  const safeTemp = temp > 0 ? temp : 37.2
  const safeAge = age > 0 ? age : 0

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
  const pulsePressure = (bpSys > 0 && bpDia > 0) ? safeBpSys - safeBpDia : 40
  const meanArterialPressure = (bpSys > 0 && bpDia > 0) ? (safeBpSys + 2 * safeBpDia) / 3 : 93
  const shockIndex = (safeBpSys > 0 && safeHr > 0) ? safeHr / safeBpSys : 0.6
  const spo2AgeRatio = (safeSpo2 > 0 && safeAge > 0) ? safeSpo2 / Math.max(safeAge, 1) : 2.4
  const tempDeviation = safeTemp > 0 ? Math.abs(safeTemp - 37.0) : 0.0

  // Cardiac risk score
  let cardiacRisk = 0
  if (safeAge > 65) cardiacRisk += 2
  else if (safeAge > 45) cardiacRisk += 1
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
  if (safeAge < 18) {
    if (safeAge < 2) {
      if (safeHr > 160 || safeHr < 100) pediatricAdj += 2
    } else if (safeAge < 6) {
      if (safeHr > 140 || safeHr < 80) pediatricAdj += 1.5
    } else if (safeAge < 12) {
      if (safeHr > 120 || safeHr < 70) pediatricAdj += 1
    }
    if (safeTemp > 38.5) pediatricAdj += 2
  }

  // Geriatric adjustment
  let geriatricAdj = 0
  if (safeAge >= 65) {
    if (safeTemp < 36.5) geriatricAdj += 1.5
    if (safeBpSys < 100) geriatricAdj += 2
    if (safeAge > 80) geriatricAdj += 1
  }

  // Pregnancy adjustment
  let pregnancyAdj = 0
  if (formData.patient_sex === 'female' && safeAge >= 15 && safeAge <= 45) {
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
  if (safeAge < 18) {
    if (safeAge < 0.25 && safeTemp > 38.0) pediatricFeverRisk += 4
    else if (safeAge < 2 && safeTemp > 39.0) pediatricFeverRisk += 3
    else if (safeTemp > 40.0) pediatricFeverRisk += 2
    if (highFever) pediatricFeverRisk += 1
  }

  // Elderly fall risk
  let elderlyFallRisk = 0
  if (safeAge >= 65) {
    if (safeAge > 75) elderlyFallRisk += 1
    if (safeAge > 85) elderlyFallRisk += 2
    const fallKeywords = ['fall', 'fell', 'slip', 'trip', 'dizzy', 'weakness']
    if (fallKeywords.some(k => complaint.includes(k))) elderlyFallRisk += 3
  }

  // Adult cardiac risk
  let adultCardiacRisk = 0
  if (safeAge >= 18 && safeAge <= 65) {
    adultCardiacRisk = cardiacRisk * 0.8
  }

  // Obstetric emergency risk
  let obstetricRisk = 0
  if (formData.patient_sex === 'female' && safeAge >= 15 && safeAge <= 45) {
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

  // --- Assemble the 45-feature vector in exact order ---
  const features = [
    // Basic (14)
    age, sex, bpSys, bpDia, spo2, hr, temp, symptomCount,
    chestPain, breathlessness, alteredConsciousness, severeBleeding, seizure, highFever,
    // Vital derived (12)
    pulsePressure, meanArterialPressure, shockIndex, spo2AgeRatio, tempDeviation,
    cardiacRisk, respDistress, hemodynamic, sepsisRisk,
    pediatricAdj, geriatricAdj, pregnancyAdj,
    // Symptom interaction (8)
    cardiopulmonaryCluster, neurologicalCluster, hemorrhagicCluster, infectiousCluster,
    symptomSeverity, durationRisk, complaintRisk, comorbidityMult,
    // Age-specific (6)
    pediatricFeverRisk, elderlyFallRisk, adultCardiacRisk, obstetricRisk,
    traumaSeverity, mentalHealthCrisis,
    // Contextual (5)
    timeOfDayRisk, seasonalRisk, geographicRisk, epidemicAlertLevel, healthcareAccessibility,
  ]

  return new Float32Array(features)
}

// ---------------------------------------------------------------------------
// Inference
// ---------------------------------------------------------------------------

/**
 * Run triage inference on form data.
 * Returns { triageLevel, confidence, isLocal: true }
 */
export async function runTriage(formData) {
  const session = await loadModel()

  const featureVector = buildFeatureVector(formData)
  const loadedOrt = await initializeOnnxRuntime()
  const tensor = new loadedOrt.Tensor('float32', featureVector, [1, NUM_FEATURES])

  const results = await session.run({ float_input: tensor })

  // label output: int64 tensor, value is 0/1/2
  const labelIndex = Number(results.label.data[0])
  const triageLevel = TRIAGE_LABELS[labelIndex] ?? null

  // probabilities: flat array [prob_0, prob_1, prob_2]
  let confidence = null
  try {
    const probData = results.probabilities.data
    confidence = Number.isFinite(labelIndex) && TRIAGE_LABELS[labelIndex] ? probData[labelIndex] : null
  } catch {
    // non-critical — confidence display is optional
  }

  const symptoms = normalizeSymptoms(formData.symptoms || [])
  const redFlags = assessRedFlags(formData, symptoms)
  const uncertainty = {
    high_uncertainty: false,
    agreement_score: 1,
    epistemic_uncertainty: 0,
  }

  if (triageLevel == null) {
    return {
      triageLevel: 'EMERGENCY',
      confidence: null,
      isLocal: true,
      needsReview: true,
      reviewReason: UNKNOWN_LABEL_MESSAGE,
      modelVersion: MODEL_VERSION,
      featureSchemaVersion: FEATURE_SCHEMA_VERSION,
      modelHash: _modelHash,
      redFlags: redFlags.redFlags,
      mustEscalate: true,
      uncertainty,
    }
  }

  const needsReview = confidence == null || confidence < CONFIDENCE_FLOOR || uncertainty.high_uncertainty || redFlags.mustEscalate
  const confidenceDisplay = needsReview ? null : confidence

  return {
    triageLevel,
    confidence: confidenceDisplay,
    isLocal: true, // flags this as a preliminary local result
    needsReview,
    reviewReason: needsReview ? 'Low-confidence or red-flag case needs human review' : null,
    modelVersion: MODEL_VERSION,
    featureSchemaVersion: FEATURE_SCHEMA_VERSION,
    modelHash: _modelHash,
    redFlags: redFlags.redFlags,
    mustEscalate: redFlags.mustEscalate,
    uncertainty,
  }
}
