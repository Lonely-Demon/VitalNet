# VitalNet — System Improvement Instructions

> **Version:** 1.2 — March 2026 (Phase 11 PWA Hardening)  
> **Scope:** Targeted improvements to the Phase 10 codebase addressing security, reliability, accuracy, and code health. All changes are grounded in direct reading of the current source files. This document should be executed after the rebuild defined in `REBUILD_INSTRUCTIONS.md` is complete and verified.  
> **Intended reader:** An AI coding agent or developer. Follow each section in order; later sections may depend on earlier ones.

> [!NOTE]
> **v1.2 changes:** Added four deep-dive architectural epics for PWA hardening: safe draft keying via `client_id`, Zod clinical sanity bounds, extended Groq LLM timeouts, and Service Worker cache invalidation.

> [!IMPORTANT]
> Reading this file requires context from `REBUILD_INSTRUCTIONS.md`. The architecture described there (4-tier LLM fallback, cursor pagination, offline-first auth) is assumed to be already implemented before starting this document.

---

## 0. Pre-Improvement Checklist

Before starting, verify the baseline state:

- [ ] `python test_e2e.py` — all tests pass
- [ ] `python test_direct.py` — all tests pass
- [ ] `npm run dev` — frontend loads without console errors
- [ ] `git status` — working tree is clean (no uncommitted changes)
- [ ] `backend/models/` contains **only** `enhanced_triage_classifier.pkl`

---

## 1. Critical — Security & Reliability Fixes

These must be done first. They address a security vulnerability and a broken utility script introduced by the model cleanup.

### 1.1 Remove Traceback Exposure from Error Handler

**File:** `backend/main.py`

**Problem:** The root exception handler in `submit_case()` at line 124–127 returns the full Python traceback in the HTTP 500 response body:

```python
# CURRENT — dangerous:
raise HTTPException(status_code=500, detail={
    "error": str(e),
    "traceback": traceback.format_exc()  # ← SECURITY RISK
})
```

This leaks internal file paths, library names, version strings, and implementation details to the client. It must never reach a production HTTP response.

**Two sub-fixes required (peer review):**

**Sub-fix A — Move all imports to module level.** The current handler does `import traceback` and `from fastapi import HTTPException` inside the `except` block. Inline imports inside an exception handler are un-Pythonic and dangerous — under extreme resource exhaustion (OOM, file descriptor leak), the import itself can fail, leaving the client hanging with a hung connection instead of a 500. Move both to the top of `main.py` with the existing imports.

**Sub-fix B — Replace `print()` with `logging.error()`.** `print()` does not integrate with uvicorn's log infrastructure. `logging.error(..., exc_info=True)` correctly attaches the traceback to the structured log record so it appears in uvicorn's stderr output with timestamp and level formatting.

**Step 1 — Add to the top-level imports block in `main.py`:**

```python
import logging
import traceback
from fastapi import FastAPI, Depends, Header, HTTPException, Request

logger = logging.getLogger("vitalnet")
```

**Step 2 — Replace the `except` block in `submit_case()` (lines 124–127):**

```python
except Exception as e:
    logger.error(
        "submit_case failed for client_id=%s: %s",
        form.client_id, e,
        exc_info=True,   # attaches full traceback to the log record
    )
    raise HTTPException(
        status_code=500,
        detail="An internal server error occurred. The case was not saved. Please retry."
    )
```

**Verification:** Disconnect Supabase, submit a case. Confirm:
- HTTP response body: `"detail": "An internal server error occurred..."` only — no paths, no traceback
- uvicorn stderr: full traceback visible with timestamp

---

### 1.2 Fix Broken ONNX Export Script (`export_onnx.py`)

**Files affected:**
- `backend/scripts/export_onnx.py` — broken (references deleted file)
- The currently-serving `frontend/public/models/triage_classifier.onnx` — may be stale

**Problem (introduced by the cleanup in this session):** `export_onnx.py` at line 31 hardcodes `PKL_PATH` to point to `backend/models/triage_classifier.pkl` — the legacy model **that was just deleted**:

```python
# CURRENT — references a file that no longer exists:
PKL_PATH = os.path.join(BACKEND_DIR, "models", "triage_classifier.pkl")
```

Running this script now raises `FileNotFoundError`. More critically, the script exports the **wrapped VotingClassifier from the legacy pkl bundle** using `skl2onnx.convert_sklearn()`. The enhanced model (`enhanced_triage_classifier.pkl`) cannot be exported with the same approach because `EnhancedTriageClassifier` pickle contains a `VotingClassifier` wrapping a `CalibratedClassifierCV` — **skl2onnx does not directly support this pipeline**.

**Root cause analysis:** The correct ONNX export path for the enhanced classifier is to export the **`meta_classifier` (`VotingClassifier`) before calibration** — probabilities are softer from the voting ensemble and accurate enough for offline triage. Alternatively, export only the `clinical_reasoner` (`HistGradientBoostingClassifier`) as a standalone model with `skl2onnx` for guaranteed compat.

**Recommended fix — export the `clinical_reasoner` sub-model as the ONNX artifact:**

The `clinical_reasoner` (`HistGradientBoostingClassifier`, Stage 3) is the most feature-complete sub-model and is directly supported by `skl2onnx`. It is trained on the full 45-feature vector and produces calibrated probabilities. Offline inference does not need the full ensemble — a calibrated HGBC is already clinical-grade for preliminary triage.

**Updated `export_onnx.py` — full replacement:**

