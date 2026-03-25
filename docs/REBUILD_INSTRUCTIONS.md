# VitalNet — Comprehensive Rebuild Instructions

> **Version:** 1.1 — March 2026 (peer-reviewed)  
> **Scope:** Full overhaul of the existing Phase 10 codebase, preserving all functionality while fixing structural flaws, closing technical debt, and improving performance, reliability, and offline-first robustness.  
> **Intended reader:** An AI coding agent or developer executing this rebuild from scratch using the existing codebase as a reference. Every change described here is grounded in explicit observations of the actual source files.

> [!NOTE]
> **v1.1 changes:** Five technical amendments applied after peer review — native async Gemini call, `client_id` scope clarification, server-down ONNX fallback, offline queue dead-letter handling, and pagination model corrected to cursor-based. All original changes remain intact.

---

## 0. Pre-Rebuild Checklist

Before writing a single line of code, complete these steps in order.

### 0.1 Read All Context Documents
The following files are mandatory reading. Do not skip.

- `Context/Additionl Context/VitalNet_RnD_Log.md` — Understand the 5-layer product vision and why the current codebase is only the AI Diagnostic Layer slice.
- `Context/Additionl Context/VitalNet_RnD_v4.md` — Master R&D document. Read the guardrail architecture (Q25) and the expert-novice gap resolution (Q34) in full.
- `Context/VitalNet_Status_Briefing_2026-03-23.md` — Current posture, blockers, and open items.
- `Context/test_credentials.md` — Test accounts for ASHA/Doctor/Admin roles.
- `AGENTS.md` — All coding conventions, commands, and agentic behavior rules.

### 0.2 Critical Constraints — Do Not Violate

These are non-negotiable architectural decisions that must be preserved through the rebuild:

1. **Triage independence**: The ML classifier's `triage_level` output MUST NEVER be overridden by the LLM. The line `briefing["triage_level"] = triage_result["triage_level"]` in `llm.py` represents a life-safety guardrail. It must exist in all rebuild variants.
2. **`shap==0.51.0`**: Do NOT change this version. It is pinned for Python 3.13 and Windows compatibility. Upgrading without re-verifying the SHAP round-trip on `triage_classifier.pkl` will break classifier loading at startup.
3. **`scikit-learn>=1.5.2`**: Do not downgrade. Feature engineering in `clinical_features.py` depends on this version.
4. **Non-removable disclaimer**: Every briefing output must include `FIXED_DISCLAIMER` as a non-overridable field. The LLM cannot remove or modify it.
5. **Supabase RLS**: The three-client database model (`supabase_anon`, `get_supabase_for_user()`, `supabase_admin`) must be preserved as-is. Never use `supabase_admin` for case data queries — only for `auth.admin.*` operations.

### 0.3 Environment Variables Required

Both `.env.local` (backend) and `.env.local` (frontend) must be present. The backend `config.py` reads from `.env.local` via `pydantic-settings`.

**Backend `.env.local` (in `/backend/`):**
```
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_JWT_SECRET=
SUPABASE_SERVICE_ROLE_KEY=
GROQ_API_KEY=
GEMINI_API_KEY=          # NEW — add this for the Gemini fallback implementation
FRONTEND_URL=            # e.g. https://vitalnet.vercel.app
```

**Frontend `.env.local` (in `/frontend/`):**
```
VITE_API_BASE_URL=       # e.g. http://localhost:8000
VITE_SUPABASE_URL=
VITE_SUPABASE_ANON_KEY=
```

### 0.4 Verify Baseline Before Changing Anything

Run both services and confirm the current state works before touching any code:

```powershell
# Terminal 1 — Backend
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend
npm install
npm run dev
```

Confirm:
- `GET http://localhost:8000/api/health` returns `{"status":"ok","database":"connected","classifier":"loaded"}`
- Login works with all three test credential roles (from `Context/test_credentials.md`)
- A case submission completes end-to-end (ASHA → classification → briefing → Doctor dashboard)

---

## 1. Backend Rebuild

Work through each section in order. Do not jump ahead.

### 1.1 New Dependency: Google Generative AI

The Gemini fallback described in the R&D document and the `REBUILD_ANALYSIS.md` was never implemented. The `MODELS` list in `llm.py` currently only contains two Groq models. This must be fixed.

**Install the package:**
```powershell
cd backend
pip install google-generativeai>=0.8.0
```

**Update `requirements.txt`** — add this line after `groq`:
```
google-generativeai>=0.8.0
```

### 1.2 Update `config.py` — Add Gemini API Key

**File:** `backend/config.py`

Current state:
```python
class Settings(BaseSettings):
    supabase_url: str
    supabase_anon_key: str
    supabase_jwt_secret: str
    supabase_service_role_key: str
    groq_api_key: str
    model_config = SettingsConfigDict(env_file='.env.local', extra='ignore')
```

Replace with:
```python
class Settings(BaseSettings):
    supabase_url: str
    supabase_anon_key: str
    supabase_jwt_secret: str
    supabase_service_role_key: str
    groq_api_key: str
    gemini_api_key: str = ""   # Optional — fallback tier 2 and 3
    frontend_url: str = ""
    model_config = SettingsConfigDict(env_file='.env.local', extra='ignore')
```

The `gemini_api_key` defaults to empty string so the app starts without it (Gemini becomes inactive, not a crash).

### 1.3 Rebuild `llm.py` — Full Rewrite

This is the highest-impact change. The current `llm.py` has three structural problems:
1. It uses the **synchronous** Groq client inside an `async def` route, blocking the event loop for 2–8 seconds on every submission.
2. The **system prompt is read from disk** on every single LLM call (an open-file syscall per request).
3. The **Gemini fallback is missing** — only two Groq models exist in `MODELS`.

