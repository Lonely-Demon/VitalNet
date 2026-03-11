# VitalNet — Developer Context Document
## For AI Coding Agents (Google Antigravity, Claude Code, Gemini CLI, etc.)
### Constrained to Development-Relevant Information Only

---

> **How to use this document**
> This is the single source of truth for building VitalNet. Read it completely before writing a single line of code. Every architecture decision, technology choice, and constraint documented here was reached through extensive deliberation. Do not deviate from these decisions without explicit instruction. When in doubt, refer back to this document.

---

## 1. WHAT WE ARE BUILDING

VitalNet is a clinical intelligence bridge. A software system that sits between an ASHA worker in the field and a PHC doctor at a clinic.

**The one-sentence definition:**
An ASHA worker fills a structured form on her Android phone. A doctor somewhere receives a structured clinical briefing with a triage classification before the patient arrives.

**The single unbroken flow that must work:**
```
ASHA fills form → FastAPI receives POST → GBM classifier fires → 
SHAP produces explanation → Groq LLM generates briefing → 
SQLite writes record → Doctor dashboard displays card
```

Everything built must serve this flow. Nothing built should exist outside this flow during the 24-hour sprint.

---

## 2. SYSTEM ARCHITECTURE

### 2.1 Layer Overview

```
Frontend (React + Vite)
    ├── ASHA Intake Form  →  POST /api/submit
    └── Doctor Dashboard  ←  GET /api/cases

Backend (FastAPI + Python)
    ├── POST /api/submit
    │     ├── Pydantic validation
    │     ├── GBM classifier (.pkl) → triage level
    │     ├── SHAP TreeExplainer → risk driver sentence
    │     ├── Groq Llama-3.3-70B → structured briefing JSON
    │     └── SQLite write (SQLAlchemy ORM)
    └── GET /api/cases → list of all case records
```

### 2.2 Data Flow — Step by Step

**Step 1 — ASHA Form Input**
React form collects: age, sex, chief_complaint, complaint_duration, vitals (bp_systolic, bp_diastolic, spo2, heart_rate, temperature), symptom_checklist (array of strings), free_text_observations.
Submits as JSON POST to `/api/submit`.

**Step 2 — FastAPI Input Structuring**
Pydantic model validates incoming JSON.
Maps to clinical JSON schema.
Required fields: age, sex, chief_complaint.
All vitals fields are optional — missing vitals must be handled gracefully.

**Step 3 — Triage Classification**
GBM classifier (.pkl loaded at startup) runs inference on structured vitals + symptom data.
Returns: triage_level (EMERGENCY / URGENT / ROUTINE), confidence_score (float).
This runs synchronously — it is fast (<5ms) and must complete before LLM call.
The classifier is LLM-independent. If Groq is down, triage still fires.

**Step 4 — SHAP Explanation**
SHAP TreeExplainer runs on the same input.
Returns the top contributing feature.
Converted to a plain English sentence: e.g. "SpO2 at 91% in a patient with chest tightness was the primary signal driving Emergency classification."

**Step 5 — LLM Briefing Generation**
Groq Llama-3.3-70B called with structured system prompt + patient JSON.
Returns structured JSON matching the briefing schema (see Section 4.3).
Temperature: 0.1. Max tokens: 1000.
Timeout: 8 seconds (configured via `client.with_options(timeout=httpx.Timeout(8.0))`).

**response_format:** Use `response_format={"type": "json_object"}` — forces valid JSON output, eliminates markdown fence stripping. Confirmed supported on `llama-3.3-70b-versatile` via Groq API docs.

**Error handling — use typed Groq exceptions (not bare `except Exception`):**
```python
import groq
except groq.RateLimitError     # 429 — back off, use fallback briefing
except groq.APIConnectionError # network — use fallback briefing  
except groq.InternalServerError # 5xx — use fallback briefing
```
Fallback behaviour: return safe briefing dict with triage_level from classifier (never null), briefing fields show "unavailable" state. Triage badge always renders.