```python
#!/usr/bin/env python3
"""
Export the clinical_reasoner sub-model from enhanced_triage_classifier.pkl
to ONNX format for client-side inference via onnxruntime-web.

Why clinical_reasoner (not the full ensemble):
- skl2onnx supports HistGradientBoostingClassifier natively
- CalibratedClassifierCV wrapping VotingClassifier is not serialisable to ONNX
- The clinical_reasoner is trained on all 45 features, same pipeline as backend
- Offline triage is preliminary — the full ensemble runs on the server on sync

Usage:
    pip install skl2onnx onnxruntime
    cd backend
    python scripts/export_onnx.py

Output:
    frontend/public/models/triage_classifier.onnx
"""

import os
import sys
import warnings
import numpy as np

warnings.filterwarnings("ignore", category=UserWarning)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
BACKEND_DIR  = os.path.join(PROJECT_ROOT, "backend")
PKL_PATH     = os.path.join(BACKEND_DIR, "models", "enhanced_triage_classifier.pkl")
ONNX_DIR     = os.path.join(PROJECT_ROOT, "frontend", "public", "models")
ONNX_PATH    = os.path.join(ONNX_DIR, "triage_classifier.onnx")

sys.path.insert(0, BACKEND_DIR)

# ---------------------------------------------------------------------------
# Load enhanced model and extract clinical_reasoner sub-model
# ---------------------------------------------------------------------------
print(f"[1/5] Loading enhanced model from {PKL_PATH}")
from enhanced_classifier import EnhancedTriageClassifier

classifier = EnhancedTriageClassifier.load_model(PKL_PATH)

if not classifier.is_trained:
    raise RuntimeError("Loaded model reports is_trained=False — cannot export.")

# Extract the HistGradientBoostingClassifier sub-model
clinical_reasoner = classifier.clinical_reasoner
num_features = classifier.feature_count

print(f"       Sub-model  : {type(clinical_reasoner).__name__}")
print(f"       Features   : {num_features}")
print(f"       Labels     : {{0: ROUTINE, 1: URGENT, 2: EMERGENCY}}")

# ---------------------------------------------------------------------------
# Convert to ONNX
# ---------------------------------------------------------------------------
print("[2/5] Converting clinical_reasoner to ONNX ...")

from skl2onnx import convert_sklearn
from skl2onnx.common.data_types import FloatTensorType
import onnx
from onnx import helper as onnx_helper

# Monkey-patch for numpy bool serialisation bug in skl2onnx 1.20
_orig_make_attribute = onnx_helper.make_attribute

def _patched_make_attribute(key, value):
    if isinstance(value, (list, tuple)):
        value = [int(v) if isinstance(v, (bool, np.bool_)) else v for v in value]
    elif isinstance(value, (bool, np.bool_)):
        value = int(value)
    return _orig_make_attribute(key, value)

onnx_helper.make_attribute = _patched_make_attribute

try:
    onnx_model = convert_sklearn(
        clinical_reasoner,
        initial_types=[("float_input", FloatTensorType([None, num_features]))],
        target_opset=15,
        options={id(clinical_reasoner): {"zipmap": False}},
    )
finally:
    onnx_helper.make_attribute = _orig_make_attribute

# ---------------------------------------------------------------------------
# Validate output names
# ---------------------------------------------------------------------------
output_names = [o.name for o in onnx_model.graph.output]
print(f"       ONNX outputs: {output_names}")

assert "label" in output_names, (
    f"Expected output 'label', got {output_names}. "
    "The frontend (triageClassifier.js) depends on this name."
)
assert "probabilities" in output_names, (
    f"Expected output 'probabilities', got {output_names}. "
    "The frontend (triageClassifier.js) depends on this name."
)

# ---------------------------------------------------------------------------
# Sanity check with onnxruntime
# ---------------------------------------------------------------------------
print("[3/5] Running sanity check ...")

import onnxruntime as onnxrt
from clinical_features import ClinicalFeatureEngineer

engineer = ClinicalFeatureEngineer()
feat_dict = engineer.engineer_features({
    "patient_age": 30,
    "patient_sex": "male",
    "bp_systolic": 120,
    "bp_diastolic": 80,
    "spo2": 98,
    "heart_rate": 72,
    "temperature": 37.0,
    "symptoms": [],
    "chief_complaint": "Headache",
    "complaint_duration": "1-3 days",
    "location": "Mumbai City",
    "known_conditions": "",
    "observations": "",
    "current_medications": "",
})

label_map = {0: "ROUTINE", 1: "URGENT", 2: "EMERGENCY"}

# Feature order must match the training order —use sorted keys (same as training)
feature_names = sorted(feat_dict.keys())  # matches how the enhanced model was trained
dummy = np.array(
    [[feat_dict[name] for name in feature_names]],
    dtype=np.float32,
)

sess = onnxrt.InferenceSession(onnx_model.SerializeToString())
onnx_out = sess.run(None, {"float_input": dummy})
predicted_label = int(onnx_out[0][0])
probabilities   = onnx_out[1][0]

print(f"       Predicted : {predicted_label} → {label_map[predicted_label]}")
print(f"       Probs     : {[round(float(p), 4) for p in probabilities]}")

# A normal dummy patient should be ROUTINE (0)
if predicted_label != 0:
    print("  [WARN] Expected ROUTINE for a healthy dummy patient — check model.")

# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------
print(f"[4/5] Saving to {ONNX_PATH}")
os.makedirs(ONNX_DIR, exist_ok=True)
with open(ONNX_PATH, "wb") as f:
    f.write(onnx_model.SerializeToString())

file_size_kb = os.path.getsize(ONNX_PATH) / 1024
print(f"       Done!  Size: {file_size_kb:.1f} KB  ({num_features} features)")

print("[5/5] ONNX export complete.")
print(f"       Frontend serves it at: /models/triage_classifier.onnx")
print("       Sub-model: clinical_reasoner (HistGradientBoostingClassifier, Stage 3)")
print("       NOTE: feature order is sorted(feat_dict.keys()) — must match triageClassifier.js")
```

> [!IMPORTANT]
> After running this script, you MUST verify that the feature order used in `triageClassifier.js` (`buildFeatureVector`) exactly matches the order produced by `sorted(feat_dict.keys())` from `ClinicalFeatureEngineer`. The JS file currently assembles features in a hand-coded order (lines 342–358 of `triageClassifier.js`). If the trained model's feature order differs from the JS order, the ONNX model will misclassify. Run the sanity check in step 4 of the script and also add a cross-check (see Section 1.3).

**Run the export:**

```powershell
cd d:\Southern_Ring_Nebula\VitalNet\backend
pip install skl2onnx onnxruntime  # if not already installed
python scripts/export_onnx.py
```

---

### 1.3 Automate ONNX Feature Order via `features_config.json`

> [!IMPORTANT]
> This section supersedes the original manual cross-check script. The `features_config.json` approach eliminates an entire class of silent bugs where Python and JS fall out of sync.

**Problem:** The original plan relied on `check_feature_order.py` — a manual comparison between the Python feature list and the hand-coded JS array in `triageClassifier.js`. This human-in-the-loop sync is fragile. If a feature is added to `ClinicalFeatureEngineer` next month and the JS is not updated, the ONNX model will produce confidently wrong triage classifications with no runtime error.

**Fix — two coordinated changes:**

**Sub-fix A — Extend `export_onnx.py` to generate `features_config.json`:**

Add the following as a new final step in `export_onnx.py`, after the ONNX file is saved:

```python
# [NEW STEP 5b] Generate features_config.json alongside the ONNX model
import json

features_config = {
    "feature_names": feature_names,   # sorted list, same order as ONNX input layer
    "num_features": len(feature_names),
    "model": "clinical_reasoner (HistGradientBoostingClassifier)",
    "exported_at": __import__('datetime').datetime.utcnow().isoformat() + "Z",
}

config_path = os.path.join(ONNX_DIR, "features_config.json")
with open(config_path, "w") as f:
    json.dump(features_config, f, indent=2)

print(f"       Features manifest: {config_path}")
print(f"       Feature count: {len(feature_names)}")
```

**Sub-fix B — Update `triageClassifier.js` to consume `features_config.json` dynamically:**

Replace the static `buildFeatureVector()` function with a config-driven version. The JSON manifest is fetched once during `loadModel()` and cached in module scope.