**File:** `backend/llm.py` — complete replacement:

```python
"""
VitalNet LLM Briefing Generator — async, 3-tier fallback
Tier 1: Groq Llama-3.3-70B (primary, ~2s)
Tier 2: Groq Llama-3.1-8B  (on Groq rate limit)
Tier 3: Gemini 2.5 Flash    (on both Groq models exhausted)
Tier 4: Gemini 2.5 Flash-Lite (on Gemini Flash rate limit)
All tiers share the same output schema enforcement.
The triage_level from the ML classifier is locked — no LLM can override it.
"""
import os
import json
import asyncio
from pathlib import Path

import groq
from groq import AsyncGroq  # Use async client — non-blocking event loop

from config import settings

# ─── Module-level constants ──────────────────────────────────────────────────

SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "clinical_system_prompt.txt"

FIXED_DISCLAIMER = (
    "AI-generated clinical briefing for decision support only. "
    "Requires qualified medical examination and physician judgment "
    "before any clinical action."
)

REQUIRED_FIELDS = [
    "triage_level", "primary_risk_driver", "differential_diagnoses",
    "red_flags", "recommended_immediate_actions", "recommended_tests",
    "uncertainty_flags", "disclaimer",
]

LIST_FIELDS = {
    "differential_diagnoses", "red_flags",
    "recommended_immediate_actions", "recommended_tests",
}

# ─── Clients — initialized once at module load ───────────────────────────────

_groq_client: AsyncGroq | None = None
_gemini_configured: bool = False

if settings.groq_api_key:
    _groq_client = AsyncGroq(api_key=settings.groq_api_key)

if settings.gemini_api_key:
    try:
        import google.generativeai as genai
        genai.configure(api_key=settings.gemini_api_key)
        _gemini_configured = True
    except ImportError:
        print("[WARN] google-generativeai not installed — Gemini fallback disabled")

# ─── System prompt — cached at module load, never re-read from disk ──────────

_SYSTEM_PROMPT: str = SYSTEM_PROMPT_PATH.read_text(encoding="utf-8")


# ─── Patient context builder ──────────────────────────────────────────────────

def _build_patient_context(form_data: dict, triage_result: dict) -> str:
    def fmt(val, unit=""):
        return f"{val}{unit}" if val is not None and val != -1 else "Not recorded"

    symptoms = form_data.get("symptoms", [])
    symptoms_str = ", ".join(symptoms) if symptoms else "None reported"

    return f"""PATIENT CONTEXT:
- Age: {form_data.get('patient_age')} years
- Sex: {form_data.get('patient_sex')}
- Location: {form_data.get('location')}
- Chief Complaint: {form_data.get('chief_complaint')}
- Duration: {form_data.get('complaint_duration')}
- BP: {fmt(form_data.get('bp_systolic'))}/{fmt(form_data.get('bp_diastolic'))} mmHg
- SpO2: {fmt(form_data.get('spo2'), '%')}
- Heart Rate: {fmt(form_data.get('heart_rate'), ' bpm')}
- Temperature: {fmt(form_data.get('temperature'), '°C')}
- Symptoms reported: {symptoms_str}
- ASHA observations: {form_data.get('observations') or 'None recorded'}
- Known conditions: {form_data.get('known_conditions') or 'None reported'}
- Current medications: {form_data.get('current_medications') or 'None reported'}

TRIAGE CLASSIFICATION (from ML classifier — locked, do not override):
Level: {triage_result['triage_level']}
Confidence: {triage_result['confidence_score']:.2f}
Primary signal: {triage_result['risk_driver']}"""


# ─── Schema enforcement ───────────────────────────────────────────────────────

def _enforce_schema(briefing: dict, triage_result: dict) -> dict:
    """
    Hard-lock the triage level and disclaimer, ensure all required fields exist.
    This runs on every LLM output regardless of which tier produced it.
    """
    briefing["triage_level"] = triage_result["triage_level"]  # SAFETY: LLM cannot override
    briefing["disclaimer"] = FIXED_DISCLAIMER
    for field in REQUIRED_FIELDS:
        if field not in briefing:
            briefing[field] = [] if field in LIST_FIELDS else "Not available"
    return briefing


# ─── Groq async call ─────────────────────────────────────────────────────────

async def _call_groq(model: str, patient_context: str) -> dict:
    """Attempt one Groq model call. Raises on failure — caller handles retry."""
    response = await _groq_client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": patient_context},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
        max_tokens=1000,
        timeout=8,
    )
    return json.loads(response.choices[0].message.content)


# ─── Gemini async call ────────────────────────────────────────────────────────

async def _call_gemini(model_name: str, patient_context: str) -> dict:
    """
    Attempt a Gemini model call using the native async API.
    Uses generate_content_async() — NOT asyncio.to_thread().
    The google-generativeai SDK natively supports async; wrapping with
    asyncio.to_thread() would waste a thread pool worker unnecessarily.
    Raises on failure — caller handles retry.
    """
    import google.generativeai as genai
    model = genai.GenerativeModel(
        model_name=model_name,
        system_instruction=_SYSTEM_PROMPT,
        generation_config=genai.GenerationConfig(
            response_mime_type="application/json",
            temperature=0.1,
            max_output_tokens=1000,
        ),
    )
    # Use native async method — avoids thread pool overhead
    response = await model.generate_content_async(patient_context)
    return json.loads(response.text)


# ─── Main entry point — fully async ─────────────────────────────────────────

async def generate_briefing(form_data: dict, triage_result: dict) -> dict:
    """
    Generate a clinical briefing using the 4-tier fallback chain.
    Never raises — always returns a usable briefing dict.
    Triage level from classifier is enforced on every output path.
    """
    if not _groq_client and not _gemini_configured:
        print("⚠ No LLM API keys configured — returning fallback briefing.")
        return _fallback_briefing(triage_result)

    patient_context = _build_patient_context(form_data, triage_result)

    # ── Tier 1 & 2: Groq models ───────────────────────────────────────────────
    if _groq_client:
        for model in ["llama-3.3-70b-versatile", "llama-3.1-8b-instant"]:
            try:
                briefing = await _call_groq(model, patient_context)
                print(f"✓ Briefing generated via Groq/{model}")
                return _enforce_schema(briefing, triage_result)
            except groq.RateLimitError:
                print(f"Rate limit on Groq/{model} — trying next tier")
                await asyncio.sleep(0.5)   # Brief pause before next attempt
                continue
            except (groq.APIConnectionError, groq.InternalServerError):
                print(f"Connection/server error on Groq/{model} — trying next tier")
                continue
            except json.JSONDecodeError:
                print(f"JSON parse error on Groq/{model} — trying next tier")
                continue
            except Exception as e:
                print(f"Unexpected error on Groq/{model}: {e} — trying next tier")
                continue

    # ── Tier 3 & 4: Gemini models ─────────────────────────────────────────────
    if _gemini_configured:
        for model in ["gemini-2.5-flash", "gemini-2.5-flash-lite"]:
            try:
                briefing = await _call_gemini(model, patient_context)
                print(f"✓ Briefing generated via Gemini/{model}")
                return _enforce_schema(briefing, triage_result)
            except json.JSONDecodeError:
                print(f"JSON parse error on Gemini/{model} — trying next tier")
                continue
            except Exception as e:
                # Catches Gemini quota errors, connection errors, etc.
                print(f"Error on Gemini/{model}: {e} — trying next tier")
                await asyncio.sleep(0.5)
                continue

    # ── All tiers exhausted ───────────────────────────────────────────────────
    print("⚠ All LLM tiers exhausted — returning fallback briefing. Triage badge intact.")
    return _fallback_briefing(triage_result)


# ─── Fallback briefing ────────────────────────────────────────────────────────

def _fallback_briefing(triage_result: dict) -> dict:
    return {
        "triage_level":                 triage_result["triage_level"],
        "primary_risk_driver":          triage_result["risk_driver"],
        "differential_diagnoses":       ["LLM briefing unavailable — triage from ML classifier is intact"],
        "red_flags":                    [],
        "recommended_immediate_actions":["Refer patient to PHC doctor for in-person evaluation"],
        "recommended_tests":            [],
        "uncertainty_flags":            "LLM briefing could not be generated. Triage level and risk driver from ML classifier remain valid.",
        "disclaimer":                   FIXED_DISCLAIMER,
        "_model_used":                  "fallback",
    }
```

