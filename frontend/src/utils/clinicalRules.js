// frontend/src/utils/clinicalRules.js
//
// Deterministic clinical safety rules for the OFFLINE triage path — a 1:1
// mirror of backend/app/ml/classifier.py (_safety_net_check and
// _news2_concerning_vital). These run REGARDLESS of the ML tree evaluator, so:
//   1. Unambiguous critical presentations escalate to EMERGENCY even for inputs
//      the model was never trained on ("classify under any circumstances").
//   2. A concerning single vital can never be left as ROUTINE (URGENT floor).
//   3. If the tree model itself fails to load, these rules still produce a safe
//      triage — triage never fails.
// Keeping this identical to the Python side is what preserves online/offline
// agreement; if you change one, change both.

const CRITICAL_SYMPTOMS_OVERRIDE = new Set([
  'altered_consciousness', 'seizure', 'severe_bleeding', 'swelling_face_throat',
])

const HYPERTENSIVE_NEURO = new Set([
  'severe_headache', 'weakness_one_side', 'difficulty_speaking', 'altered_consciousness',
])

const num = (v) => (v === null || v === undefined || v === '' ? null : Number(v))

/**
 * Extreme-presentation safety net. Returns a human-readable reason (→ EMERGENCY)
 * or null. Mirrors classifier.py::_safety_net_check.
 */
export function safetyNetCheck(formData) {
  const symptoms = new Set(formData.symptoms || [])
  const hits = [...symptoms].filter((s) => CRITICAL_SYMPTOMS_OVERRIDE.has(s))
  if (hits.length) {
    const readable = hits.map((h) => h.replace(/_/g, ' ')).sort().join(', ')
    return `Critical symptom present: ${readable}`
  }

  const age = num(formData.patient_age)
  const temp = num(formData.temperature)
  if (age !== null && age < 0.25 && temp !== null && temp >= 38.0) {
    return `Neonatal fever (age ${Math.round(age * 12)} months, temperature ${temp}°C)`
  }

  const spo2 = num(formData.spo2)
  if (spo2 !== null && spo2 < 85) return `Critically low oxygen saturation (${spo2}%)`

  const hr = num(formData.heart_rate)
  if (hr !== null && (hr < 35 || hr > 170)) return `Extreme heart rate (${hr} bpm)`

  const bpSys = num(formData.bp_systolic)
  if (bpSys !== null && (bpSys < 70 || bpSys > 220)) return `Extreme systolic blood pressure (${bpSys} mmHg)`

  if (bpSys !== null && bpSys >= 180) {
    const neuro = [...symptoms].filter((s) => HYPERTENSIVE_NEURO.has(s))
    if (neuro.length) {
      const readable = neuro.map((h) => h.replace(/_/g, ' ')).sort().join(', ')
      return `Hypertensive crisis (systolic BP ${bpSys} mmHg) with neurological symptom(s): ${readable} — possible hypertensive encephalopathy/stroke`
    }
  }

  if (temp !== null && (temp > 41.5 || temp < 33.0)) return `Extreme body temperature (${temp}°C)`

  return null
}

/**
 * NEWS2 "concerning single vital" (score >= 2, but not extreme). Returns a
 * reason (→ floor ROUTINE up to URGENT) or null. Mirrors
 * classifier.py::_news2_concerning_vital.
 */
export function news2ConcerningVital(formData) {
  const spo2 = num(formData.spo2)
  if (spo2 !== null && spo2 <= 92) return `low oxygen saturation (${spo2}%)`

  const bpSys = num(formData.bp_systolic)
  if (bpSys !== null && (bpSys <= 100 || bpSys >= 180)) return `concerning systolic blood pressure (${bpSys} mmHg)`

  const hr = num(formData.heart_rate)
  if (hr !== null && (hr <= 40 || hr >= 120)) return `concerning heart rate (${hr} bpm)`

  const temp = num(formData.temperature)
  if (temp !== null && (temp <= 35.0 || temp >= 39.1)) return `concerning temperature (${temp}°C)`

  return null
}
