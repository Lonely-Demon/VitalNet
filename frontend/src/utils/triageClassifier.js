// frontend/src/utils/triageClassifier.js
//
// Client-side ONNX triage inference using the enhanced 45-feature model.
// Ports backend/clinical_features.py ClinicalFeatureEngineer to JavaScript.
//
import * as ort from 'onnxruntime-web'

// Disable multi-threading — requires COOP/COEP headers that Vite dev server
// and many production hosts don't set.  Single-threaded WASM is fast enough
// for a 45-feature model inference (<10 ms).
ort.env.wasm.numThreads = 1

const MODEL_PATH = '/models/triage_classifier.onnx'
const TRIAGE_LABELS = ['ROUTINE', 'URGENT', 'EMERGENCY']
const NUM_FEATURES = 45

// ---------------------------------------------------------------------------
// Session management
// ---------------------------------------------------------------------------

let _session = null
let _loadPromise = null

/**
 * Load and cache the ONNX session.
 * Called once on ASHA panel mount — not on every submission.
 * Retries on failure (resets _loadPromise so next call retries).
 */
export async function loadModel() {
  if (_session) return _session
  if (_loadPromise) return _loadPromise

  _loadPromise = ort.InferenceSession.create(MODEL_PATH, {
    executionProviders: ['wasm'],
    graphOptimizationLevel: 'all',
  }).then((session) => {
    _session = session
    _loadPromise = null
    console.log('[VitalNet] ONNX model loaded (enhanced 45-feature)')
    return session
  }).catch((err) => {
    // Reset so next call retries instead of returning the failed promise
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
    const tensor = new ort.Tensor('float32', dummyInput, [1, NUM_FEATURES])
    await session.run({ float_input: tensor })
    console.log('[VitalNet] ONNX warmup complete — ready for offline triage')
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
  const tensor = new ort.Tensor('float32', featureVector, [1, NUM_FEATURES])

  const results = await session.run({ float_input: tensor })

  // label output: int64 tensor, value is 0/1/2
  const labelIndex = Number(results.label.data[0])
  const triageLevel = TRIAGE_LABELS[labelIndex] ?? 'ROUTINE'

  // probabilities: flat array [prob_0, prob_1, prob_2]
  let confidence = null
  try {
    const probData = results.probabilities.data
    confidence = probData[labelIndex]
  } catch {
    // non-critical — confidence display is optional
  }

  return {
    triageLevel,
    confidence,
    isLocal: true, // flags this as a preliminary local result
  }
}