### 1.4 Update `main.py` — Async Pipeline + Schema Fixes

**File:** `backend/main.py`

Apply all of the following changes. They are non-contiguous edits — read carefully.

#### 1.4.1 — Add `asyncio` import and update `generate_briefing` call

At the top of `main.py`, the `generate_briefing` import stays the same. Because `generate_briefing` is now `async`, it must be `await`ed.

**Change the submit route body from:**
```python
# Step 2: LLM briefing (may fail gracefully)
briefing = generate_briefing(form_data, triage_result)
```
**To:**
```python
# Step 2: LLM briefing — async, non-blocking (may fail gracefully)
briefing = await generate_briefing(form_data, triage_result)
```

#### 1.4.2 — Add `created_offline` field to the insert record

In the `submit_case` route, the record dict currently hardcodes `"created_offline": False`. This means analytics can never distinguish offline submissions from online ones.

**Change:**
```python
"created_offline": False,
```
**To:**
```python
"created_offline": form.created_offline,
```

This reads the flag from the form payload (which the client sends as `true` when syncing from the offline queue).

#### 1.4.3 — Make the UPSERT idempotent on `client_id`

The current `insert` can create duplicate records if the background sync fires twice for the same queued item (possible on flaky connections).

**Change:**
```python
result = db.table("case_records").insert(record).execute()
```
**To:**
```python
result = (
    db.table("case_records")
    .upsert(record, on_conflict="client_id", ignore_duplicates=True)
    .execute()
)
```

This requires the `client_id` column to have a `UNIQUE` constraint in Supabase (see Section 2.2).

#### 1.4.4 — Replace the raw header split with `HTTPBearer` in auth

Every route currently does `authorization.split(" ", 1)[1]` manually, which crashes with an unhandled `AttributeError` if the header is missing or malformed.

In `auth.py`, the `get_current_user` dependency already validates the Bearer prefix (`if not authorization or not authorization.startswith('Bearer '):`), so the split in `main.py` routes is safe given auth runs first. However, the explicit token extraction in the route body can be made more defensive.

**Change every occurrence of:**
```python
raw_token = authorization.split(" ", 1)[1]
```
**To:**
```python
raw_token = (authorization or "").split(" ", 1)[-1]
```

This guarantees no `IndexError` even if auth somehow passes through without the header being set.

### 1.5 Update `schemas.py` — Add `created_offline` Field

**File:** `backend/schemas.py`

Add the missing field to `IntakeForm`:

```python
# Add to IntakeForm class, after client_submitted_at:
created_offline: bool = False
```

The complete updated `IntakeForm` class:
```python
class IntakeForm(BaseModel):
    patient_name: str = Field(min_length=1, max_length=100)
    patient_age: int = Field(ge=0, le=120)
    patient_sex: str
    chief_complaint: str
    complaint_duration: str
    location: str

    bp_systolic: Optional[int] = Field(None, ge=30, le=300)
    bp_diastolic: Optional[int] = Field(None, ge=10, le=200)
    spo2: Optional[int] = Field(None, ge=50, le=100)
    heart_rate: Optional[int] = Field(None, ge=10, le=250)
    temperature: Optional[float] = Field(None, ge=25.0, le=45.0)

    symptoms: List[str] = []
    observations: Optional[str] = Field(None, max_length=500)
    known_conditions: Optional[str] = None
    current_medications: Optional[str] = None

    # Offline sync metadata
    client_id: Optional[uuid.UUID] = None
    client_submitted_at: Optional[datetime] = None
    created_offline: bool = False   # NEW — True when submitted via offline queue sync
```