Groq SDK auto-retries connection errors and 429s with exponential backoff (2 retries by default). Do not implement manual retry on top of this.

**Step 6 — Database Write**
SQLAlchemy ORM writes full case record to SQLite.
FHIR-compatible schema (see Section 4.4).
Every record is timestamped with ASHA identity (form field) and location (form field).

**Step 7 — Doctor Dashboard**
React fetches GET /api/cases on load and polls every 30 seconds.
Displays cases sorted by triage level: EMERGENCY first, then URGENT, then ROUTINE.
Each case renders as a briefing card (see Section 5.2).

---

## 3. TECH STACK — LOCKED DECISIONS

Do not substitute any of these without explicit instruction. Every choice was made deliberately.

### 3.1 Backend

| Component | Technology | Version | Reason |
|---|---|---|---|
| Runtime | Python | 3.13.7 | Installed on dev machine |
| Framework | FastAPI | 0.115+ | Async-first, Pydantic v2 native, Python ML integration |
| Validation | Pydantic v2 | Latest | Schema IS the clinical data contract |
| ASGI Server | Uvicorn | Latest | FastAPI native |
| ML | scikit-learn | 1.5+ | GBM classifier |
| Explainability | shap | Latest | TreeExplainer for GBM |
| ORM | SQLAlchemy | 2.x | Async-compatible, FHIR schema |
| Database | SQLite | Built-in | Zero setup, offline-safe |
| LLM | Groq SDK | Latest | llama-3.3-70b-versatile |

### 3.2 Frontend

| Component | Technology | Version | Reason |
|---|---|---|---|
| Framework | React | 18 | Component model for form complexity |
| Build Tool | Vite | 5 | Fast HMR, single command deploy |
| HTTP | Axios or fetch | — | POST to FastAPI |
| Styling | Tailwind CSS | 4.x (via @tailwindcss/vite) | Utility-first, mobile-first. No tailwind.config.js needed. Use `@import "tailwindcss"` in CSS. |

### 3.3 Infrastructure

| Component | Technology | Notes |
|---|---|---|
| ML Training | Google Colab (T4 GPU) | Train ONCE, commit .pkl to repo |
| Backend Hosting | Railway | Dockerfile-based, GitHub auto-deploy |
| Frontend Hosting | Vercel | Vite build, GitHub auto-deploy |
| Version Control | GitHub | Single repo, monorepo structure |

### 3.4 API Keys Required

```
GROQ_API_KEY=your_key_here
GEMINI_API_KEY=your_key_here  # fallback only — not in 24hr sprint scope
SARVAM_API_KEY=your_key_here  # voice only — not in 24hr sprint scope
```

---

## 4. DATA SCHEMAS — DO NOT DEVIATE

These schemas are the contract between every layer of the system. Changing them breaks the pipeline.

### 4.1 Intake Form Schema (Frontend → Backend)

```python
class IntakeForm(BaseModel):
    # Required
    asha_id: str
    patient_age: int  # years
    patient_sex: str  # "male" | "female" | "other"
    chief_complaint: str  # dropdown value
    complaint_duration: str  # dropdown value e.g. "2 hours", "1 day", "3 days"
    location: str  # village/area name

    # Vitals — all optional, None if not provided
    bp_systolic: Optional[int] = None   # mmHg
    bp_diastolic: Optional[int] = None  # mmHg
    spo2: Optional[int] = None          # percentage
    heart_rate: Optional[int] = None    # bpm
    temperature: Optional[float] = None # Celsius

    # Symptoms
    symptoms: List[str] = []  # from checklist
    observations: Optional[str] = None  # free text

    # Optional context
    known_conditions: Optional[str] = None
    current_medications: Optional[str] = None
```

### 4.2 Classifier Input Schema

The classifier receives a feature vector. Handle missing vitals with median imputation or a sentinel value (-1) — the classifier must be trained to handle missing values. Features in order:

```python
features = [
    patient_age,
    1 if patient_sex == "male" else 0,
    bp_systolic or -1,
    bp_diastolic or -1,
    spo2 or -1,
    heart_rate or -1,
    temperature or -1,
    len(symptoms),  # symptom count as proxy
    1 if "chest_pain" in symptoms else 0,
    1 if "breathlessness" in symptoms else 0,
    1 if "altered_consciousness" in symptoms else 0,
    1 if "severe_bleeding" in symptoms else 0,
    1 if "seizure" in symptoms else 0,
    1 if "high_fever" in symptoms else 0,
]
```

### 4.3 LLM Output Schema (Briefing JSON)

This is the locked output schema the LLM must return. System prompt enforces this.

```json
{
  "triage_level": "EMERGENCY | URGENT | ROUTINE",
  "primary_risk_driver": "plain English sentence explaining what drove the classification",
  "differential_diagnoses": ["diagnosis 1", "diagnosis 2", "diagnosis 3"],
  "red_flags": ["flag 1", "flag 2"],
  "recommended_immediate_actions": ["action 1", "action 2"],
  "recommended_tests": ["test 1", "test 2"],
  "uncertainty_flags": "what information is missing that would change this assessment",
  "disclaimer": "AI-generated clinical briefing for decision support only. Requires qualified medical examination and physician judgment before any clinical action."
}
```

**Rules enforced in system prompt:**
- triage_level must match the classifier output passed in — LLM cannot override it
- uncertainty_flags is mandatory — LLM must state missing information explicitly
- disclaimer is hardcoded — LLM cannot modify it
- No prose outside the JSON schema
- Each field has a character limit enforced in the prompt

### 4.4 SQLite Case Record Schema (FHIR-Compatible)

```python
# SQLAlchemy 2.x — use Mapped + mapped_column (modern style, no deprecation warnings)
# Import: from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
class CaseRecord(Base):
    __tablename__ = "cases"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    # ASHA identity
    asha_id: Mapped[str] = mapped_column(String, nullable=False)
    location: Mapped[str] = mapped_column(String, nullable=False)

    # Patient
    patient_age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    patient_sex: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    chief_complaint: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    complaint_duration: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Vitals (nullable)
    bp_systolic: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bp_diastolic: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    spo2: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    heart_rate: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Symptoms
    symptoms_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array as string
    observations: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    known_conditions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    current_medications: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # AI outputs
    triage_level: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # EMERGENCY|URGENT|ROUTINE
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    risk_driver: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    briefing_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # full LLM JSON as string

    # Status
    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
```

---

## 5. SYSTEM PROMPT — THREE-LAYER ARCHITECTURE

This is the exact structure of the system prompt. File location in repo: `/backend/prompts/clinical_system_prompt.txt`

Do not simplify this. Each layer serves a distinct safety function.

### Layer 1 — Role and Constraints (Static, Never Changes)

```
You are a clinical decision support tool assisting PHC doctors in rural India.

ROLE:
- You assist qualified medical professionals — you do not replace them
- You flag, rank, and explain — you do not diagnose
- The doctor makes all clinical decisions

HARD RULES:
1. The triage_level in your output MUST match the triage_level provided in the patient context. You cannot override it under any circumstances.
2. The disclaimer field value is fixed. You must output it exactly as provided. You cannot modify it.
3. uncertainty_flags is mandatory. If any information is missing or insufficient, state explicitly what is missing and how it would change your assessment.
4. Respond ONLY in the JSON schema provided. No prose outside the schema. No additional fields.
5. If you cannot generate a confident differential, output your best assessment with high uncertainty_flags — do not refuse to respond.
6. Use qualified language throughout: "may indicate", "consistent with", "warrants investigation" — never "is" or "confirms".
```

### Layer 2 — Patient Context (Dynamic, From Form)