```javascript
// At the top of triageClassifier.js, replace the hardcoded NUM_FEATURES and add:
const FEATURES_CONFIG_PATH = '/models/features_config.json'
let _featureNames = null   // populated during model warmup

// Replace loadModel() to also load the feature config:
export async function loadModel() {
  if (_session && _featureNames) return _session
  if (_loadPromise) return _loadPromise

  _loadPromise = Promise.all([
    ort.InferenceSession.create(MODEL_PATH, {
      executionProviders: ['wasm'],
      graphOptimizationLevel: 'all',
    }),
    fetch(FEATURES_CONFIG_PATH).then(r => r.json()),
  ]).then(([session, config]) => {
    _session = session
    _featureNames = config.feature_names   // canonical order from Python
    _loadPromise = null
    console.log(`[VitalNet] ONNX model loaded (${config.num_features} features, ${config.model})`)
    return session
  }).catch((err) => {
    _loadPromise = null
    console.error('[VitalNet] ONNX model or feature config load failed:', err)
    throw err
  })

  return _loadPromise
}
```

Update `buildFeatureVector()` to use `_featureNames` for final assembly:

```javascript
// The raw computed values dictionary — keys must match Python ClinicalFeatureEngineer output keys exactly
function buildFeatureMap(formData) {
  // ... (all existing computation logic stays here, unchanged) ...
  // Return a KEY-VALUE map, NOT an ordered array
  return {
    age, sex, bp_systolic: bpSys, bp_diastolic: bpDia, spo2, heart_rate: hr,
    temperature: temp, symptom_count: symptomCount,
    chest_pain: chestPain, breathlessness, altered_consciousness: alteredConsciousness,
    severe_bleeding: severeBleeding, seizure, high_fever: highFever,
    pulse_pressure: pulsePressure, mean_arterial_pressure: meanArterialPressure,
    shock_index: shockIndex, spo2_age_ratio: spo2AgeRatio, temp_deviation: tempDeviation,
    cardiac_risk_score: cardiacRisk, respiratory_distress_score: respDistress,
    hemodynamic_instability: hemodynamic, sepsis_risk_score: sepsisRisk,
    pediatric_adjustment: pediatricAdj, geriatric_adjustment: geriatricAdj,
    pregnancy_adjustment: pregnancyAdj,
    cardiopulmonary_cluster: cardiopulmonaryCluster, neurological_cluster: neurologicalCluster,
    hemorrhagic_cluster: hemorrhagicCluster, infectious_cluster: infectiousCluster,
    symptom_severity_score: symptomSeverity, duration_risk: durationRisk,
    complaint_risk: complaintRisk, comorbidity_multiplier: comorbidityMult,
    pediatric_fever_risk: pediatricFeverRisk, elderly_fall_risk: elderlyFallRisk,
    adult_cardiac_risk: adultCardiacRisk, obstetric_risk: obstetricRisk,
    trauma_severity: traumaSeverity, mental_health_crisis: mentalHealthCrisis,
    time_of_day_risk: timeOfDayRisk, seasonal_risk: seasonalRisk,
    geographic_risk: geographicRisk, epidemic_alert_level: epidemicAlertLevel,
    healthcare_accessibility: healthcareAccessibility,
  }
}

// Build ordered Float32Array using the canonical feature order from Python
function buildFeatureVector(formData) {
  if (!_featureNames) throw new Error('Feature config not loaded yet — call loadModel() first')
  const featureMap = buildFeatureMap(formData)
  return new Float32Array(_featureNames.map(name => featureMap[name] ?? 0))
}
```

> [!NOTE]
> The key names in `buildFeatureMap()` must match the keys returned by Python's `ClinicalFeatureEngineer.engineer_features()`. Run `python scripts/check_feature_order.py` (kept as a debug utility) to print the exact Python key names and verify the JS map uses identical strings.

**Run the export to regenerate both artefacts:**

```powershell
cd d:\Southern_Ring_Nebula\VitalNet\backend
python scripts/export_onnx.py
# Produces: frontend/public/models/triage_classifier.onnx
#           frontend/public/models/features_config.json
```

---

### 1.4 Remove Dead Legacy Fallback Code from `classifier.py`

**File:** `backend/classifier.py`

**Problem:** `classifier.py` still references `LEGACY_PKL_PATH` (line 13) and contains a full legacy loading branch (lines 67–100) that tries to load `triage_classifier.pkl` — the file that was deleted. If the enhanced classifier fails to load for any reason, the code tries the legacy path, fails with `FileNotFoundError`, and raises `RuntimeError("No valid classifier found")` — losing meaningful error context.

Additionally, lines 24–29 declare six global variables (`_clf`, `_explainer`, `_feature_names`, `_label_map`, `_accuracy`, `_emergency_fn`) that are only used by the legacy path. They are dead code.

**Fix — clean up `classifier.py`:**

1. **Remove** `LEGACY_PKL_PATH` constant (line 13)
2. **Remove** the six legacy global variable declarations (lines 24–29)
3. **Replace** the `load_classifier()` function with a simplified version that only loads the enhanced model and raises a descriptive error on failure:

```python
def load_classifier() -> bool:
    """
    Load the enhanced multi-stage classifier.
    Raises RuntimeError with a descriptive message if loading fails.
    """
    global _classifier, _classifier_type, _model_info

    if not ENHANCED_PKL_PATH.exists():
        raise RuntimeError(
            f"Enhanced classifier not found at {ENHANCED_PKL_PATH}. "
            "Run backend/scripts/retrain_and_export.py to regenerate."
        )

    try:
        from enhanced_classifier import EnhancedTriageClassifier
        _classifier = EnhancedTriageClassifier.load_model(str(ENHANCED_PKL_PATH))
        _classifier_type = "enhanced"
        _model_info = _classifier.get_model_info()

        acc = _model_info['performance_metrics'].get('accuracy', 'N/A')
        recall = _model_info['performance_metrics'].get('emergency_recall', 'N/A')
        print(f"[OK] Enhanced classifier loaded — v{_model_info['model_version']}")
        print(f"[OK] Accuracy: {acc:.4f}  Emergency recall: {recall:.4f}")
        return True

    except Exception as e:
        raise RuntimeError(
            f"Enhanced classifier loading failed: {e}. "
            "The model file may be corrupt. Run retrain_and_export.py to regenerate."
        ) from e
```

4. **Remove** `_predict_legacy()` function (lines 154–177) — it is now unreachable
5. **Remove** `_get_legacy_risk_driver()` function (lines 283–313) — it is now unreachable
6. **Update** `_predict_enhanced()` to remove the inner legacy fallback (lines 146–148):

```python
# Remove this block from _predict_enhanced() — legacy fallback is gone:
# if _clf is not None:
#     return _predict_legacy(form_data)
```

Replace the except block with:

```python
    except Exception as e:
        print(f"[ERROR] Enhanced prediction failed: {e}")
        raise  # Let main.py's handler catch this as a 500
```

---

### 1.5 Harden the Health Check Endpoint

**File:** `backend/main.py`

