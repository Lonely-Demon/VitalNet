// frontend/tests/featureParity.test.mjs
//
// Parity guard for clinical feature engineering (FEATURES_ROADMAP.md §1.2).
// backend/app/ml/clinical_features.py::ClinicalFeatureEngineer is hand-ported
// into buildFeatureMap() here — if a future change to one isn't mirrored in
// the other, offline triage silently diverges from online triage for the
// same patient. Loads the fixture written by
// backend/scripts/export_golden_vectors.py and re-runs buildFeatureMap() on
// every recorded input, asserting an exact (tolerance-bounded) match.
//
// Every fixture input carries an explicit _reference_month (set by
// scripts/train_classifier.py::generate_patient), which buildFeatureMap()
// prefers over `new Date()` for seasonal_risk — so this test's outcome no
// longer depends on real wall-clock time for that feature. The global Date
// constructor is still frozen to FROZEN_REFERENCE_TIME below (must match
// export_golden_vectors.py's FROZEN_REFERENCE_TIME and test_feature_parity.py's
// twin) as a defensive fallback for any other contextual feature that reads
// it directly.
//
// Run: node frontend/tests/featureParity.test.mjs

import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const FROZEN_REFERENCE_TIME = new Date(2026, 6, 4, 12, 0, 0) // month is 0-indexed: 6 = July

const RealDate = Date
class FrozenDate extends RealDate {
  constructor(...args) {
    super(...(args.length ? args : [FROZEN_REFERENCE_TIME]))
  }
  static now() {
    return FROZEN_REFERENCE_TIME.getTime()
  }
}
globalThis.Date = FrozenDate

const { buildFeatureMap } = await import('../src/utils/triageClassifier.js')

const here = dirname(fileURLToPath(import.meta.url))
const vectors = JSON.parse(readFileSync(join(here, 'fixtures/golden_feature_vectors.json'), 'utf8'))

const TOLERANCE = 1e-6
let mismatches = 0
let shown = 0

for (let i = 0; i < vectors.length; i++) {
  const { input, features: expected } = vectors[i]
  const computed = buildFeatureMap(input)

  const expectedKeys = Object.keys(expected).sort()
  const computedKeys = Object.keys(computed).sort()
  if (expectedKeys.join(',') !== computedKeys.join(',')) {
    mismatches++
    if (shown++ < 5) {
      const missing = expectedKeys.filter((k) => !computedKeys.includes(k))
      const extra = computedKeys.filter((k) => !expectedKeys.includes(k))
      console.error(`  vector ${i}: key mismatch — missing=${missing}, extra=${extra}`)
    }
    continue
  }

  let vectorHadMismatch = false
  for (const key of expectedKeys) {
    if (Math.abs(computed[key] - expected[key]) > TOLERANCE) {
      vectorHadMismatch = true
      if (shown++ < 30) {
        console.error(`  vector ${i}, feature '${key}': expected ${expected[key]}, got ${computed[key]}`)
      }
    }
  }
  if (vectorHadMismatch) mismatches++
}

const total = vectors.length
if (mismatches === 0) {
  console.log(`featureParity: PASS — buildFeatureMap matches ClinicalFeatureEngineer on all ${total} golden vectors.`)
  process.exit(0)
} else {
  console.error(`featureParity: FAIL — ${mismatches}/${total} vectors diverge. Offline feature engineering would not match the server. Do not ship.`)
  process.exit(1)
}