```
PATIENT CONTEXT:
- Age: {patient_age} years
- Sex: {patient_sex}
- Location: {location}
- Chief Complaint: {chief_complaint}
- Duration: {complaint_duration}
- BP: {bp_systolic}/{bp_diastolic} mmHg [or "Not recorded"]
- SpO2: {spo2}% [or "Not recorded"]
- Heart Rate: {heart_rate} bpm [or "Not recorded"]
- Temperature: {temperature}°C [or "Not recorded"]
- Symptoms reported: {symptoms_list}
- ASHA observations: {observations}
- Known conditions: {known_conditions or "None reported"}
- Current medications: {current_medications or "None reported"}

TRIAGE CLASSIFICATION (from ML classifier — locked, do not override):
Level: {triage_level}
Confidence: {confidence_score}
Primary signal: {shap_explanation}
```

### Layer 3 — Output Schema (Locked)

```
Respond ONLY with this exact JSON structure. No text before or after.

{
  "triage_level": "{triage_level — copy exactly from context above}",
  "primary_risk_driver": "one sentence explaining the primary clinical signal in plain English",
  "differential_diagnoses": ["most likely", "second", "third"],
  "red_flags": ["specific red flag 1", "specific red flag 2"],
  "recommended_immediate_actions": ["action 1", "action 2", "action 3"],
  "recommended_tests": ["test 1", "test 2"],
  "uncertainty_flags": "explicit statement of what information is missing and how it affects this assessment",
  "disclaimer": "AI-generated clinical briefing for decision support only. Requires qualified medical examination and physician judgment before any clinical action."
}
```

---

## 6. FRONTEND SPECIFICATIONS

### 6.1 ASHA Intake Form — Field Specifications

**Chief Complaint (dropdown — required):**
```
Chest pain / tightness
Breathlessness / difficulty breathing
Fever
Abdominal pain
Headache / dizziness
Weakness / fatigue
Altered consciousness / confusion
Seizure
Severe bleeding
Nausea / vomiting
Baby / child unwell
Pregnancy complication
Injury / trauma
Other
```

**Complaint Duration (dropdown — required):**
```
Less than 1 hour
1–6 hours
6–24 hours
1–3 days
More than 3 days
```

**Symptom Checklist (multi-select checkboxes):**
```
chest_pain
breathlessness
high_fever (>102°F / >38.9°C)
altered_consciousness
seizure
severe_bleeding
severe_abdominal_pain
persistent_vomiting
severe_headache
weakness_one_side
difficulty_speaking
swelling_face_throat
```

**Vitals Fields (all optional, numeric input):**
- BP Systolic (mmHg) — placeholder: "e.g. 120"
- BP Diastolic (mmHg) — placeholder: "e.g. 80"
- SpO2 (%) — placeholder: "e.g. 98"
- Heart Rate (bpm) — placeholder: "e.g. 72"
- Temperature (°C) — placeholder: "e.g. 37.2"

**Text Fields:**
- ASHA ID (required) — text input
- Patient Age (required) — numeric input
- Patient Sex (required) — radio: Male / Female / Other
- Location/Village (required) — text input
- Observations (optional) — textarea, max 500 chars

### 6.2 Doctor Dashboard — Briefing Card Structure

Each case card must display:

```
┌─────────────────────────────────────────┐
│ [EMERGENCY] badge (red)                  │
│ Patient: 55M | Location: Rural UP        │
│ Chief Complaint: Chest pain | 2 hours    │
│ Submitted: 14:32 by ASHA-001            │
├─────────────────────────────────────────┤
│ PRIMARY SIGNAL                           │
│ SpO2 at 91% with chest tightness in     │
│ male over 50 — primary Emergency driver  │
├─────────────────────────────────────────┤
│ DIFFERENTIALS                            │
│ • Acute coronary syndrome                │
│ • Hypertensive urgency                   │
│ • Pulmonary embolism                     │
├─────────────────────────────────────────┤
│ RED FLAGS                                │
│ ⚠ SpO2 below 94%                        │
│ ⚠ BP above 160 systolic                 │
├─────────────────────────────────────────┤
│ IMMEDIATE ACTIONS                        │
│ → ECG if available                       │
│ → Aspirin 325mg if ACS suspected        │
│ → Oxygen supplementation                 │
├─────────────────────────────────────────┤
│ UNCERTAINTY FLAGS                        │
│ No prior cardiac history recorded        │
├─────────────────────────────────────────┤
│ ⚠ AI-generated. Physician judgment      │
│   required before any clinical action.  │
├─────────────────────────────────────────┤
│ [Mark Reviewed]  [Add Notes]            │
└─────────────────────────────────────────┘
```