**Problem:** `GET /api/health` always returns `"classifier": "loaded"` at line 61, regardless of whether `load_classifier()` succeeded at startup. If the classifier fails silently, the health check gives a false "all green" signal.

**Fix — expose actual classifier state via the public `get_classifier_info()` API:**

```python
@app.get("/api/health")
async def health():
    from classifier import get_classifier_info

    # Database connectivity check
    try:
        supabase_anon.table("facilities").select("id").limit(1).execute()
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)[:80]}"  # Truncate — never expose full errors

    # Classifier state — use public API, not private _classifier_type variable
    info = get_classifier_info()
    classifier_loaded = bool(info["classifier_type"])
    classifier_status = (
        f"loaded — {info['classifier_type']} v{info['model_info'].get('model_version', 'N/A')}"
        if classifier_loaded
        else "NOT LOADED"
    )

    return {
        "status": "ok" if db_status == "connected" and classifier_loaded else "degraded",
        "database": db_status,
        "classifier": classifier_status,
        "version": "0.2.0",
    }
```

---

## 2. Medium Priority — Accuracy & Performance

### 2.1 Apply DB-Level Triage Sorting (Complete the Deferred Step)

**Files:** Supabase SQL + `backend/main.py`

**Problem:** `GET /api/cases` currently fetches by `created_at` cursor from the DB and then **re-sorts the fetched page in Python** (line 174–175 of `main.py`) by triage priority. This means an EMERGENCY case submitted 3 days ago is correctly elevated within its page, but **cannot bubble above newer ROUTINE cases** fetched in earlier pages. Doctors see 50 newest cases sorted by priority within that window — not a true global priority queue.

This was noted as deferred in `REBUILD_INSTRUCTIONS.md` Section 4.2. Execute it now.

**Step 1 — Add Supabase computed column:**

Run in the Supabase SQL editor:

```sql
-- Add triage_priority as a stored computed column
ALTER TABLE case_records ADD COLUMN IF NOT EXISTS triage_priority INTEGER
GENERATED ALWAYS AS (
    CASE triage_level
        WHEN 'EMERGENCY' THEN 0
        WHEN 'URGENT'    THEN 1
        WHEN 'ROUTINE'   THEN 2
        ELSE 3
    END
) STORED;

-- Add index for the new sort column
CREATE INDEX IF NOT EXISTS idx_case_records_triage_sort
ON case_records (triage_priority ASC, created_at DESC)
WHERE deleted_at IS NULL;
```

**Step 2 — Update `GET /api/cases` in `main.py`:**

Replace lines 155–175 (the current query + Python sort). The critical fix here is the **composite keyset cursor** — the old implementation used a single `created_at` cursor against a multi-column sort, which causes cases to silently disappear at triage tier boundaries:

```python
# Update route signature to accept both cursor components:
@app.get("/api/cases")
async def get_cases(
    authorization: str = Header(None),
    user: dict = Depends(require_role("doctor", "admin")),
    before_time: str = None,      # ISO timestamp of the last seen case
    before_priority: int = None,  # triage_priority of the last seen case (0/1/2)
    limit: int = 25,
):
    raw_token = (authorization or "").split(" ", 1)[-1]
    db = get_supabase_for_user(raw_token)
    limit = max(1, min(limit, 100))

    query = (
        db.table("case_records")
        .select(
            "id, patient_name, patient_age, patient_sex, "
            "triage_level, triage_priority, triage_confidence, risk_driver, "
            "created_at, reviewed_at, reviewed_by, facility_id, created_offline"
        )
        .is_("deleted_at", "null")
        .order("triage_priority", desc=False)   # EMERGENCY (0) first
        .order("created_at", desc=True)          # Newest within each tier
        .limit(limit + 1)
    )

    if before_time is not None and before_priority is not None:
        # Composite keyset cursor:
        # Fetch cases that are AFTER the last seen case in the sort order:
        # either (a) lower priority tier (higher integer), OR
        # (b) same priority tier but older created_at.
        # This is the correct two-column keyset pagination pattern.
        #
        # PostgREST or_() string: supabase-py passes this as a raw filter.
        # Verified syntax: or(col.op.val,and(col.eq.val,col.lt.val))
        query = query.or_(
            f"triage_priority.gt.{before_priority},"
            f"and(triage_priority.eq.{before_priority},created_at.lt.{before_time})"
        )

    result = query.execute()
    rows = result.data

    has_more = len(rows) > limit
    cases = rows[:limit]
    # No Python-side sort needed — DB handles ordering

    return {
        "cases": cases,
        "hasMore": has_more,
        # Return both cursor components for the next page request
        "nextCursor": cases[-1]["created_at"] if has_more and cases else None,
        "nextTriagePriority": cases[-1]["triage_priority"] if has_more and cases else None,
    }
```

> [!IMPORTANT]
> The `or_()` nested-and filter string requires PostgREST v10+. Supabase Platform runs PostgREST v11+ so this is safe, but verify with a quick integration test (see Section 4.3, Step 6).

**Frontend update (`api.js`):** Update `getCases()` to pass `before_time` and `before_priority` as query parameters instead of just `before`, and thread `nextTriagePriority` through the "Load More" state in `Dashboard.jsx`.

---

### 2.2 Add API Rate Limiting with `slowapi` (Per-User, Not Per-IP)

**Files:** `backend/requirements.txt`, `backend/main.py`

**Problem:** `POST /api/submit` has no rate limiting. A misbehaving client or buggy retry loop could exhaust Groq/Gemini quotas.

**Why not IP-based limiting:** In rural healthcare settings (the primary deployment context for VitalNet), an entire clinic’s ASHA workers often share a single NAT or satellite connection — meaning they all present the same public IP. If 5 workers each submit 4 cases in a minute, an IP-based 20/minute limit would lock out the entire facility. The correct identity for rate limiting is the **authenticated user**, not the connection point.

**Step 1 — Add to `requirements.txt`:**

```text
slowapi==0.1.9
```

**Step 2 — Define a per-user key function in `main.py`:**

The JWT payload is already validated and decoded by `get_current_user()` before the route runs. Extract the `sub` (Supabase user ID) from the request — but since `slowapi`’s key function runs before `Depends()`, we must decode the token directly in the key function:

```python
import base64, json as _json
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

def _get_user_id(request: Request) -> str:
    """
    Extract the Supabase user ID (sub) from the Bearer JWT for rate limiting.
    Falls back to client IP if the token is absent or malformed —
    this prevents unauthenticated callers from bypassing the limiter.
    """
    try:
        auth_header = request.headers.get("authorization", "")
        token = auth_header.split(" ", 1)[-1]
        payload_b64 = token.split(".")[1]
        payload_b64 += "=" * (-len(payload_b64) % 4)
        payload = _json.loads(base64.urlsafe_b64decode(payload_b64))
        return payload.get("sub") or request.client.host
    except Exception:
        return request.client.host  # fallback: IP-based limiting for bad tokens

limiter = Limiter(key_func=_get_user_id)
```

**Step 3 — Register and apply:**

