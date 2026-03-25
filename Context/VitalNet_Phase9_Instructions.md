# VitalNet — Phase 9 Build Instructions
**ONNX Offline Classifier · Instant Triage in the Field**

| | |
|---|---|
| **Prepared for** | Google Antigravity |
| **Phase** | 9 of 10 |
| **Depends on** | Phase 8 complete — PWA installed, offline queue working |
| **Files changed** | `backend/` (ONNX conversion script) · `frontend/` (ONNX inference, UI update) |
| **Risk level** | LOW-MEDIUM — classifier runs in isolation, does not touch auth or data layer |
| **Date** | March 2026 |

---

## 1. What Phase 8 Left Us

- App is a PWA — installable, app shell cached, loads offline
- Offline submissions queue to IndexedDB and sync on reconnect
- ASHA worker submits a form offline → sees "Saved offline" toast
- The triage badge and briefing only appear after sync (server-side)
- The ONNX conversion has already been tested: `.pkl` → `.onnx` conversion works, output file is ~500KB

**The gap Phase 9 closes:** An ASHA worker in a rural area with no connectivity submits a case. Right now in Phase 8, she has to wait until sync to see the triage result. A patient with EMERGENCY status might be sent home because the ASHA worker had no guidance. Phase 9 runs the classifier directly in the browser the moment the form is submitted — online or offline — giving an instant triage badge before the LLM briefing is available.

---

## 2. What Phase 9 Builds

### 2.1 Scope

**In scope:**
- Convert `triage_classifier.pkl` to `triage_classifier.onnx` via `skl2onnx` (Python script)
- Ship the `.onnx` file as a static asset in the frontend (`public/models/`)
- Load and run ONNX inference in the browser using `onnxruntime-web`
- Show instant triage badge in the ASHA panel at form submission time
- The offline queue entry is annotated with the local triage result
- After sync, the server-side triage result (authoritative) overwrites the local result

**Out of scope:**
- SHAP explanations offline (TreeExplainer cannot be converted to ONNX — this is a known hard limitation)
- LLM briefing offline (requires Groq API — by definition server-side)
- Doctor dashboard showing local triage result (doctor always sees the server-authoritative value)

### 2.2 SHAP Offline Limitation — Important Context

The `.pkl` bundles both the `HistGradientBoostingClassifier` and the `shap.TreeExplainer`. Only the classifier converts to ONNX. The explainer does not travel. This means:

- **Offline:** Triage badge shown instantly (EMERGENCY / URGENT / ROUTINE) with no risk driver explanation
- **After sync:** Full briefing with SHAP risk driver appears in submission history
- The UI must make this two-stage reveal clear to the ASHA worker: "Preliminary result — full analysis after sync"

### 2.3 Feature Encoding

The classifier was trained on a 14-feature vector. ONNX inference must produce the exact same input vector the model was trained on. The feature names and encoding must match the backend `classifier.py` exactly:

```
age, heart_rate, spo2, temperature, bp_systolic, bp_diastolic,
chest_pain, shortness_of_breath, high_fever, unconscious,
altered_sensorium, severe_vomiting, abdominal_pain, known_cardiac
```

Missing vitals: backend uses `-1` sentinel. The ONNX frontend code must apply the same sentinel. Symptom booleans: `1` if selected, `0` if not. All values must be `Float32`.

---

## 3. Step-by-Step Instructions

### STEP 1 — Backend: Convert .pkl to .onnx

This is a one-time Python script. Run it in the backend environment (not Colab — run locally where `sklearn`, `skl2onnx`, and `onnxconverter-common` are installed):

```bash
pip install skl2onnx onnxconverter-common
```

Create `backend/scripts/export_onnx.py`:

```python
"""
Converts triage_classifier.pkl → triage_classifier.onnx
Run from backend/ directory: python scripts/export_onnx.py

Requires: skl2onnx, onnxconverter-common
Output: models/triage_classifier.onnx (~500KB)
"""
import pickle
import numpy as np
from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType

MODEL_PATH  = 'models/triage_classifier.pkl'
OUTPUT_PATH = 'models/triage_classifier.onnx'
N_FEATURES  = 14

with open(MODEL_PATH, 'rb') as f:
    model_data = pickle.load(f)

classifier = model_data['classifier']
feature_names = model_data['feature_names']

print(f"Feature names ({len(feature_names)}): {feature_names}")
print(f"Label map: {model_data['label_map']}")

# Define input type: float32 tensor, shape [None, 14]
initial_type = [('float_input', FloatTensorType([None, N_FEATURES]))]

# Convert
onnx_model = convert_sklearn(
    classifier,
    initial_types=initial_type,
    target_opset=17,
)

with open(OUTPUT_PATH, 'wb') as f:
    f.write(onnx_model.SerializeToString())

print(f"Exported: {OUTPUT_PATH}")
print(f"Size: {len(onnx_model.SerializeToString()) / 1024:.1f} KB")

# Smoke test
import onnxruntime as rt
sess = rt.InferenceSession(OUTPUT_PATH)
test_input = np.array([[55, 88, 91, 37.5, 145, 92, 1, 1, 0, 0, 0, 0, 0, 0]], dtype=np.float32)
pred = sess.run(None, {'float_input': test_input})
print(f"Smoke test prediction: {pred}")
print("Conversion successful.")
```