**Triage badge colors:**
- EMERGENCY: red background, white text (`bg-red-600 text-white`)
- URGENT: amber background, dark text (`bg-amber-500 text-gray-900`)
- ROUTINE: green background, white text (`bg-green-600 text-white`)

---

## 7. PROJECT STRUCTURE

```
vitalnet/
├── backend/
│   ├── main.py                    # FastAPI app, routes
│   ├── models.py                  # SQLAlchemy ORM models
│   ├── schemas.py                 # Pydantic input/output schemas
│   ├── classifier.py              # GBM .pkl loader + inference
│   ├── explainer.py               # SHAP TreeExplainer wrapper
│   ├── llm.py                     # Groq API call + response handling
│   ├── database.py                # SQLAlchemy engine + session
│   ├── prompts/
│   │   └── clinical_system_prompt.txt  # Three-layer system prompt
│   ├── models/
│   │   └── triage_classifier.pkl  # Trained GBM — committed to repo
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env                       # API keys — never committed
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   ├── pages/
│   │   │   ├── IntakeForm.jsx     # ASHA intake form
│   │   │   └── Dashboard.jsx      # Doctor dashboard
│   │   ├── components/
│   │   │   ├── BriefingCard.jsx   # Single case briefing card
│   │   │   ├── TriageBadge.jsx    # Color-coded badge component
│   │   │   └── VitalsInput.jsx    # Vitals field group
│   │   └── main.jsx
│   ├── index.html
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── package.json
├── colab/
│   └── train_classifier.ipynb     # GBM training notebook
├── .gitignore
└── README.md
```

---

## 8. CLASSIFIER TRAINING SPECIFICATION

This runs on Google Colab before the sprint. Output is `triage_classifier.pkl` committed to `/backend/models/`.

### 8.1 Synthetic Dataset Generation

Generate 5,000 synthetic patient records. Label each with triage level using clinical rules:

**EMERGENCY rules (any one of):**
- SpO2 < 90%
- Heart rate > 130 or < 40
- BP systolic > 180 or < 80
- Temperature > 40°C or < 35°C
- altered_consciousness in symptoms
- seizure in symptoms
- severe_bleeding in symptoms
- Age > 60 AND SpO2 < 94 AND chest_pain in symptoms

**URGENT rules (any one of, not Emergency):**
- SpO2 90–94%
- Heart rate 110–130
- BP systolic 160–180
- Temperature 38.9–40°C
- breathlessness in symptoms AND heart_rate > 100
- Age > 50 AND chest_pain in symptoms AND bp_systolic > 150
- severe_abdominal_pain in symptoms AND high_fever in symptoms

**ROUTINE:**
- Everything else

**Calibration requirement:**
The classifier must minimize false negatives on Emergency cases. Use class_weight in GradientBoostingClassifier or adjust classification threshold post-training. A false negative on Emergency (Emergency classified as Routine) is the dangerous failure mode.

### 8.2 Training Code Structure

```python
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
import shap
import pickle
import numpy as np

# Generate synthetic data
# [data generation code]

# Train
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
clf = GradientBoostingClassifier(n_estimators=100, max_depth=4, random_state=42)
clf.fit(X_train, y_train)

# Validate — print these numbers, they go on the PPT
print(classification_report(y_test, clf.predict(X_test)))
print(confusion_matrix(y_test, clf.predict(X_test)))

# Verify zero false negatives on Emergency
# [check CM Emergency row]

# Save
with open("triage_classifier.pkl", "wb") as f:
    pickle.dump(clf, f)

# Verify SHAP works
explainer = shap.TreeExplainer(clf)
shap_values = explainer.shap_values(X_test[:1])
print("SHAP working:", shap_values)
```

