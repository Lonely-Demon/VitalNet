// frontend/tests/safetyNet.test.mjs
//
// Parity guard for safetyNetCheck() / news2ConcerningVital() (clinicalRules.js)
// against their Python mirror (backend/app/ml/classifier.py::_safety_net_check
// / _news2_concerning_vital). Replays the same cases
// backend/tests/test_classifier_safety.py checks and asserts the same
// escalate/no-escalate outcome (reason wording only needs to be equivalent,
// not byte-identical, across languages).
//
// Run: node frontend/tests/safetyNet.test.mjs

import { safetyNetCheck, news2ConcerningVital } from '../src/utils/clinicalRules.js'

const BASE = {
  patient_age: 40, patient_sex: 'male',
  bp_systolic: 120, bp_diastolic: 80, spo2: 98, heart_rate: 74,
  temperature: 37.0, symptoms: [], chief_complaint: 'Weakness / fatigue',
  complaint_duration: '1-3 days', location: 'Rural District',
  known_conditions: '', current_medications: '',
}

const cases = (overrides) => ({ ...BASE, ...overrides })

let failures = 0
function expect(name, actual, expected) {
  if (actual !== expected) {
    failures++
    console.error(`  FAIL ${name}: expected ${expected}, got ${actual}`)
  } else {
    console.log(`  PASS ${name}`)
  }
}

// Extreme vitals -> always EMERGENCY (safetyNetCheck returns a reason string)
for (const ov of [
  { spo2: 84 }, { spo2: 70 },
  { heart_rate: 34 }, { heart_rate: 180 },
  { bp_systolic: 65 }, { bp_systolic: 240 },
  { temperature: 42.0 }, { temperature: 32.5 },
]) {
  expect(`extreme vital ${JSON.stringify(ov)} triggers safety net`, safetyNetCheck(cases(ov)) !== null, true)
}

// Critical symptoms -> always EMERGENCY
for (const sym of ['altered_consciousness', 'seizure', 'severe_bleeding', 'swelling_face_throat']) {
  expect(`critical symptom ${sym} triggers safety net`, safetyNetCheck(cases({ symptoms: [sym] })) !== null, true)
}

// Neonatal fever -> EMERGENCY
expect('neonatal fever triggers safety net', safetyNetCheck(cases({ patient_age: 0.1, temperature: 38.5 })) !== null, true)

// Concerning-but-not-extreme vitals -> NEWS2 floor flags them (never routine)
for (const ov of [
  { spo2: 92 }, { spo2: 91 },
  { heart_rate: 122 }, { heart_rate: 40 },
  { bp_systolic: 98 }, { bp_systolic: 185 },
  { temperature: 39.3 }, { temperature: 34.8 },
]) {
  expect(`concerning vital ${JSON.stringify(ov)} flagged by NEWS2 floor`, news2ConcerningVital(cases(ov)) !== null, true)
}

// Healthy vitals, no symptoms -> no escalation
expect('healthy vitals do not trigger safety net', safetyNetCheck(cases({})) !== null, false)
expect('healthy vitals do not trigger NEWS2 floor', news2ConcerningVital(cases({})) !== null, false)

// --- Pregnancy-specific preeclampsia rule (docs/DECISIONS.md §30) ---

for (const ov of [
  { bp_systolic: 160, bp_diastolic: 100 },
  { bp_systolic: 150, bp_diastolic: 110 },
  { bp_systolic: 170, bp_diastolic: 115 },
]) {
  expect(`severe hypertension in pregnancy ${JSON.stringify(ov)} triggers safety net`,
    safetyNetCheck(cases({ ...ov, is_pregnant: true, patient_sex: 'female' })) !== null, true)

  expect(`same BP ${JSON.stringify(ov)} without is_pregnant does not trigger safety net`,
    safetyNetCheck(cases({ ...ov, patient_sex: 'female' })) !== null, false)
}

for (const symptom of ['severe_headache', 'severe_abdominal_pain']) {
  expect(`BP 145/95 + ${symptom} + is_pregnant triggers safety net`,
    safetyNetCheck(cases({
      bp_systolic: 145, bp_diastolic: 95, is_pregnant: true, patient_sex: 'female', symptoms: [symptom],
    })) !== null, true)
}

expect('BP 145/95 + is_pregnant with no severe feature does not trigger safety net',
  safetyNetCheck(cases({ bp_systolic: 145, bp_diastolic: 95, is_pregnant: true, patient_sex: 'female' })) !== null, false)

expect('BP 145/95 + severe_headache without is_pregnant does not trigger safety net',
  safetyNetCheck(cases({ bp_systolic: 145, bp_diastolic: 95, patient_sex: 'female', symptoms: ['severe_headache'] })) !== null, false)

if (failures > 0) {
  console.error(`\nsafetyNet parity: FAIL — ${failures} case(s) disagree with the Python mirror`)
  process.exit(1)
} else {
  console.log('\nsafetyNet parity: PASS — safetyNetCheck/news2ConcerningVital match backend/app/ml/classifier.py on all cases')
}
