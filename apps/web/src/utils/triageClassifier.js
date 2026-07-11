// frontend/src/utils/triageClassifier.js
//
// Offline triage orchestration — Round 6 rebuild plan, Phase 5/6. The
// clinical logic itself (rules engine, feature engineering, tree
// evaluation, contraindications) now lives entirely in @vitalnet/clinical-
// core; this file owns only what's genuinely BROWSER-specific and doesn't
// belong in an environment-agnostic package: fetching + caching the
// trained model artifact, and warmup scheduling.
//
// Mode: "hybrid", NOT "rules_first" — deliberately. rules_first is the
// target end-state (docs/DECISIONS.md §33), but /api/submit (the legacy,
// live backend) still computes the AUTHORITATIVE, persisted tier with
// classifier.py::predict_triage's model-primary semantics, and rules_first
// disagrees with that on 0.88% of cases (docs/CLINICAL_REVIEW.md — 51/10,000
// EMERGENCY->URGENT among them). Showing a rules_first preliminary tier
// offline, before that delta has clinician sign-off, would let an offline
// ASHA worker see a lower preliminary tier than the case may become once it
// syncs and the server retriages it from the raw submitted vitals. "hybrid"
// mode reproduces the server's exact current ordering (safety-net override
// -> model authoritative -> NEWS2 floor), so the offline preliminary tier
// always matches what /api/submit will assign on sync. Flip this to
// rules_first only alongside the actual server-side cutover, once
// docs/CLINICAL_REVIEW.md's sign-off is recorded.
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

import { triage, checkOverrides, checkContraindications } from '@vitalnet/clinical-core'

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
      { mode: 'hybrid', trees: _treeJson, featureNames: _featureNames },
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
// Inference — matches the server's CURRENT authoritative semantics
// (@vitalnet/clinical-core's triage(), "hybrid" mode). See this file's
// header for why not "rules_first".
// ---------------------------------------------------------------------------

/**
 * Run offline triage on form data. Always returns a result — never throws
 * for well-formed input. Shape:
 *   { triageLevel, confidence, lowConfidence, isLocal: true,
 *     modelUnavailable, contraindicationFlags, firedRules }
 *
 * "hybrid" mode requires a loaded model — it has no rules-only fallback
 * (the model IS authoritative for the non-override band in this mode,
 * unlike rules_first). When the model can't be loaded, this can only
 * safely report what's mode-independent: the unconditional safety-net
 * override (identical in hybrid and rules_first — an EMERGENCY override
 * is EMERGENCY either way) and contraindication flags. Everything else
 * comes back as `triageLevel: null` ("unknown — will be determined when
 * this case syncs") rather than guessing at a tier that might not match
 * what the server assigns from the same raw vitals on sync.
 */
export async function runTriage(formData) {
  const engineInput = {
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
  }

  let trees, featureNames
  try {
    trees = await loadModel()
    featureNames = _featureNames
  } catch {
    // Model unavailable — hybrid mode can't run without one (see doc
    // comment above). Fall back to the override-only, mode-independent
    // safety net rather than a guessed tier.
    const override = checkOverrides(engineInput)
    return {
      triageLevel: override ? 'EMERGENCY' : null,
      confidence: null,
      lowConfidence: false,
      isLocal: true,
      modelUnavailable: true,
      contraindicationFlags: checkContraindications(engineInput),
      firedRules: override ? [override] : [],
    }
  }

  const result = triage(engineInput, { mode: 'hybrid', trees, featureNames })

  return {
    triageLevel: result.tier,
    confidence: result.model?.confidence ?? null,
    lowConfidence: result.model?.lowConfidence ?? false,
    isLocal: true,
    modelUnavailable: false,
    contraindicationFlags: result.contraindicationFlags,
    firedRules: result.firedRules,
  }
}