```python
# After app = FastAPI(...):
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Apply to submit endpoint (Request must be the first positional parameter):
@app.post("/api/submit")
@limiter.limit("20/minute")   # 20 per authenticated user per minute
async def submit_case(
    request: Request,
    form: IntakeForm,
    authorization: str = Header(None),
    user: dict = Depends(require_role("asha_worker", "admin")),
):
    ...
```

**Suggested limits by endpoint:**

| Endpoint | Limit | Identity | Rationale |
|---|---|---|---|
| `POST /api/submit` | 20/minute | User ID | One ASHA worker cannot physically submit >3 cases/min |
| `GET /api/cases` | 60/minute | User ID | Dashboard polling; generous for real-time feel |
| `GET /api/health` | 120/minute | IP | Monitoring probes; IP is fine here |


---

### 2.3 Paginate `GET /api/cases/mine`

**File:** `backend/main.py`

**Problem:** The ASHA worker's personal submission history endpoint (line 222–231) fetches **all** of the caller's cases with no limit:

```python
result = (
    db.table("case_records")
    .select("id, chief_complaint, triage_level, created_at, reviewed_at, patient_age, patient_sex")
    .eq("submitted_by", user["sub"])
    .is_("deleted_at", "null")
    .order("created_at", desc=True)
    .execute()   # ← no .limit()
)
```

A worker who has submitted 300+ cases over several months will pull the full dataset on every panel load. This will become progressively slower and more expensive as the deployment matures.

**Fix — add limit + cursor pagination:**

```python
@app.get("/api/cases/mine")
async def get_my_cases(
    authorization: str = Header(None),
    user: dict = Depends(require_role("asha_worker", "admin")),
    before: str = None,   # created_at ISO cursor
    limit: int = 25,
):
    raw_token = (authorization or "").split(" ", 1)[-1]
    db = get_supabase_for_user(raw_token)
    limit = max(1, min(limit, 100))

    query = (
        db.table("case_records")
        .select("id, patient_name, chief_complaint, triage_level, created_at, reviewed_at, patient_age, patient_sex")
        .eq("submitted_by", user["sub"])
        .is_("deleted_at", "null")
        .order("created_at", desc=True)
        .limit(limit + 1)
    )

    if before:
        query = query.lt("created_at", before)

    result = query.execute()
    rows = result.data
    has_more = len(rows) > limit

    return {
        "cases": rows[:limit],
        "hasMore": has_more,
        "nextCursor": rows[limit - 1]["created_at"] if has_more and rows else None,
    }
```

> [!NOTE]
> `my cases` is sorted by `created_at DESC` only (no triage priority sort). ASHA workers view their own history chronologically. A simple single-column cursor is correct and sufficient here.

---

### 2.4 Move `train_enhanced_classifier.py` to `scripts/`

**Files affected:** `backend/train_enhanced_classifier.py` → `backend/scripts/train_enhanced_classifier.py`

**Problem:** A 17KB training script lives in the backend root directory alongside production modules (`main.py`, `llm.py`, etc.). This is misleading — an agent reading the root directory could mistake it for an active runtime module.

**Fix:**
```powershell
cd d:\Southern_Ring_Nebula\VitalNet\backend
Move-Item train_enhanced_classifier.py scripts\train_enhanced_classifier.py
```

No code changes needed — it is a standalone script with no imports referencing it.

Update `CLASSIFIER_CHANGELOG.md` to reflect the new path.

---

## 3. Code Health — Classifier Architecture Consolidation

### 3.1 Wire Up `ContinualLearningManager` or Remove It

**File:** `backend/enhanced_classifier.py`

**Problem:** `ContinualLearningManager` (lines 344–426) has a complete class interface: `add_outcome_feedback()` collects cases, tracks error severity, and supposedly triggers `_perform_model_update()` when the buffer fills. But `_perform_model_update()` (line 411) is a complete stub — it logs and clears the buffer, doing nothing else. No route in `main.py` calls `ContinualLearningManager.add_outcome_feedback()`. The class is entirely inert.

There are two valid paths:

**Option A — Remove the class (recommended for now):**
The infrastructure for collecting doctor feedback (case outcomes) does not exist yet on the frontend. Without the feedback collection UI and the `PATCH /api/cases/{id}/outcome` backend endpoint, the class cannot function. Remove it from `enhanced_classifier.py` for clarity and add a `CHANGELOG` note:

```python
# Delete lines 344–426 of enhanced_classifier.py (ContinualLearningManager class)
```

Then, when the doctor feedback feature is implemented in a future sprint, reintroduce the manager with a real implementation against a feedback queue in Supabase.

**Option B — Keep as planned stub (annotate clearly):**
If removing feels premature, add a `[STUB]` docstring that is explicit about its state:

```python
class ContinualLearningManager:
    """
    [STUB — NOT ACTIVE]
    Planned: collect named clinical outcomes from the Doctor Review flow
    and use them to trigger offline model retraining.
    
    Current state: feedback_buffer is populated correctly, but
    _perform_model_update() does not retrain — it logs and clears.
    
    Activation requires:
      1. A PATCH /api/cases/{id}/outcome endpoint
      2. A Doctor UI to submit actual patient outcomes
      3. A background task that retrains on a Supabase feedback table
    
    Do not call this class in production routes until all three exist.
    """
```

**Recommendation:** Apply **Option A** (remove), then commit. The class can be recreated properly when the feedback feature is scoped.

---

---

## 4. Architectural Epics (Pre-Feature Hardening)

The items in this section are larger in scope than the hotfixes above. They do not block the v1.1 sprint but are critical for long-term viability of VitalNet as a rural offline-first PWA. Each is a self-contained epic that should be planned individually.

---

### 4.1 Form Draft Persistence — Tab Eviction & Data Loss

**Files:** `frontend/src/pages/IntakeForm.jsx`, `frontend/src/lib/offlineQueue.js` (reuse existing IndexedDB)

**Problem:** The intake form collects up to 45 data points. Android tablets aggressively evict background browser tabs to free RAM — a 2GB device (standard ASHA worker hardware) can kill a background tab in under 30 seconds. If a worker spends 5 minutes filling the form, switches to the camera app, and returns, the tab refreshes silently and all fields are wiped.

`localStorage` is currently used only by Supabase Auth — no form state is persisted anywhere.

**Fix — implement `useDraftSave` hook (Keyed by `client_id`):**

Keying drafts by `user_id` allows only one draft at a time. If an ASHA worker gets interrupted mid-form by an emergency walk-in and starts a new case, the new case permanently overwrites the first one. By generating the `client_id` (UUID) the moment the "New Case" button is clicked, we safely isolate drafts.