### 1.6 Clean Up Dead Classifier Files

The following files are dead code — `classifier.py` supersedes them all and is the only file imported anywhere. Delete them:

```powershell
cd backend
Remove-Item classifier_original.py
Remove-Item classifier_v2.py
```

**Do NOT delete:**
- `classifier.py` — currently active
- `enhanced_classifier.py` — imported by `classifier.py` for the enhanced model path
- `clinical_features.py` — imported by `classifier.py` for feature engineering

After deleting, create `CLASSIFIER_CHANGELOG.md` in `/backend/` documenting the evolution:

```markdown
# Classifier Evolution

| Version | File | Notes |
|---|---|---|
| v1.0 | `classifier_original.py` (deleted) | Original Phase 1, basic vitals features |
| v2.0 | `classifier_v2.py` (deleted) | Second iteration, improved recall |
| v3.0 (legacy) | `classifier.py` → `_predict_legacy()` | 45-feature pipeline via `ClinicalFeatureEngineer` |
| v4.0 (enhanced) | `enhanced_classifier.py` | Multi-stage classifier, auto-loaded if `enhanced_triage_classifier.pkl` exists |
```

### 1.7 Remove the Orphaned `_safe_vital()` Function

**File:** `backend/classifier.py`

Lines 314–318 contain `_safe_vital()` which is never called within the file. Remove it:

```python
# DELETE these lines (314–318):
def _safe_vital(val):
    """Return the value if valid, -1 if missing or sentinel."""
    if val is None or val == -1:
        return -1
    return val
```

### 1.8 Add SHAP Computation Improvement (Risk Driver Caching)

**File:** `backend/classifier.py`

The legacy path currently calls `_explainer.shap_values()` on every inference request. SHAP `TreeExplainer` computation is expensive (~50–200ms). Since the enhanced classifier is preferred and generates risk drivers via the cheaper `_generate_risk_explanation()` path, add a note and guard:

In `_get_legacy_risk_driver()`, add an explanation-only mode that skips SHAP if the explainer is very slow:
```python
def _get_legacy_risk_driver(features: np.ndarray, triage_level: str) -> str:
    """
    SHAP-based risk driver explanation for legacy classifier.
    NOTE: SHAP computation runs on every legacy inference. If latency is a concern,
    migrate to the enhanced classifier which uses a cheaper rule-based explanation.
    """
    # ... existing implementation unchanged ...
```

No functional change — just a documented note. The real fix is using the enhanced classifier (which already avoids per-request SHAP).

### 1.9 Backend Verification

After completing all backend changes, run the verification sequence:

```powershell
cd backend
# 1. Lint check
ruff check .
# 2. Start server
python -m uvicorn main:app --reload --port 8000
# 3. In a second terminal — run E2E tests
python test_e2e.py
# 4. Run direct classifier test
python test_direct.py
```

Expected outcomes:
- `ruff check .` — zero errors
- `GET /api/health` — `{"status":"ok","database":"connected","classifier":"loaded"}`
- `test_e2e.py` — all tests pass
- LLM briefing generation logs show `✓ Briefing generated via Groq/llama-3.3-70b-versatile` (or lower tier if rate limited)

---

## 2. Database (Supabase) Changes

These changes are performed in the **Supabase SQL Editor** in the project dashboard. Navigate to the SQL Editor and run each statement separately.

### 2.1 Add `created_offline` Column

The column must be added to `case_records` to store the flag from Section 1.5:

```sql
ALTER TABLE case_records
ADD COLUMN IF NOT EXISTS created_offline BOOLEAN NOT NULL DEFAULT FALSE;
```

### 2.2 Add UNIQUE Constraint on `client_id`

This enables the idempotent upsert from Section 1.4.3. Without this constraint, the `on_conflict="client_id"` in the upsert will fail silently and revert to a regular insert.

> [!NOTE]
> **`client_id` is already generated for ALL submissions — both online and offline.** In `api.js`, `clientId = uuidv4()` is called at line 18, before the `navigator.onLine` check. Every submission (online or queued) carries a UUID. The UNIQUE constraint is therefore safe to add immediately with no risk of breaking online inserts. PostgreSQL allows multiple NULLs in a UNIQUE column by default, so any legacy rows with `NULL` client_id (from before this change) will not conflict.

```sql
ALTER TABLE case_records
ADD CONSTRAINT case_records_client_id_unique UNIQUE (client_id);
```

**Safety check — run this first and resolve any duplicates before applying the constraint:**
```sql
SELECT client_id, COUNT(*) FROM case_records
WHERE client_id IS NOT NULL
GROUP BY client_id HAVING COUNT(*) > 1;
```

### 2.3 Add Performance Indexes

These indexes are critical for production-scale query performance. Without them, the doctor dashboard query (`WHERE deleted_at IS NULL ORDER BY created_at DESC`) becomes a full table scan as data grows.

```sql
-- Doctor dashboard: most common query pattern
CREATE INDEX IF NOT EXISTS idx_case_records_active_created
ON case_records (deleted_at, created_at DESC)
WHERE deleted_at IS NULL;

-- ASHA panel: submissions by user
CREATE INDEX IF NOT EXISTS idx_case_records_submitted_by
ON case_records (submitted_by, deleted_at);

-- Analytics: triage level distribution queries
CREATE INDEX IF NOT EXISTS idx_case_records_triage_level
ON case_records (triage_level)
WHERE deleted_at IS NULL;

-- Facility-scoped queries (Doctor and Admin panel filters)
CREATE INDEX IF NOT EXISTS idx_case_records_facility
ON case_records (facility_id, created_at DESC)
WHERE deleted_at IS NULL;
```

