// frontend/src/utils/triageClassifier.js
import * as ort from 'onnxruntime-web'

const MODEL_PATH = '/models/triage_classifier.onnx'
const TRIAGE_LABELS = ['ROUTINE', 'URGENT', 'EMERGENCY']

// Feature order MUST match training script exactly — do not reorder
const FEATURE_ORDER = [
  'age',
  'sex',
  'bp_systolic',
  'bp_diastolic',
  'spo2',
  'heart_rate',
  'temperature',
  'symptom_count',
  'chest_pain',
  'breathlessness',
  'altered_consciousness',
  'severe_bleeding',
  'seizure',
  'high_fever',
]

const SYMPTOM_FLAGS = [
  'chest_pain',
  'breathlessness',
  'altered_consciousness',
  'severe_bleeding',
  'seizure',
  'high_fever',
]

let _session = null
let _loadPromise = null

/**
 * Load and cache the ONNX session.
 * Called once on ASHA panel mount — not on every submission.
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
    console.log('[VitalNet] ONNX model loaded')
    return session
  })

  return _loadPromise
}

/**
 * Warm up the model with a dummy inference pass.
 * Eliminates first-submission latency.
 */
export async function warmupModel() {
  const session = await loadModel()
  const dummyInput = new Float32Array(14).fill(0)
  const tensor = new ort.Tensor('float32', dummyInput, [1, 14])
  await session.run({ float_input: tensor })
}

/**
 * Build the float32 feature vector from IntakeForm data.
 * Missing vitals → -1 sentinel (matches training).
 */
function buildFeatureVector(formData) {
  const symptoms = formData.symptoms || []

  // Compute symptom_count from selected symptom flags
  const symptomCount = SYMPTOM_FLAGS.filter((s) => symptoms.includes(s)).length

  const raw = {
    age: formData.patient_age ?? -1,
    sex: formData.patient_sex === 'male' ? 1 : formData.patient_sex === 'female' ? 0 : -1,
    bp_systolic: formData.bp_systolic ?? -1,
    bp_diastolic: formData.bp_diastolic ?? -1,
    spo2: formData.spo2 ?? -1,
    heart_rate: formData.heart_rate ?? -1,
    temperature: formData.temperature ?? -1,
    symptom_count: symptomCount,
    chest_pain: symptoms.includes('chest_pain') ? 1 : 0,
    breathlessness: symptoms.includes('breathlessness') ? 1 : 0,
    altered_consciousness: symptoms.includes('altered_consciousness') ? 1 : 0,
    severe_bleeding: symptoms.includes('severe_bleeding') ? 1 : 0,
    seizure: symptoms.includes('seizure') ? 1 : 0,
    high_fever: symptoms.includes('high_fever') ? 1 : 0,
  }

  return new Float32Array(FEATURE_ORDER.map((f) => raw[f]))
}

/**
 * Run triage inference on form data.
 * Returns { triageLevel, confidence, isLocal: true }
 */
export async function runTriage(formData) {
  const session = await loadModel()

  const featureVector = buildFeatureVector(formData)
  const tensor = new ort.Tensor('float32', featureVector, [1, 14])

  const results = await session.run({ float_input: tensor })

  // label output: int64 tensor, value is 0/1/2
  const labelIndex = Number(results.label.data[0])
  const triageLevel = TRIAGE_LABELS[labelIndex] ?? 'ROUTINE'

  // probabilities: map of label string → probability
  // onnxruntime-web returns this as a Map or object depending on version
  let confidence = null
  try {
    const probData = results.probabilities.data
    // probData is a flat array: [prob_0, prob_1, prob_2]
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