---

## 9. API ENDPOINTS

### POST /api/submit
**Request:** IntakeForm JSON (Section 4.1)
**Response:**
```json
{
  "case_id": 1,
  "triage_level": "EMERGENCY",
  "confidence_score": 0.94,
  "risk_driver": "SpO2 at 91% with chest tightness...",
  "briefing": { ...LLM output schema... },
  "status": "success"
}
```

### GET /api/cases
**Response:** Array of case records sorted by triage level then timestamp descending
```json
[
  {
    "case_id": 1,
    "created_at": "2026-03-10T14:32:00Z",
    "asha_id": "ASHA-001",
    "location": "Rampur Village",
    "patient_age": 55,
    "patient_sex": "male",
    "chief_complaint": "Chest pain / tightness",
    "triage_level": "EMERGENCY",
    "risk_driver": "...",
    "briefing": { ... },
    "reviewed": false
  }
]
```

### PATCH /api/cases/{case_id}/review
**Request:** `{ "reviewed": true, "review_notes": "optional string" }`
**Response:** `{ "status": "updated" }`

### GET /api/health
**Response:** `{ "status": "ok", "classifier": "loaded", "db": "connected" }`

---

## 10. ENVIRONMENT AND CONSTRAINTS

### 10.1 Development Machine

- OS: Windows 10
- Python: 3.13.7 (native Windows — no WSL)
- Node: v22.17.0
- RAM: 4GB
- CPU: Intel Pentium P6200

**Memory discipline on 4GB RAM:**
- Never run Chrome + VS Code + both dev servers simultaneously
- FastAPI dev server: ~80MB
- React dev server (Vite): ~150MB
- Browser with one tab: ~200MB
- Total safe working set: ~430MB — fits within 4GB with OS overhead

### 10.2 Windows-Specific Commands

All commands assume Windows CMD or PowerShell — not bash.

**Virtual environment:**
```cmd
python -m venv venv
venv\Scripts\activate
```

**Environment variables (Windows):**
```cmd
set GROQ_API_KEY=your_key_here
```
Or use a `.env` file with `python-dotenv`.

**Running FastAPI:**
```cmd
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Running Vite:**
```cmd
npm run dev
```

### 10.3 CORS Configuration

FastAPI must allow requests from the React dev server during development and from the Vercel URL in production.

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "https://your-app.vercel.app",  # Production
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 10.4 .env File Structure

```
GROQ_API_KEY=gsk_...
GEMINI_API_KEY=AI...
DATABASE_URL=sqlite:///./vitalnet.db
ENVIRONMENT=development
```

### 10.5 .gitignore Requirements

```
.env
venv/
__pycache__/
*.pyc
node_modules/
dist/
vitalnet.db
*.log
```

**The .pkl file IS committed to the repo.** It is not sensitive data — it is the trained model that the application depends on. Without it committed, Railway cannot run the classifier.

---

## 11. DEPLOYMENT

### 11.1 Railway (Backend)

**Dockerfile:**
```dockerfile
FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Railway environment variables** (set in Railway dashboard):
```
GROQ_API_KEY=your_key
GEMINI_API_KEY=your_key
DATABASE_URL=sqlite:///./vitalnet.db
ENVIRONMENT=production
PORT=8000
```

### 11.2 Vercel (Frontend)

**vite.config.js** — Tailwind v4 requires `@tailwindcss/vite` plugin. Proxy in dev, env var in production:
```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: { '/api': 'http://localhost:8000' }  // remove for Vercel production build
  }
})
```

**index.css** — Tailwind v4 uses a single import (no `@tailwind base/components/utilities`):
```css
@import "tailwindcss";
```