### 2.4 Verify RLS Policies Are Intact

After all DDL changes, confirm no RLS policies were inadvertently dropped:

```sql
SELECT tablename, policyname, permissive, roles, cmd
FROM pg_policies
WHERE tablename = 'case_records'
ORDER BY policyname;
```

Expected: at minimum policies for `SELECT` (doctor/admin), `INSERT` (asha_worker/admin), `UPDATE` (doctor/admin for review).

---

## 3. Frontend Rebuild

### 3.1 Fix Role Source — Read From JWT, Not Profile Fetch

**File:** `frontend/src/store/authStore.jsx`

**Problem:** The current implementation sets `role: profile?.role ?? null`. If `fetchProfile()` fails offline (catches and warns silently), the user's role is `null` and they cannot access their panel. This is the most impactful frontend reliability bug.

**The fix:** Supabase stores the role in `session.user.app_metadata.role` (confirmed present — `auth.py` already checks `app_metadata.role` on the backend). Read it from there first, falling back to the profile table as secondary.

Find this line in the `value` object:
```js
role: profile?.role ?? null,
```
Replace with:
```js
role: session?.user?.app_metadata?.role ?? profile?.role ?? null,
```

This means role-based access control works **immediately on login** without waiting for the `fetchProfile()` DB call, and **survives offline** because the role is embedded in the JWT.

### 3.2 Fix `created_offline` Flag + Harden `processQueue` Dead-Letter Handling

#### 3.2.1 — `offlineQueue.js`: No changes needed

**File:** `frontend/src/lib/offlineQueue.js`

The `enqueue` function stores the payload as-is. No changes needed here — the `created_offline: true` flag will be included in the payload if the caller adds it.

#### 3.2.2 — `api.js`: Set `created_offline: true` and fix head-of-line blocking

**File:** `frontend/src/lib/api.js`

**Fix 1 — `created_offline` flag:** The offline path currently passes `payload` directly to `enqueue` without the flag set.

**Fix 2 (peer review) — Head-of-line blocking in `processQueue`:** The current implementation handles `409` (conflict/duplicate) and `422` (schema validation error) by dequeuing, which is correct. However, any other `4xx` status (e.g., `400 Bad Request` from a malformed payload caused by a schema migration) falls into the final `else` branch and is left in the queue for infinite retry. A single permanently-invalid item at the front of the queue blocks all subsequent items from syncing.

**Full updated `submitCase()` offline path:**
```js
if (!navigator.onLine) {
    const offlinePayload = { ...payload, created_offline: true }
    await enqueue(clientId, offlinePayload)
    // Signal useLocalTriage to begin ONNX warmup (see Section 3.3)
    window.dispatchEvent(new CustomEvent('vitalnet-server-unreachable'))
    return { queued: true, client_id: clientId }
}
```

**Full updated `processQueue()` — replace the status branching block:**
```js
if (res.ok) {
    await dequeue(item.client_id)
    synced++
} else if (res.status === 409) {
    // Conflict = already inserted (idempotent duplicate) — safe to dequeue
    await dequeue(item.client_id)
    synced++
} else if (res.status >= 400 && res.status < 500) {
    // Any 4xx = permanent client error — this payload will NEVER succeed.
    // Dequeue immediately to unblock subsequent queue items.
    // This covers 422 (schema mismatch), 400 (bad request), 403 (auth expired), etc.
    console.warn(
        '[VitalNet] Permanent error — dequeuing case to prevent head-of-line blocking.',
        item.client_id, res.status, await res.text()
    )
    await dequeue(item.client_id)
    failed++
} else {
    // 5xx = transient server error — leave in queue for next sync attempt
    failed++
}
```

This replaces the previous specific `res.status === 422` check with a general `4xx` guard that catches all permanent client errors. The comment documents the intent clearly for future maintainers.

### 3.3 Fix ONNX Model — Lazy Load on Offline Detection + Server-Down Fallback

**File:** `frontend/src/hooks/useLocalTriage.js`

**Problem 1:** `warmupModel()` was called unconditionally on mount, loading ~3MB even when server-side inference is available.

**Problem 2 (peer review):** `navigator.onLine === true` only means the device has network access — it does NOT mean the FastAPI backend is reachable. If the server is down (502 Bad Gateway, deployment restart, etc.), the ONNX model won't be loaded because the browser thinks it's online. The ASHA worker gets no local triage fallback during server outages.

**Fix:** Expose a `triggerWarmup()` function from the hook that `api.js` can call when a server-down error is detected. Also load preemptively on the browser `offline` event.

```js
import { useState, useEffect, useCallback } from 'react'
import { warmupModel, runTriage } from '../utils/triageClassifier'

export function useLocalTriage() {
  const [modelReady, setModelReady] = useState(false)
  const [modelError, setModelError] = useState(null)

  // Shared warmup function — can be called internally or externally
  const triggerWarmup = useCallback(() => {
    if (modelReady) return  // Already loaded — skip
    warmupModel()
      .then(() => setModelReady(true))
      .catch((err) => {
        console.warn('[VitalNet] ONNX warmup failed:', err)
        setModelError(err.message)
        // Non-fatal — form still works, local triage just unavailable
      })
  }, [modelReady])

  useEffect(() => {
    // Load immediately if already offline at mount time
    if (!navigator.onLine) triggerWarmup()

    // Preemptively load when the browser detects loss of network
    window.addEventListener('offline', triggerWarmup)
    return () => window.removeEventListener('offline', triggerWarmup)
  }, [triggerWarmup])

  const classify = useCallback(
    async (formData) => {
      if (!modelReady) return null
      try {
        return await runTriage(formData)
      } catch (err) {
        console.warn('[VitalNet] Local triage failed:', err)
        return null
      }
    },
    [modelReady]
  )

  return { modelReady, modelError, classify, triggerWarmup }
}
```

