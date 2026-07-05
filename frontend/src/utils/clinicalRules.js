// frontend/src/utils/clinicalRules.js
//
// Deterministic clinical safety rules for the OFFLINE triage path — a 1:1
// mirror of backend/app/ml/classifier.py (_safety_net_check and
// _news2_concerning_vital) and backend/app/ml/contraindications.py. These
// run REGARDLESS of the ML tree evaluator, so:
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

// Severe features of preeclampsia this app can actually observe (ACOG
// Practice Bulletin 222) — used only alongside is_pregnant + a preeclampsia-
// range BP reading (docs/DECISIONS.md §30).
const PREECLAMPSIA_SEVERE_SYMPTOMS = new Set(['severe_headache', 'severe_abdominal_pain'])

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

  if (formData.is_pregnant) {
    const bpDia = num(formData.bp_diastolic)
    if (bpSys !== null && bpDia !== null) {
      if (bpSys >= 160 || bpDia >= 110) {
        return `Severe hypertension in pregnancy (BP ${bpSys}/${bpDia} mmHg) — possible severe preeclampsia`
      }
      if (bpSys >= 140 || bpDia >= 90) {
        const hit = [...symptoms].filter((s) => PREECLAMPSIA_SEVERE_SYMPTOMS.has(s))
        if (hit.length) {
          const readable = hit.map((h) => h.replace(/_/g, ' ')).sort().join(', ')
          return `Hypertension in pregnancy (BP ${bpSys}/${bpDia} mmHg) with severe feature(s): ${readable} — possible preeclampsia with severe features`
        }
      }
    }
  }

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

// ---------------------------------------------------------------------------
// Contraindication/interaction flags — mirrors
// backend/app/ml/contraindications.py::RULES exactly. See that module's
// docstring for scope: free-text keyword matching against a small curated
// list, not a general drug-interaction database. Never changes the triage
// tier — the caller folds any flag into a "needs review" style signal.
// ---------------------------------------------------------------------------

const CONTRAINDICATION_RULES = [
  {
    id: 'nsaid_renal',
    medicationTerms: ['ibuprofen', 'diclofenac', 'naproxen', 'nsaid', 'mefenamic', 'aceclofenac'],
    conditionTerms: ['kidney', 'renal', 'ckd', 'dialysis'],
    message: 'NSAID use with known kidney/renal disease — NSAIDs can worsen renal function; verify before recommending.',
  },
  {
    id: 'ace_arb_renal',
    medicationTerms: ['enalapril', 'lisinopril', 'ramipril', 'captopril', 'losartan', 'telmisartan', 'olmesartan', 'ace inhibitor'],
    conditionTerms: ['kidney', 'renal', 'ckd', 'dialysis'],
    message: 'ACE inhibitor/ARB with known kidney disease — risk of hyperkalemia or worsening renal function; verify before recommending.',
  },
  {
    id: 'metformin_vomiting',
    medicationTerms: ['metformin', 'glucophage'],
    symptomCodes: ['persistent_vomiting'],
    message: 'Metformin with persistent vomiting — risk of dehydration-related lactic acidosis; verify before continuing metformin.',
  },
  {
    id: 'anticoagulant_bleeding',
    medicationTerms: ['warfarin', 'acitrom', 'dabigatran', 'apixaban', 'rivaroxaban', 'heparin', 'anticoagulant'],
    symptomCodes: ['severe_bleeding'],
    message: 'Anticoagulant use with active severe bleeding — bleeding risk is compounded; flag for urgent clinical attention.',
  },
  {
    id: 'beta_blocker_bradycardia',
    medicationTerms: ['atenolol', 'metoprolol', 'propranolol', 'bisoprolol', 'beta blocker', 'beta-blocker'],
    maxHeartRate: 55,
    message: 'Beta-blocker use with a low heart rate — may indicate excessive beta-blockade; verify before further heart-rate-lowering treatment.',
  },
  {
    id: 'hypoglycemia_agent_altered_consciousness',
    medicationTerms: ['insulin', 'glimepiride', 'glipizide', 'glyburide', 'gliclazide', 'sulfonylurea'],
    symptomCodes: ['altered_consciousness'],
    message: 'Insulin/sulfonylurea use with altered consciousness — consider hypoglycemia; verify blood glucose before assuming another cause.',
  },
]

/**
 * Returns an array of human-readable contraindication flags (possibly
 * empty). Mirrors classifier.py::check_contraindications /
 * contraindications.py::RULES.
 */
export function checkContraindications(formData) {
  const medications = (formData.current_medications || '').toLowerCase()
  if (!medications) return []

  const conditions = (formData.known_conditions || '').toLowerCase()
  const symptoms = new Set(formData.symptoms || [])
  const heartRate = num(formData.heart_rate)

  const flags = []
  for (const rule of CONTRAINDICATION_RULES) {
    if (!rule.medicationTerms.some((term) => medications.includes(term))) continue

    const conditionHit = Boolean(rule.conditionTerms) && rule.conditionTerms.some((term) => conditions.includes(term))
    const symptomHit = Boolean(rule.symptomCodes) && rule.symptomCodes.some((code) => symptoms.has(code))
    const heartRateHit = rule.maxHeartRate !== undefined && heartRate !== null && heartRate < rule.maxHeartRate

    if (conditionHit || symptomHit || heartRateHit) flags.push(rule.message)
  }
  return flags
}