```javascript
// frontend/src/hooks/useDraftSave.js
import { openDB } from 'idb'   // already available via existing offlineQueue.js

const DB_NAME = 'vitalnet-offline'
const STORE   = 'form-drafts'

export function useDraftSave(clientId) {
  // Load draft by client_id
  async function loadDraft() {
    const db = await openDB(DB_NAME, /* version */ 2, {
      upgrade(db) {
        if (!db.objectStoreNames.contains(STORE)) {
          db.createObjectStore(STORE)  // keyed manually
        }
      },
    })
    const draft = await db.get(STORE, `draft-${clientId}`)
    // Reject stale drafts older than 24h
    if (draft && Date.now() - draft.savedAt < 24 * 60 * 60 * 1000) {
      return draft.formData
    }
    return null
  }

  // Debounced auto-save — called on every form field change
  async function saveDraft(formData) {
    const db = await openDB(DB_NAME, 2)
    await db.put(STORE, { formData, savedAt: Date.now() }, `draft-${clientId}`)
  }

  // Clear after successful submission
  async function clearDraft() {
    const db = await openDB(DB_NAME, 2)
    await db.delete(STORE, `draft-${clientId}`)
  }

  return { loadDraft, saveDraft, clearDraft }
}

// Global utility for the pending drafts UI
export async function getAllPendingDrafts() {
  const db = await openDB(DB_NAME, 2)
  const keys = await db.getAllKeys(STORE)
  const drafts = await Promise.all(keys.map(k => db.get(STORE, k)))
  return drafts.map((d, i) => ({ id: keys[i].replace('draft-', ''), ...d }))
}
```

**Integration into `IntakeForm.jsx`:**

```javascript
import { v4 as uuidv4 } from 'uuid'

// Generate client_id immediately when form mounts
const [clientId] = useState(() => uuidv4())
const { loadDraft, saveDraft, clearDraft } = useDraftSave(clientId)

// On mount: URL routing should determine if we are loading an existing draft
useEffect(() => {
  // If navigating from "Pending Drafts" UI with a specific ID in URL
  if (props.draftId) {
    loadDraft().then(draft => {
      if (draft) {
        // Show a restore banner, not a silent restore
        setDraftRestorePrompt(draft)
      }
    })
  }
}, [props.draftId])

// On every field change: debounced save
useEffect(() => {
  const timer = setTimeout(() => saveDraft(formValues), 500)
  return () => clearTimeout(timer)
}, [formValues])

// After queue push / successful submission:
await clearDraft()
```

> [!IMPORTANT]
> Also add a small "Pending Drafts" list in the Dashboard UI (using `getAllPendingDrafts`) so workers can resume abandoned cases. Set a cron-like cleanup to purge abandoned drafts older than 24-48 hours so IndexedDB doesn't balloon.

---

### 4.2 True Connectivity Detection — The `navigator.onLine` Illusion

**Files:** `frontend/src/lib/api.js`, `frontend/src/hooks/useLocalTriage.js`

**Problem:** `navigator.onLine` only checks whether the device has a local interface connection (Wi-Fi, LTE). It does not confirm the remote backend is reachable. In rural clinics with satellite internet, the clinic's satellite link can go down while the Wi-Fi router remains fully up — `navigator.onLine` stays `true`. The app then attempts `fetch()` to Groq/Supabase, which hangs for 60–90 seconds (browser default timeout) before throwing `Failed to fetch`. The ASHA worker gets no triage result and no feedback during this window.

**Fix — replace `navigator.onLine` checks with an active server probe:**

Create `frontend/src/lib/connectivity.js`:

```javascript
// frontend/src/lib/connectivity.js

const PROBE_TIMEOUT_MS = 5000
const PROBE_URL = '/api/health'   // VitalNet backend itself, not an external URL

/**
 * True connectivity check: verifies the VitalNet backend is reachable.
 * Returns true only if /api/health responds within 5 seconds.
 * Uses AbortController — no hanging fetch.
 * Uses cache:'no-store' — bypasses service worker cache.
 */
export async function isServerReachable() {
  if (!navigator.onLine) return false   // fast-path: no local interface at all

  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), PROBE_TIMEOUT_MS)

  try {
    const res = await fetch(PROBE_URL, {
      method: 'GET',
      cache: 'no-store',
      signal: controller.signal,
    })
    return res.ok
  } catch {
    return false   // abort, network error, or fetch failure
  } finally {
    clearTimeout(timeout)
  }
}
```

**Update `api.js` `submitCase()` to use the probe:**

```javascript
import { isServerReachable } from './connectivity'

export async function submitCase(formData) {
  const clientId = uuidv4()   // generated before reachability check (idempotency)

  const online = await isServerReachable()   // replaces: navigator.onLine

  if (!online) {
    // Dispatch the same event used by useLocalTriage for ONNX lazy-loading
    window.dispatchEvent(new CustomEvent('vitalnet-server-unreachable'))
    await enqueueOffline({ ...formData, client_id: clientId })
    return { queued: true, client_id: clientId }
  }

  // ... rest of online submit path unchanged
}
```

**Update `useLocalTriage.js` — add a third ONNX load trigger for already-offline mount:**

```javascript
useEffect(() => {
  // Trigger 1: was already offline when page loaded
  if (!navigator.onLine) { loadOnnxModel(); return }

  // Trigger 2 & 3: go offline or server becomes unreachable mid-session
  window.addEventListener('offline', loadOnnxModel)
  window.addEventListener('vitalnet-server-unreachable', loadOnnxModel)
  return () => {
    window.removeEventListener('offline', loadOnnxModel)
    window.removeEventListener('vitalnet-server-unreachable', loadOnnxModel)
  }
}, [])
```

> [!NOTE]
> The probe URL must be `/api/health` (the VitalNet server), not an external endpoint. This correctly handles deployments where the backend is on a local clinic LAN with no internet but full LAN connectivity.

---

### 4.3 LLM Retry-Before-Downgrade — JSON Parse Errors

**File:** `backend/llm.py`

**Problem:** A `json.JSONDecodeError` on the 70B Groq model (e.g., a trailing comma, markdown code fence wrapping the JSON, or a stray explanatory sentence) immediately triggers downgrade to the 8B model. This is a formatting artifact, not a reasoning failure. Clinical briefing quality silently degrades for every submission affected by a transient formatting issue.

**Fix — two coordinated changes:**

**Sub-fix A — Add `json-repair` as a pre-parsing step:**

Install: add `json-repair==0.36.0` to `requirements.txt`.

Wrap every `json.loads()` call in `llm.py` with a repair-then-parse pattern:

```python
from json_repair import repair_json

def _parse_llm_json(raw: str) -> dict:
    """
    Parse LLM JSON output with auto-repair for common formatting errors:
    trailing commas, markdown code fences, unescaped quotes, etc.
    Raises json.JSONDecodeError only if repair also fails.
    """
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        repaired = repair_json(raw, return_objects=True)
        if isinstance(repaired, dict):
            return repaired
        raise   # re-raise original error — repair produced a non-dict
```

Replace `json.loads(response.choices[0].message.content)` in `_call_groq()` and `json.loads(response.text)` in `_call_gemini()` with `_parse_llm_json(...)`.

**Sub-fix B — Add intra-tier retry before downgrading:**