**Update `api.js` — trigger warmup on server-down errors:**

The `submitCase()` function in `api.js` already catches `TypeError` (network failure) and queues the submission. It also catches 5xx server errors and rethrows them. We need it to also signal the hook to begin ONNX warmup in both cases, so local triage is ready for the user's next submission attempt.

Because `api.js` is not a React component (it cannot call hooks), use a **module-level event bus** — dispatch a `CustomEvent` that `useLocalTriage` listens for:

```js
// In api.js submitCase() — add to the offline enqueue path:
if (!navigator.onLine) {
    const offlinePayload = { ...payload, created_offline: true }
    await enqueue(clientId, offlinePayload)
    // Signal to any mounted useLocalTriage hook to begin ONNX warmup
    window.dispatchEvent(new CustomEvent('vitalnet-server-unreachable'))
    return { queued: true, client_id: clientId }
}

// Also in the catch block for TypeError (network error while online):
} catch (err) {
    if (err instanceof TypeError) {
        await enqueue(clientId, { ...payload, created_offline: true })
        // Server appeared online but connection failed — trigger ONNX warmup
        window.dispatchEvent(new CustomEvent('vitalnet-server-unreachable'))
        return { queued: true, client_id: clientId }
    }
    throw err
}
```

**Update `useLocalTriage.js` to listen for the event:**

```js
useEffect(() => {
    if (!navigator.onLine) triggerWarmup()

    window.addEventListener('offline', triggerWarmup)
    // Also warm up if server becomes unreachable while browser is online
    window.addEventListener('vitalnet-server-unreachable', triggerWarmup)
    return () => {
      window.removeEventListener('offline', triggerWarmup)
      window.removeEventListener('vitalnet-server-unreachable', triggerWarmup)
    }
}, [triggerWarmup])
```

**Behavioral result:** ONNX model is never loaded during normal online operation. It begins loading the moment the browser goes offline OR the server becomes unreachable (even with network available), ensuring local triage is ready before the next submission attempt.

### 3.4 Add Queue Size Cap to `offlineQueue.js`

**File:** `frontend/src/lib/offlineQueue.js`

Add a guard in `enqueue` to prevent unbounded IndexedDB growth on low-memory devices:

```js
const MAX_QUEUE_SIZE = 50

export async function enqueue(clientId, payload) {
  const db = await getQueueDB()
  
  // Guard: refuse to queue if at capacity
  const count = await db.count(STORE_NAME)
  if (count >= MAX_QUEUE_SIZE) {
    console.warn(`[VitalNet] Offline queue is full (${MAX_QUEUE_SIZE} items). Cannot queue more.`)
    throw new Error(`Offline queue is full (${MAX_QUEUE_SIZE} items). Please sync before submitting more cases.`)
  }

  await db.put(STORE_NAME, {
    client_id:  clientId,
    payload,
    queued_at:  new Date().toISOString(),
  })
  notifyQueueChange()
}
```

**Update `IntakeForm.jsx`** to handle this error gracefully. In the `handleSubmit` catch block, check for the specific queue-full message:
```js
} catch (err) {
  if (err.message?.includes('queue is full')) {
    setError('Offline queue is full (50 cases). Connect to internet to sync before submitting more cases.')
  } else {
    setError(err.message || "Submission failed. Check connection.")
  }
}
```

### 3.5 Frontend Verification

```powershell
cd frontend
npm run dev
```

Manual verification checklist:
- [ ] ASHA login — role is read immediately (no loading flicker)
- [ ] Doctor login — role is read immediately
- [ ] Submit a case online — `✓ Briefing generated via Groq/...` in backend logs
- [ ] Disable network (browser DevTools → Network → Offline) — submit a case → "Saved offline" card appears with local triage badge
- [ ] Re-enable network — OfflineBanner shows syncing, then clears
- [ ] In browser DevTools, confirm ONNX model fetch does NOT occur when online
- [ ] Check browser DevTools → Application → IndexedDB → `vitalnet_offline` → `submission_queue` — verify `created_offline: true` is stored in the offline payload

---

## 4. Additional Improvements (Lower Priority, Do After Core Rebuild)

These improvements are valuable but not blockers. Complete them after verifying all core rebuild steps pass.

### 4.1 Split `GET /api/cases` Into List + Detail Endpoints

**Problem:** Every call to `GET /api/cases` returns the full `briefing` JSONB blob for every case, even though the priority queue list view only needs triage level, patient name, and timestamps. This is ~60% unnecessary payload.

**Backend — add a detail endpoint to `main.py`:**
```python
@app.get("/api/cases/{case_id}")
async def get_case_detail(
    case_id: str,
    authorization: str = Header(None),
    user: dict = Depends(require_role("doctor", "admin")),
):
    """Returns the full record including briefing JSONB for one case."""
    raw_token = (authorization or "").split(" ", 1)[-1]
    db = get_supabase_for_user(raw_token)
    result = (
        db.table("case_records")
        .select("*")
        .eq("id", case_id)
        .is_("deleted_at", "null")
        .single()
        .execute()
    )
    return result.data
```

**Modify `GET /api/cases`** to return only the list columns:
```python
result = (
    db.table("case_records")
    .select("id, patient_name, patient_age, patient_sex, triage_level, triage_confidence, risk_driver, created_at, reviewed_at, reviewed_by, facility_id, created_offline")
    .is_("deleted_at", "null")
    .order("created_at", desc=True)
    .execute()
)
```

