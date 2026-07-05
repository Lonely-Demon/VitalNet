// frontend/tests/contraindications.test.mjs
//
// Parity guard for checkContraindications() (clinicalRules.js) against its
// Python mirror (backend/app/ml/contraindications.py). Not a golden-vector
// fixture like treeParity — the rule table is small and hand-mirrored, so
// this replays the same cases backend/tests/test_contraindications.py
// checks and asserts the same flag COUNT fires for each (message wording
// only needs to be equivalent, not byte-identical, across languages).
//
// Run: node frontend/tests/contraindications.test.mjs

import { checkContraindications } from '../src/utils/clinicalRules.js'

const BASE = {
  patient_age: 40, patient_sex: 'male',
  bp_systolic: 120, bp_diastolic: 80, spo2: 98, heart_rate: 74,
  temperature: 37.0, symptoms: [], chief_complaint: 'Weakness / fatigue',
  complaint_duration: '1-3 days', location: 'Rural District',
  known_conditions: '', current_medications: '',
}

const cases = (overrides) => ({ ...BASE, ...overrides })

let failures = 0
function expectFlagCount(name, formData, expectedCount) {
  const flags = checkContraindications(formData)
  if (flags.length !== expectedCount) {
    failures++
    console.error(`  FAIL ${name}: expected ${expectedCount} flag(s), got ${flags.length} — ${JSON.stringify(flags)}`)
  } else {
    console.log(`  PASS ${name}`)
  }
}

expectFlagCount('no medications -> no flags', cases({}), 0)
expectFlagCount('medication alone, no matching condition/symptom -> no flags',
  cases({ current_medications: 'ibuprofen 400mg' }), 0)
expectFlagCount('NSAID + renal condition -> flagged',
  cases({ current_medications: 'ibuprofen', known_conditions: 'chronic kidney disease' }), 1)
expectFlagCount('ACE inhibitor + renal condition -> flagged',
  cases({ current_medications: 'lisinopril 10mg', known_conditions: 'renal impairment' }), 1)
expectFlagCount('metformin + persistent vomiting -> flagged',
  cases({ current_medications: 'metformin 500mg', symptoms: ['persistent_vomiting'] }), 1)
expectFlagCount('metformin without vomiting -> no flags',
  cases({ current_medications: 'metformin 500mg' }), 0)
expectFlagCount('anticoagulant + severe bleeding -> flagged',
  cases({ current_medications: 'warfarin', symptoms: ['severe_bleeding'] }), 1)
expectFlagCount('beta-blocker + bradycardia -> flagged',
  cases({ current_medications: 'atenolol 50mg', heart_rate: 48 }), 1)
expectFlagCount('beta-blocker + normal heart rate -> no flags',
  cases({ current_medications: 'atenolol 50mg', heart_rate: 74 }), 0)
expectFlagCount('insulin + altered consciousness -> flagged',
  cases({ current_medications: 'insulin glargine', symptoms: ['altered_consciousness'] }), 1)
expectFlagCount('multiple medications -> multiple flags',
  cases({ current_medications: 'ibuprofen, lisinopril', known_conditions: 'chronic kidney disease' }), 2)
expectFlagCount('case-insensitive matching',
  cases({ current_medications: 'IBUPROFEN', known_conditions: 'Chronic KIDNEY Disease' }), 1)

if (failures > 0) {
  console.error(`\ncontraindications parity: FAIL — ${failures} case(s) disagree with the Python mirror`)
  process.exit(1)
} else {
  console.log('\ncontraindications parity: PASS — checkContraindications matches backend/app/ml/contraindications.py on all cases')
}