If `_parse_llm_json()` still raises after repair (genuine model failure, not formatting), retry the **same model** once before moving on:

```python
MAX_RETRIES_PER_MODEL = 1   # 1 retry = 2 total attempts per tier

# In generate_briefing(), replace the Groq loop:
if _groq_client:
    for model in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]:
        for attempt in range(MAX_RETRIES_PER_MODEL + 1):
            try:
                briefing = await _call_groq(model, patient_context)
                logger.info("Briefing via Groq/%s (attempt %d)", model, attempt + 1)
                return _enforce_schema(briefing, triage_result)
            except groq.RateLimitError:
                logger.warning("Rate limit on Groq/%s — moving to next tier", model)
                await asyncio.sleep(0.5)
                break   # rate limit is not retriable within the same tier
            except json.JSONDecodeError:
                if attempt < MAX_RETRIES_PER_MODEL:
                    logger.warning("JSON parse error on Groq/%s — retrying same model", model)
                    await asyncio.sleep(0.3)
                    continue
                logger.warning("JSON parse error on Groq/%s after retry — downgrading", model)
                break
            except Exception as e:
                logger.warning("Error on Groq/%s: %s — moving on", model, e)
                break
```

**Sub-fix C — Harden the system prompt:**

Add the following line to the end of `backend/prompts/clinical_system_prompt.txt`:

```
CRITICAL: Your response MUST be a single valid JSON object only. Do not wrap it in markdown code blocks. Do not add any explanatory text before or after the JSON. Do not use trailing commas.
```

---

### 4.4 System Prompt Crash Guard at Startup

**File:** `backend/llm.py`

**Problem:** Line 58 reads the system prompt at module import time:

```python
_SYSTEM_PROMPT: str = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
```

If the file is missing, renamed, or on a read-locked filesystem, this raises `FileNotFoundError` during module import — before FastAPI even starts. The entire application crashes with no useful error message in the uvicorn output.

**Fix — wrap with try/except and fallback:**

```python
try:
    _SYSTEM_PROMPT: str = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")
except FileNotFoundError:
    logger.error(
        "[CRITICAL] System prompt not found at %s. Using minimal fallback prompt.",
        SYSTEM_PROMPT_PATH
    )
    _SYSTEM_PROMPT = (
        "You are a clinical triage assistant. Analyse the patient data and return a JSON briefing "
        "with keys: triage_level, primary_risk_driver, differential_diagnoses, red_flags, "
        "recommended_immediate_actions, recommended_tests, uncertainty_flags, disclaimer."
    )
```

This allows the application to start and serve triage requests with a degraded but functional prompt, rather than crashing entirely.

---

### 4.5 Offline Queue Rate-Safety During Bulk Sync

**File:** `frontend/src/lib/offlineQueue.js` (or wherever `processQueue()` is called)

**Problem:** `processQueue()` submits all queued cases in a tight loop with no inter-item delay. A worker who accumulated 20 offline cases and then reconnects will fire 20 API calls in rapid succession. With the per-user rate limit of 20/minute added in Section 2.2, the 20th submission will hit the limit precisely. Any additional case or retry push would return a 429 and would need to be requeueued.

**Fix — add a paced delay between queue items:**

```javascript
// In processQueue(), add a delay between submissions:
const QUEUE_ITEM_DELAY_MS = 3500   // 3.5s = max ~17 items/minute, safely under 20/min limit

for (const item of queue) {
  try {
    await submitCase(item)
    await removeFromQueue(item.client_id)
  } catch (err) {
    // existing error handling — head-of-line skip
    console.warn('[Queue] Submission failed, skipping:', item.client_id, err)
  }
  // Rate-safety delay between items
  await new Promise(resolve => setTimeout(resolve, QUEUE_ITEM_DELAY_MS))
}
```

> [!NOTE]
> 3.5s spacing yields a maximum bulk sync rate of ~17 items/minute. Combined with the 20/minute per-user limit, this leaves headroom for any manual submissions the worker makes simultaneously during sync.

---

---

### 4.6 Clinical Sanity Bounds (Data Integrity)

**Files:** `frontend/package.json`, `frontend/src/utils/validation.js`, `frontend/src/pages/IntakeForm.jsx`

**Problem:** The ML model is garbage-in-garbage-out. The `IntakeForm` currently allows submission of clinically impossible values (e.g., Heart Rate = 900, SpO2 = 150%, Temp = 50°C). If these bad inputs enter the offline IndexedDB queue, the ONNX model processes them and derives wildly inaccurate confidence scores and feature ratios, corrupting the triage timeline.

**Fix — add hard Zod schema validation:**

Install Zod in the frontend:
```bash
cd frontend
npm install zod
```

Create `frontend/src/utils/validation.js`:
```javascript
import { z } from 'zod';

export const clinicalSchema = z.object({
  patient_name: z.string().min(2, "Name is required"),
  patient_age: z.number().min(0).max(120, "Age must be realistic"),
  patient_sex: z.enum(["male", "female", "other"]),
  bp_systolic: z.number().min(50).max(300).optional().or(z.literal('')),
  bp_diastolic: z.number().min(30).max(200).optional().or(z.literal('')),
  spo2: z.number().min(50).max(100, "SpO2 cannot exceed 100%").optional().or(z.literal('')),
  heart_rate: z.number().min(30).max(300, "Heart rate out of bounds").optional().or(z.literal('')),
  temperature: z.number().min(32).max(43, "Temperature must be between 32°C and 43°C").optional().or(z.literal('')),
  chief_complaint: z.string().min(3, "Required")
  // ... apply similar sensible bounds to other fields
});
```

In `IntakeForm.jsx`, enforce this schema *before* saving to the offline queue or submitting online. If validation fails, block submission and highlight the offending fields.

---

### 4.7 Groq LLM Timeout Bump to 15s

**File:** `backend/llm.py`

**Problem:** In `llm.py`, the `_call_groq` wrapper passes `timeout=8.0` via `asyncio.to_thread` for the `llama-3.3-70b-versatile` model. Generating a comprehensive, structured JSON clinical briefing under standard API load often takes 5–10 seconds. An 8-second limit is too aggressive and frequently trips the `Timeout` handler midway through generation, causing a premature downgrade to the inferior 8B model.

**Fix — bump timeout to safely accommodate 70B inference:**

Find the `chat.completions.create` call in `_call_groq` (around line ~110 depending on previous edits) and increase `timeout`:

```python
        # Increase from 8.0 to 15.0 for stability in 70B JSON generation
        response = await asyncio.to_thread(
            _groq_client.chat.completions.create,
            model=model_name,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(patient_context)}
            ],
            temperature=0.1,
            response_format={"type": "json_object"},
            timeout=15.0  # <--- BUMP TO 15.0
        )
```

---

### 4.8 Service Worker Cache Invalidation (Deployment Safety)

**Files:** `frontend/vite.config.js`, `frontend/src/App.jsx`