**Frontend — update `DoctorPanel.jsx`** to fetch individual briefings on card expansion, not on initial load.

### 4.2 Implement DB-Level Sorting for `/api/cases`

**Problem:** Sorting is done in Python after fetching all records from the database, which prevents efficient pagination.

**Fix:** Add a stored computed column for sort priority in Supabase:

```sql
ALTER TABLE case_records ADD COLUMN triage_priority INTEGER
GENERATED ALWAYS AS (
    CASE triage_level
        WHEN 'EMERGENCY' THEN 0
        WHEN 'URGENT'    THEN 1
        WHEN 'ROUTINE'   THEN 2
        ELSE 3
    END
) STORED;
```

In `main.py`, replace the Python `cases.sort(...)` call with DB-level ordering and remove the sort block entirely:

```python
.order("triage_priority", desc=False)
.order("created_at", desc=True)
```

### 4.3 Add Pagination — Cursor-Based "Load More" Only

> [!WARNING]
> **Do NOT implement offset-based pagination (`LIMIT x OFFSET y`) for the Doctor Dashboard.**
>
> **Reason (peer review):** `Dashboard.jsx` holds all cases in local React `useState([])` and uses Supabase Realtime subscriptions (`useRealtimeCases`) to splice new inserts into the local array in real time. If you add offset-based pagination, a Realtime `INSERT` event (new EMERGENCY case at position 0) shifts every item's offset position server-side — the client's page 1 now overlaps with what was page 2, causing duplicates and missed items with no clean reconciliation path.

**Correct approach — cursor-based "load more":**

All cases are retained in local state once loaded. Additional cases are fetched using the `created_at` of the last-loaded item as a cursor (not an offset integer). Realtime inserts are prepended/sorted into the existing array at position 0, unaffected by the cursor.

**Backend — add `before` cursor parameter to `GET /api/cases`:**

```python
@app.get("/api/cases")
async def get_cases(
    authorization: str = Header(None),
    user: dict = Depends(require_role("doctor", "admin")),
    limit: int = 50,
    before: str | None = None,   # ISO timestamp cursor — load cases older than this
):
    raw_token = (authorization or "").split(" ", 1)[-1]
    db = get_supabase_for_user(raw_token)
    query = (
        db.table("case_records")
        .select("id, patient_name, patient_age, patient_sex, triage_level, triage_priority, triage_confidence, risk_driver, created_at, reviewed_at, facility_id, created_offline")
        .is_("deleted_at", "null")
        .order("triage_priority", desc=False)
        .order("created_at", desc=True)
        .limit(limit)
    )
    if before:
        query = query.lt("created_at", before)  # "older than cursor" pagination
    result = query.execute()
    return result.data
```

**Frontend — `Dashboard.jsx` integration pattern:**

- Initial fetch: `GET /api/cases` (no cursor) — returns newest 50
- "Load More" button: `GET /api/cases?before={oldest_local_created_at}` — appends to `cases` state
- Realtime inserts: prepend directly to `cases` state, no cursor interaction
- Realtime updates: in-place update by `id`, no cursor interaction

This keeps Supabase Realtime subscriptions and pagination fully compatible.

### 4.4 Commit Untracked Critical Files

The following files are not tracked by git and must be committed:

```powershell
cd d:\Southern_Ring_Nebula\VitalNet
git add "Context/Additionl Context/"
git add "Context/VitalNet_Status_Briefing_2026-03-23.md"
git add REBUILD_INSTRUCTIONS.md
git add backend/CLASSIFIER_CHANGELOG.md
git commit -m "Add: untracked context documents and rebuild instructions"
```

### 4.5 Update `VitalNet_RnD_v4.md` Outdated Sections

The master R&D document still references SQLite and marks Doctor Authentication as "ROADMAP". These must be updated:

**In Section 5.2 (Database):** Replace all references to SQLite with Supabase PostgreSQL.

**In Section 6.1:** Change `Doctor Authentication: ROADMAP` to `Doctor Authentication: COMPLETE — Supabase JWT + RLS, Phase 7`.

**In Section 6.3:** Update classifier section to reflect the 45-feature enhanced pipeline and ONNX browser export.

---

## 5. Rebuild Completion Verification

Run through this checklist end-to-end before marking the rebuild complete.

### 5.1 Backend Integration Tests

```powershell
cd backend
python test_e2e.py
python test_direct.py
python test_enhanced_classifier.py
```

All must pass with zero failures.

### 5.2 Manual End-to-End Flow

| Step | Action | Expected Result |
|---|---|---|
| 1 | Login as `asha_worker` | Role detected immediately from JWT, ASHA Panel loads |
| 2 | Submit a complete case online | Backend logs `✓ Briefing generated via Groq/...` |
| 3 | Submit case while offline (DevTools Offline mode) | "Saved Offline" card + local ONNX triage badge |
| 4 | Go back online | OfflineBanner shows sync progress then clears |
| 5 | Verify the synced record in Supabase | `created_offline = true` on the row |
| 6 | Login as `doctor` | Doctor Panel shows cases sorted by triage priority |
| 7 | Click "Review" on a case | Reviewed timestamp appears; Realtime UPDATE fires |
| 8 | Login as `admin` | Admin Panel shows analytics and user management |
| 9 | Submit same `client_id` twice | Second insert silently ignored (upsert idempotency) |
| 10 | Kill Groq API key, restart, submit | Gemini fallback activates; logs show `✓ Briefing generated via Gemini/...` |
| 11 | Kill all API keys, restart, submit | Fallback briefing returned; triage badge still correct |
| 12 | Stop uvicorn while online, submit | `vitalnet-server-unreachable` fires; ONNX loads; local triage shown |
| 13 | Enqueue 50 offline cases | 51st submission shows "queue is full" error message |
| 14 | Force a `400 Bad Request` in processQueue | Case is dead-lettered; remaining queue items continue syncing |