After running, copy the output file to the frontend:

```bash
cp models/triage_classifier.onnx ../frontend/public/models/triage_classifier.onnx
```

Commit `frontend/public/models/triage_classifier.onnx` to git. It's ~500KB — acceptable as a static asset.

**Verify the label map output from the script matches the backend exactly:**
- `0 → ROUTINE`, `1 → URGENT`, `2 → EMERGENCY`

The ONNX model outputs integer class indices. The frontend must use this same mapping.

### STEP 2 — Frontend: Install onnxruntime-web

```bash
npm install onnxruntime-web
```

`onnxruntime-web` ships with WASM binaries. These must be served correctly. Add to `vite.config.js` to ensure the WASM files are copied to dist:

```javascript
// In vite.config.js, add to the existing config:
import { viteStaticCopy } from 'vite-plugin-static-copy'

// In plugins array, add:
viteStaticCopy({
  targets: [{
    src: 'node_modules/onnxruntime-web/dist/*.wasm',
    dest: '.',
  }]
})
```

```bash
npm install vite-plugin-static-copy
```

### STEP 3 — Create src/lib/triageClassifier.js

This module loads the ONNX model once and exposes a `classify(formData)` function that returns the triage result synchronously (after the async model load).

```javascript
import * as ort from 'onnxruntime-web'

// Label map must match backend exactly
const LABEL_MAP = { 0: 'ROUTINE', 1: 'URGENT', 2: 'EMERGENCY' }

// Feature order must match training exactly
const FEATURE_ORDER = [
  'age', 'heart_rate', 'spo2', 'temperature',
  'bp_systolic', 'bp_diastolic',
  'chest_pain', 'shortness_of_breath', 'high_fever', 'unconscious',
  'altered_sensorium', 'severe_vomiting', 'abdominal_pain', 'known_cardiac',
]

let sessionPromise = null

function getSession() {
  if (!sessionPromise) {
    sessionPromise = ort.InferenceSession.create('/models/triage_classifier.onnx', {
      executionProviders: ['wasm'],
    })
  }
  return sessionPromise
}

// Pre-warm: start loading as soon as this module is imported
// so the model is ready when the ASHA worker submits
getSession().catch(() => {
  // Silent fail on load — classify() will handle errors
  sessionPromise = null
})

/**
 * classify(formData) — runs offline triage inference
 *
 * formData: the IntakeForm values object
 * Returns: { triage_level: 'ROUTINE'|'URGENT'|'EMERGENCY', local: true }
 * Returns null if model not loaded or inference fails
 */
export async function classify(formData) {
  try {
    const session = await getSession()

    // Build feature vector in training order
    // Missing vitals → -1 sentinel (matches backend)
    const features = FEATURE_ORDER.map(name => {
      const val = formData[name]
      if (val === null || val === undefined || val === '') return -1
      return parseFloat(val)
    })

    const tensor = new ort.Tensor('float32', Float32Array.from(features), [1, FEATURE_ORDER.length])
    const results = await session.run({ float_input: tensor })

    // ONNX outputs: label (int64 class index) and probabilities
    const classIndex = Number(results['label'].data[0])
    const triageLevel = LABEL_MAP[classIndex] || 'ROUTINE'

    return {
      triage_level: triageLevel,
      local: true,       // flags this as a local/preliminary result
    }
  } catch (err) {
    console.warn('ONNX inference failed:', err)
    return null           // caller handles null gracefully
  }
}

/**
 * warmUp() — call on ASHAPanel mount to pre-load the model
 * so first submission has no latency
 */
export async function warmUp() {
  try {
    await getSession()
  } catch {
    // Silent fail
  }
}
```

### STEP 4 — Update src/lib/api.js submitCase()

Update the offline-aware `submitCase()` to run local triage before queuing:

```javascript
import { classify } from './triageClassifier'

export async function submitCase(formData) {
  const clientId = uuidv4()
  const payload  = {
    ...formData,
    client_id:           clientId,
    client_submitted_at: new Date().toISOString(),
  }

  // Run local classifier regardless of connectivity
  // This gives instant feedback even offline
  const localTriage = await classify(formData)

  if (!navigator.onLine) {
    const token = await getAccessToken()
    // Store local triage result with the queued entry for UI display
    await enqueue(clientId, payload, token, localTriage)
    return { queued: true, client_id: clientId, local_triage: localTriage }
  }

  // Online path — POST to server
  // Server runs authoritative classifier, local result is just for UX feedback
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/submit`, {
    method: 'POST', headers, body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(await res.text())
  const serverResult = await res.json()

  // Return server result but include local_triage for immediate UI feedback
  // (server triage is authoritative and should match local)
  return { ...serverResult, local_triage: localTriage }
}
```

Update `offlineQueue.js` `enqueue()` to accept and store `localTriage`:

```javascript
export async function enqueue(clientId, payload, accessToken, localTriage = null) {
  const db = await getQueueDB()
  await db.put(STORE_NAME, {
    client_id:    clientId,
    payload,
    access_token: accessToken,
    local_triage: localTriage,
    queued_at:    new Date().toISOString(),
  })
}
```

### STEP 5 — Update IntakeForm.jsx — Triage Result Display

Update the submit handler to show the local triage result immediately:

```javascript
const result = await submitCase(formData)

