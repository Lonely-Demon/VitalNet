// frontend/tests/treeParity.test.mjs
//
// Parity guard for the offline (JS) triage engine. Loads the compact tree JSON
// the browser actually ships (public/models/triage_trees.json) and the golden
// fixture written by backend/scripts/train_classifier.py (labels computed by the
// Python reference evaluator, which the training script asserts equals the real
// scikit-learn model and onnxruntime). If evaluateTrees() here disagrees on any
// vector, the offline triage a patient receives would differ from the server —
// so this MUST fail CI rather than silently diverge.
//
// Run: node frontend/tests/treeParity.test.mjs
// (Plain Node, no test framework needed — exits non-zero on failure.)

import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import { evaluateTrees } from '../src/utils/treeEvaluator.js'

const here = dirname(fileURLToPath(import.meta.url))
const treeJson = JSON.parse(readFileSync(join(here, '../public/models/triage_trees.json'), 'utf8'))
const golden = JSON.parse(readFileSync(join(here, 'fixtures/golden_vectors.json'), 'utf8'))

let mismatches = 0
for (const { features, expected_class } of golden.vectors) {
  const { classIndex } = evaluateTrees(treeJson, features)
  if (classIndex !== expected_class) {
    mismatches++
    if (mismatches <= 5) {
      console.error(`  mismatch: got ${classIndex}, expected ${expected_class}`)
    }
  }
}

const total = golden.vectors.length
if (mismatches === 0) {
  console.log(`treeParity: PASS — JS evaluator matches the server model on all ${total} golden vectors (model v${golden.model_version}).`)
  process.exit(0)
} else {
  console.error(`treeParity: FAIL — ${mismatches}/${total} vectors diverge. Offline triage would not match the server. Do not ship.`)
  process.exit(1)
}