### 5.3 Final Git Commit

```powershell
cd d:\Southern_Ring_Nebula\VitalNet
git add backend/
git add frontend/src/
git add REBUILD_INSTRUCTIONS.md
git commit -m "Rebuild v1.1: async LLM, 4-tier Gemini fallback, server-down ONNX, queue dead-letter, cursor pagination"
```

---

## Appendix A — File Change Summary

| File | Change Type | Section |
|---|---|---|
| `backend/config.py` | Add `gemini_api_key`, `frontend_url` fields | 1.2 |
| `backend/requirements.txt` | Add `google-generativeai>=0.8.0` | 1.1 |
| `backend/llm.py` | Full rewrite — async, 4-tier fallback, `generate_content_async` | 1.3 |
| `backend/main.py` | `await generate_briefing()`, upsert on `client_id`, `created_offline`, cursor param | 1.4, 4.3 |
| `backend/schemas.py` | Add `created_offline: bool = False` | 1.5 |
| `backend/classifier.py` | Remove orphaned `_safe_vital()` | 1.7 |
| `backend/classifier_original.py` | **Delete** | 1.6 |
| `backend/classifier_v2.py` | **Delete** | 1.6 |
| `backend/CLASSIFIER_CHANGELOG.md` | **Create** | 1.6 |
| Supabase SQL | `created_offline` column, UNIQUE constraint, 4 indexes, `triage_priority` computed column | 2.1–2.3, 4.2 |
| `frontend/src/store/authStore.jsx` | Role from JWT `app_metadata` (offline-safe) | 3.1 |
| `frontend/src/lib/api.js` | `created_offline: true`, `vitalnet-server-unreachable` event, 4xx dead-letter in `processQueue` | 3.2, 3.3 |
| `frontend/src/hooks/useLocalTriage.js` | Lazy ONNX, server-down event listener, `triggerWarmup` export | 3.3 |
| `frontend/src/lib/offlineQueue.js` | 50-item queue size cap | 3.4 |
| `frontend/src/pages/IntakeForm.jsx` | Queue-full error message | 3.4 |

---

## Appendix B — Design Decisions Locked (Do Not Change)

These patterns are architecturally correct and must survive the rebuild unchanged:

| Pattern | Location | Why |
|---|---|---|
| `briefing["triage_level"] = triage_result["triage_level"]` | `llm.py` | **Life-safety guardrail** — LLM cannot override classifier |
| `briefing["disclaimer"] = FIXED_DISCLAIMER` | `llm.py` | Regulatory/ethical requirement — non-removable |
| `supabase_admin` restricted to `auth.admin.*` only | `database.py` | Security — never touches case data |
| Three-client database model (anon/user/admin) | `database.py` | Per-request RLS enforcement |
| `shap==0.51.0` pinned version | `requirements.txt` | Python 3.13 + Windows compatibility |
| `_fallback_briefing()` always-returns | `llm.py` | ASHA worker always gets a response |
| `require_role()` dependency pattern | `auth.py` | FastAPI idiomatic, role check before any data access |
| `processQueue()` fetches fresh token at sync time | `api.js` | Tokens expire — never cache at enqueue time |
| `temperature=0.1` on all LLM calls | `llm.py` | Deterministic clinical output — do not raise |
| `clientId = uuidv4()` before `navigator.onLine` check | `api.js` | Every submission tracked — enables idempotency for both online and offline |

---

## Appendix C — Peer Review Amendment Log (v1.0 → v1.1)

| # | Concern Raised | Analysis | Verdict | Section Updated |
|---|---|---|---|---|
| 1 | `asyncio.to_thread()` wrapping Gemini SDK when native async exists | The `google-generativeai` SDK exposes `generate_content_async()` natively. Using `asyncio.to_thread` was unnecessary thread pool overhead. | ✅ Accepted — replaced with `generate_content_async()` | 1.3 |
| 2 | `client_id` only generated for offline submissions, breaking UNIQUE constraint | **The concern was already solved by the existing codebase.** `api.js` line 18 generates `clientId = uuidv4()` before the `navigator.onLine` check — every submission carries a UUID. No code change needed; clarification added. | ⚠️ Clarified — no change required | 2.2 |
| 3 | `navigator.onLine` does not detect server-down (502/503) | Correct: `navigator.onLine` reports network reachability, not backend availability. Added `vitalnet-server-unreachable` CustomEvent bus so `api.js` can signal `useLocalTriage` to begin ONNX warmup when a `TypeError` or server-down condition occurs. | ✅ Accepted — `triggerWarmup` export and event listener added | 3.3 |
| 4 | `processQueue` leaves non-422 `4xx` errors in queue (head-of-line blocking) | The existing code correctly handled `409` and `422`, but any other `4xx` (e.g., `400 Bad Request` from a schema migration) fell into the `else` branch and was never dequeued. Replaced the specific `422` check with a general `status >= 400 && status < 500` dead-letter guard. | ✅ Accepted — `processQueue` 4xx guard strengthened | 3.2 |
| 5 | Offset pagination incompatible with Supabase Realtime insert splicing | Reviewing `Dashboard.jsx` confirmed it holds all cases in local state and Realtime events splice into that array. Offset pagination would cause duplicate/missing items on Realtime inserts because server-side offsets shift. Changed to cursor-based "load more" using `created_at` as the cursor. Offset pagination explicitly prohibited in a warning block. | ✅ Accepted — cursor-based pagination documented; offset approach warned against | 4.3 |