**Problem:** PWA service workers aggressively cache the frontend. You are making breaking schema updates to the backend (e.g., new composite keyset pagination payload in `main.py`). If you deploy this, ASHA workers' tablets in the field will continue serving the old JS bundle from cache until it naturally expires, causing them to send malformed queries or crash.

**Fix — UI cache invalidation prompt:**

If using `vite-plugin-pwa`, implement a prompt using `useRegisterSW` to force immediate reload.

Create `frontend/src/components/UpdatePrompt.jsx`:

```javascript
import { useRegisterSW } from 'virtual:pwa-register/react'

export function UpdatePrompt() {
  const {
    needRefresh: [needRefresh, setNeedRefresh],
    updateServiceWorker,
  } = useRegisterSW({
    onRegistered(r) {
      console.log('SW Registered:', r)
    },
    onRegisterError(error) {
      console.log('SW registration error', error)
    },
  })

  if (!needRefresh) return null

  return (
    <div className="fixed bottom-4 right-4 bg-red-600 text-white p-4 rounded-lg shadow-xl z-50">
      <p className="font-semibold mb-2">App update available.</p>
      <button 
        onClick={() => updateServiceWorker(true)} 
        className="bg-white text-red-600 px-4 py-2 rounded shadow font-medium"
      >
        Reload to Update
      </button>
      <button 
        onClick={() => setNeedRefresh(false)} 
        className="ml-2 text-white/80 hover:text-white"
      >
        Dismiss
      </button>
    </div>
  )
}
```
Mount `<UpdatePrompt />` high in the tree (e.g., `App.jsx`). This ensures rural workers immediately pull the matching frontend bundle.

---

## 5. Improvement Completion Verification

### 5.1 Backend Tests

```powershell
cd d:\Southern_Ring_Nebula\VitalNet\backend
python test_e2e.py
python test_direct.py
python test_enhanced_classifier.py
```

All must pass. If `test_enhanced_classifier.py` references the legacy model path, update it to reference `enhanced_triage_classifier.pkl`.

### 5.2 ONNX Export Verification

```powershell
cd d:\Southern_Ring_Nebula\VitalNet\backend
python scripts/export_onnx.py
```

Expected output:
- All 5 steps complete without error
- Predicted label for the dummy patient is `0 → ROUTINE`
- ONNX file written to `frontend/public/models/triage_classifier.onnx`

### 5.3 Manual Verification Checklist

| Step | Action | Expected Result |
|---|---|---|
| 1 | `GET /api/health` | `status: ok`, `classifier` shows version and accuracy |
| 2 | Submit a valid case | 200 response — no traceback in body |
| 3 | Submit a case with DB disconnected | 500 response — body is `"An internal server error occurred..."` only |
| 4 | Submit 21 cases in rapid succession | 21st returns HTTP 429 with rate limit message |
| 5 | Disable network, submit a case | ONNX offline triage fires (check browser devtools console for `[VitalNet] ONNX model loaded`) |
| 6 | Doctor dashboard loads | Cases sort EMERGENCY → URGENT → ROUTINE correctly |
| 7 | Check `backend/` root directory | No `train_enhanced_classifier.py` in root |

### 5.4 Final Commit

```powershell
cd d:\Southern_Ring_Nebula\VitalNet
git add backend/
git add frontend/public/models/triage_classifier.onnx
git add frontend/public/models/features_config.json
git commit -m "Improve v1.2: PWA hardening, Zod validation, Service Worker cache, draft persistence"
```

---

## Appendix A — Change Summary

| File | Change | Section |
|---|---|---|
| `backend/main.py` | Remove traceback from 500 response | 1.1 |
| `backend/main.py` | Harden `/api/health` with real classifier state | 1.5 |
| `backend/main.py` | Add per-user `slowapi` rate limiting | 2.2 |
| `backend/main.py` | DB-level sort + composite keyset cursor | 2.1 |
| `backend/main.py` | Paginate `GET /api/cases/mine` | 2.3 |
| `backend/scripts/export_onnx.py` | Full rewrite + `features_config.json` output | 1.2, 1.3 |
| `backend/classifier.py` | Remove dead legacy paths, simplify `load_classifier()` | 1.4 |
| `backend/enhanced_classifier.py` | Remove `ContinualLearningManager` stub | 3.1 |
| `backend/requirements.txt` | Add `slowapi==0.1.9`, `json-repair==0.36.0` | 2.2, 4.3 |
| `backend/scripts/train_enhanced_classifier.py` | **[MOVE]** from backend root | 2.4 |
| `backend/llm.py` | `_parse_llm_json()` + intra-tier retry + prompt crash guard + 15s timeout bump | 4.3, 4.4, 4.7 |
| `backend/prompts/clinical_system_prompt.txt` | Add JSON-only instruction line | 4.3 |
| `frontend/package.json` | Add `zod` dependency | 4.6 |
| `frontend/src/utils/validation.js` | **[NEW]** Hard Zod clinical schema bounds | 4.6 |
| `frontend/src/lib/connectivity.js` | **[NEW]** True server reachability probe | 4.2 |
| `frontend/src/hooks/useDraftSave.js` | **[NEW]** Auto-save form draft to IndexedDB keyed by `client_id` | 4.1 |
| `frontend/src/components/UpdatePrompt.jsx`| **[NEW]** Service Worker cache invalidator UI | 4.8 |
| `frontend/src/pages/IntakeForm.jsx` | Integrate `useDraftSave` and Zod validation | 4.1, 4.6 |
| `frontend/src/App.jsx` | Integrate `<UpdatePrompt />` for PWA | 4.8 |
| `frontend/src/lib/api.js` | Replace `navigator.onLine` with `isServerReachable()` | 4.2 |
| `frontend/src/hooks/useLocalTriage.js` | Add mount-time offline ONNX trigger | 4.2 |
| `frontend/src/lib/offlineQueue.js` | Add inter-item delay for rate safety | 4.5 |
| `frontend/public/models/triage_classifier.onnx` | Regenerated from enhanced model | 1.2 |
| `frontend/public/models/features_config.json` | **[NEW]** Feature order manifest | 1.3 |
| Supabase SQL | Add `triage_priority` computed column + index | 2.1 |

---

## Appendix B — What Must NOT Change

These patterns are correct and are preserved from `REBUILD_INSTRUCTIONS.md`:

| Pattern | Why |
|---|---|
| `briefing["triage_level"] = triage_result["triage_level"]` | Life-safety guardrail — LLM cannot override |
| `briefing["disclaimer"] = FIXED_DISCLAIMER` | Non-removable regulatory requirement |
| `shap==0.51.0` pinned | Python 3.13 + Windows compatibility |
| `temperature=0.1` on all LLM calls | Deterministic clinical output |
| `clientId = uuidv4()` before `navigator.onLine` check | Idempotency guarantee for online + offline |
| `processQueue()` fetches fresh JWT at sync time | Tokens expire — never cache at enqueue time |
| Gemini model names `gemini-2.5-flash` / `gemini-2.5-flash-lite` | Valid API identifiers — confirmed correct |