**Environment variable in Vercel dashboard:**
```
VITE_API_BASE_URL=https://your-railway-app.railway.app
```

**In React code:**
```javascript
const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
```

---

## 12. WHAT IS OUT OF SCOPE

Do not build these during the 24-hour sprint. Do not ask about them. Do not suggest them.

- Voice input (Sarvam AI STT)
- Multilingual form (react-i18next)
- ONNX browser-side inference
- Three-tier LLM fallback chain (Groq primary only)
- SMS notifications
- Doctor authentication (JWT)
- Architecture diagram tab
- Pre-seeded demo cases (submit live cases during demo)
- Any animation or micro-interaction beyond functional feedback
- Dark mode

These are Phase 2 features. They exist in the roadmap. They do not exist in the 24-hour build.

---

## 13. CRITICAL RULES FOR THIS CODEBASE

1. **The classifier fires before the LLM call.** Always. The LLM receives the triage level as locked context. The LLM cannot produce a briefing without knowing the triage level first.

2. **The triage level on the doctor dashboard always comes from the classifier output stored in SQLite.** Never from the LLM response directly. If the LLM response has a different triage level (it shouldn't — the system prompt prevents this), the database value wins.

3. **Missing vitals are handled gracefully.** Never throw a 422 because SpO2 is missing. The classifier uses -1 as a sentinel for missing vitals. The LLM prompt explicitly notes "Not recorded" for missing fields.

4. **The disclaimer is non-removable.** It is hardcoded in the system prompt as a fixed string. It renders as a non-dismissible element in the briefing card UI.

5. **Every form submission writes to SQLite.** The database write is not optional and is not dependent on the LLM call succeeding. The record is written with whatever is available — if the LLM call fails, the case record exists with triage level and risk driver, and briefing_json is null.

6. **CORS is configured before anything else.** A React app that cannot reach FastAPI produces zero visible errors in FastAPI logs — the error lives in the browser console. Configure CORS on day one.

   **Do not use `@app.on_event("startup")`** — deprecated in FastAPI 0.115+. Use the `asynccontextmanager` lifespan pattern:
   ```python
   from contextlib import asynccontextmanager
   @asynccontextmanager
   async def lifespan(app: FastAPI):
       init_db(); load_classifier()
       yield
   app = FastAPI(lifespan=lifespan)
   ```

7. **The .pkl file is committed to the repo.** Railway cannot load a classifier that isn't in the repository. Train once on Colab, download the .pkl, commit it, and never retrain during the sprint.

8. **Save the classifier with `pickle.dump(model_data, f, protocol=5)`.** Protocol 5 is recommended by scikit-learn docs for NumPy 2.x arrays — reduces memory footprint and speeds up I/O. Protocol 5 requires Python 3.8+ to load (Railway uses 3.13-slim — compatible). Do not use default protocol.

---

## 14. DEFINITION OF DONE (24-HOUR SPRINT)

The prototype is complete when all of the following are true:

- [ ] `GET /api/health` returns `{"status": "ok", "classifier": "loaded", "db": "connected"}`
- [ ] Submitting the intake form via the React UI creates a record in SQLite
- [ ] The classifier returns a triage level for every submission
- [ ] The SHAP explainer returns a plain-English risk driver sentence
- [ ] The Groq LLM returns a valid briefing JSON matching the output schema
- [ ] The doctor dashboard displays the submitted case with triage badge and briefing card
- [ ] The "Mark Reviewed" button updates the case record in SQLite
- [ ] The deployed Railway URL returns a valid API response
- [ ] The deployed Vercel URL renders the intake form and dashboard
- [ ] End-to-end flow works on mobile browser (test on your phone)

When all ten are checked, the sprint is done.

---

*Document version: 1.0 — 24-hour sprint scope*
*Project: VitalNet — AI Diagnostic Layer*
*Dev machine: Windows 10, Python 3.13.7, Node v22.17.0*
*Prepared for use with Google Antigravity, Claude Code, Gemini CLI, GitHub Copilot*
