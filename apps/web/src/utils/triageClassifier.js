// frontend/src/utils/triageClassifier.js
//
// Offline triage orchestration — Round 6 rebuild plan, Phase 5. The clinical
// logic itself (rules engine, feature engineering, tree evaluation,
// contraindications) now lives entirely in @vitalnet/clinical-core; this
// file owns only what's genuinely BROWSER-specific and doesn't belong in an
// environment-agnostic package: fetching + caching the trained model
// artifact, and warmup scheduling. offline and online triage are now the
// same triage() function, called in "rules_first" mode — not mirrored code.
//
// Why no ONNX runtime: the model is a gradient-boosted tree ensemble, which
// evaluates in a few thousand float comparisons. Shipping a general ~12 MB WASM
// inference engine to precache and cold-compile for that is pure overhead on the
// 2 GB-class Android tablets and metered rural links this app targets. Instead
// the model is exported as compact JSON (/models/triage_trees.json, ~1 MB, gzips
// far smaller) and walked by clinical-core's treeEvaluator. Predictions are
// argmax-identical to the server, enforced by clinical-core's own golden-vector
// test — this file has no parity test of its own anymore, there is nothing
// left here that could drift from the server.

import { triage } from '@vitalnet/clinical-core'

const TREES_PATH = '/models/triage_trees.json'
const FEATURES_CONFIG_PATH = '/models/features_config.json'

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
    await loadModel()
    // Dummy triage call to force the tree-walk/JIT path warm, same intent as
    // the previous direct evaluateTrees() call — a well-formed, entirely
    // ROUTINE patient is enough to exercise the same code paths a real
    // submission will hit.
    triage(
      {
        patient_age: 30,
        patient_sex: 'male',
        bp_systolic: 120,
        bp_diastolic: 80,
        spo2: 98,
        heart_rate: 75,
        temperature: 37.0,
        symptoms: [],
        is_pregnant: null,
        chief_complaint: '',
        complaint_duration: '',
        location: '',
        known_conditions: null,
        current_medications: null,
      },
      { mode: 'rules_first', trees: _treeJson, featureNames: _featureNames },
    )
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
// Inference — offline and online are now the SAME function
// (@vitalnet/clinical-core's triage(), rules_first mode).
// ---------------------------------------------------------------------------

/**
 * Run offline triage on form data. Always returns a result — never throws for
 * well-formed input, even if the tree model failed to load (rules-only
 * fallback, since triage()'s advisory model is optional). Shape:
 *   { triageLevel, confidence, lowConfidence, isLocal: true,
 *     modelUnavailable, contraindicationFlags, firedRules }
 */
export async function runTriage(formData) {
  let modelUnavailable = false
  let trees, featureNames
  try {
    trees = await loadModel()
    featureNames = _featureNames
  } catch {
    // Model unavailable — rules-only fallback. Never fail to triage: the
    // rules engine (checkOverrides/assignTier) needs no model at all.
    modelUnavailable = true
  }

  const result = triage(
    {
      patient_age: formData.patient_age,
      patient_sex: formData.patient_sex || null,
      bp_systolic: formData.bp_systolic ?? null,
      bp_diastolic: formData.bp_diastolic ?? null,
      spo2: formData.spo2 ?? null,
      heart_rate: formData.heart_rate ?? null,
      temperature: formData.temperature ?? null,
      symptoms: formData.symptoms || [],
      is_pregnant: formData.is_pregnant ?? null,
      chief_complaint: formData.chief_complaint || null,
      complaint_duration: formData.complaint_duration || null,
      location: formData.location || null,
      known_conditions: formData.known_conditions || null,
      current_medications: formData.current_medications || null,
    },
    modelUnavailable ? { mode: 'rules_first' } : { mode: 'rules_first', trees, featureNames },
  )

  return {
    triageLevel: result.tier,
    confidence: result.model?.confidence ?? null,
    lowConfidence: result.model?.lowConfidence ?? false,
    isLocal: true,
    modelUnavailable,
    contraindicationFlags: result.contraindicationFlags,
    firedRules: result.firedRules,
  }
}