// Show triage badge immediately regardless of online/offline state
if (result.local_triage) {
  setLocalTriageResult(result.local_triage)
}

if (result.queued) {
  showToast('Saved offline — will sync when connected', 'warning')
} else {
  showToast('Case submitted successfully', 'success')
}
```

Add a triage result card below the form submit button that appears after submission. It should show:

```jsx
{localTriageResult && (
  <div className={`mt-4 rounded-lg border-l-4 p-4 ${TRIAGE_BG[localTriageResult.triage_level]}`}>
    <div className="flex items-center justify-between">
      <span className={`font-semibold text-sm ${TRIAGE_TEXT[localTriageResult.triage_level]}`}>
        {localTriageResult.triage_level}
      </span>
      {localTriageResult.local && (
        <span className="text-xs text-slate-400">Preliminary · Full analysis after sync</span>
      )}
    </div>
  </div>
)}
```

Use the existing `TRIAGE_BG` and `TRIAGE_TEXT` color maps from Phase 5.

### STEP 6 — Warm Up Model on ASHA Panel Mount

In `ASHAPanel.jsx`, import and call `warmUp()` on mount so the WASM model is loaded before the worker needs to submit:

```javascript
import { warmUp } from '../lib/triageClassifier'

useEffect(() => {
  warmUp()           // pre-load ONNX model in background
  processQueue()
  // ... existing online event listener
}, [])
```

This means the first form submission has ~0ms ONNX latency instead of 200-500ms WASM load time.

---

## 4. Verification Checklist

| # | Check | Expected Result |
|---|---|---|
| 1 | Run `export_onnx.py` | Produces `triage_classifier.onnx`, smoke test passes, size ~500KB |
| 2 | `npm run build` | Clean build. WASM files present in `dist/`. |
| 3 | Open ASHA panel — DevTools > Network | `triage_classifier.onnx` loads once, status 200 |
| 4 | Submit form online (EMERGENCY patient: age 65, SpO2 88, chest_pain=1) | Local triage badge shows EMERGENCY immediately, then server confirms EMERGENCY |
| 5 | Submit form offline (same patient) | Local triage badge shows EMERGENCY. Queue entry in IndexedDB has `local_triage: {triage_level: EMERGENCY}` |
| 6 | Reconnect after offline submission | Submission syncs. ASHA submission history shows server-confirmed EMERGENCY. |
| 7 | Submit form online (ROUTINE patient: age 30, SpO2 99, no symptoms) | Local badge shows ROUTINE. Server confirms ROUTINE. |
| 8 | Local result matches server result in 3+ test cases | Triage labels should be identical (same model, same weights) |
| 9 | DevTools > Network > set Offline, submit form | ONNX inference runs with no network calls |
| 10 | PWA installed on Android, go airplane mode, submit form | EMERGENCY badge shown immediately with "Preliminary · Full analysis after sync" |

---

## 5. What NOT to Do

- **Do NOT attempt to convert the SHAP TreeExplainer to ONNX.** It is not supported. Offline gives triage level only — risk driver comes after sync.
- **Do NOT use the local triage result as authoritative in the database.** The server always runs its own inference. The local result is UI-only.
- **Do NOT load the ONNX model in the service worker.** `onnxruntime-web` WASM runs in the main thread. Service worker context does not support all required browser APIs for WASM.
- **Do NOT skip the feature order check.** If `FEATURE_ORDER` in `triageClassifier.js` does not exactly match the training order in backend `classifier.py`, the model will produce incorrect results silently.
- **Do NOT increase the ONNX model complexity.** The 500KB file size is the result of converting the exact production model. Do not retrain or change the model in this phase.

---

## 6. Files Summary

### New Files

| File | Purpose |
|---|---|
| `backend/scripts/export_onnx.py` | One-time conversion script — pkl → onnx |
| `frontend/public/models/triage_classifier.onnx` | ONNX model served as static asset (~500KB) |
| `frontend/src/lib/triageClassifier.js` | ONNX session management + `classify()` + `warmUp()` |

### Modified Files

| File | Change |
|---|---|
| `frontend/vite.config.js` | Add `vite-plugin-static-copy` to copy WASM binaries to dist |
| `frontend/src/lib/api.js` | `submitCase()` calls `classify()` before queue/POST. Returns `local_triage`. |
| `frontend/src/lib/offlineQueue.js` | `enqueue()` accepts and stores `localTriage` |
| `frontend/src/IntakeForm.jsx` | Show local triage badge after submission. Handle `local_triage` in result. |
| `frontend/src/panels/ASHAPanel.jsx` | Call `warmUp()` on mount |
| `frontend/package.json` | Add `onnxruntime-web`, `vite-plugin-static-copy` |
