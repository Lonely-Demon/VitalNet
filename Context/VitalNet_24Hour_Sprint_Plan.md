# VitalNet — 24-Hour Sprint Plan
## From Zero to Deployed Prototype
### Dev Machine: Windows 10 | Python 3.13.7 | Node v22.17.0

---

> **How to use this document**
> Read the entire document once before touching your keyboard. Every phase has a DELIVERABLE — a binary check you run before moving to the next phase. If the deliverable check fails, you fix it before proceeding. Moving forward with a broken deliverable compounds into a broken system at hour 18 that you cannot debug under fatigue.
>
> Time estimates assume focused work with no distractions. Each phase has a buffer. Use the buffer for debugging, not for scope expansion.
>
> The sprint plan is written for you working alone on Windows native Python. Every command is Windows CMD/PowerShell.

---

## THE SINGLE RULE THAT GOVERNS THE ENTIRE SPRINT

**The minimum working prototype is one unbroken flow.**

```
ASHA fills form → FastAPI receives POST → Classifier fires →
SHAP explains → Groq generates briefing → SQLite writes →
Doctor dashboard displays card
```

Every decision during the sprint is evaluated against one question:
**"Does this serve the flow or does this distract from it?"**

If it distracts, cut it. You can add it later. You cannot recover a broken flow at hour 20.

---

---

# PRE-SPRINT (Before the Clock Starts)
## Duration: ~45 minutes | Must complete before Hour 0

This phase happens before the sprint begins. It is not optional. Skipping any step here will cost you 2–4 hours during the sprint itself.

---

### PRE-1 — Train and Commit the Classifier

**Why first:** The `.pkl` file is a hard dependency for the entire backend. Every other backend task assumes it exists. If you start building the backend without the classifier, you are building on an assumption that may break.

**Steps:**

1. Open Google Colab (colab.research.google.com)
2. Create a new notebook
3. Paste and run this complete training script:

```python
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
import shap
import pickle
import warnings
warnings.filterwarnings('ignore')

# ── SYNTHETIC DATA GENERATION ──────────────────────────────────────────────

np.random.seed(42)
N = 5000

def generate_patient():
    age = np.random.randint(1, 85)
    sex = np.random.randint(0, 2)
    bp_sys = np.random.randint(70, 200)
    bp_dia = np.random.randint(40, 120)
    spo2 = np.random.randint(80, 100)
    hr = np.random.randint(35, 160)
    temp = round(np.random.uniform(34.5, 41.5), 1)
    symptom_count = np.random.randint(0, 6)

    # High-risk symptom flags
    altered_consciousness = np.random.choice([0, 1], p=[0.92, 0.08])
    seizure = np.random.choice([0, 1], p=[0.95, 0.05])
    severe_bleeding = np.random.choice([0, 1], p=[0.94, 0.06])
    chest_pain = np.random.choice([0, 1], p=[0.80, 0.20])
    breathlessness = np.random.choice([0, 1], p=[0.78, 0.22])
    high_fever = np.random.choice([0, 1], p=[0.75, 0.25])

    return [age, sex, bp_sys, bp_dia, spo2, hr, temp,
            symptom_count, chest_pain, breathlessness,
            altered_consciousness, severe_bleeding, seizure, high_fever]

def label_patient(p):
    age, sex, bp_sys, bp_dia, spo2, hr, temp, \
    sym_count, chest_pain, breathlessness, \
    altered_con, severe_bleed, seizure, high_fever = p

    # EMERGENCY — any one of these
    if spo2 < 90: return 2
    if hr > 130 or hr < 40: return 2
    if bp_sys > 180 or bp_sys < 80: return 2
    if temp > 40.0 or temp < 35.0: return 2
    if altered_con == 1: return 2
    if seizure == 1: return 2
    if severe_bleed == 1: return 2
    if age > 60 and spo2 < 94 and chest_pain == 1: return 2

    # URGENT — any one of these (not Emergency)
    if 90 <= spo2 <= 94: return 1
    if 110 <= hr <= 130: return 1
    if 160 <= bp_sys <= 180: return 1
    if 38.9 <= temp <= 40.0: return 1
    if breathlessness == 1 and hr > 100: return 1
    if age > 50 and chest_pain == 1 and bp_sys > 150: return 1

    # ROUTINE
    return 0

data = [generate_patient() for _ in range(N)]
labels = [label_patient(p) for p in data]

X = np.array(data)
y = np.array(labels)

feature_names = [
    "age", "sex", "bp_systolic", "bp_diastolic", "spo2",
    "heart_rate", "temperature", "symptom_count",
    "chest_pain", "breathlessness", "altered_consciousness",
    "severe_bleeding", "seizure", "high_fever"
]

print(f"Dataset: {N} records")
print(f"Class distribution: ROUTINE={sum(y==0)}, URGENT={sum(y==1)}, EMERGENCY={sum(y==2)}")

# ── TRAIN ──────────────────────────────────────────────────────────────────

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

clf = GradientBoostingClassifier(
    n_estimators=150,
    max_depth=4,
    learning_rate=0.1,
    random_state=42
)
clf.fit(X_train, y_train)

# ── VALIDATE ───────────────────────────────────────────────────────────────

y_pred = clf.predict(X_test)
print("\n── CLASSIFICATION REPORT ──")
print(classification_report(y_test, y_pred,
      target_names=["ROUTINE", "URGENT", "EMERGENCY"]))

cm = confusion_matrix(y_test, y_pred)
print("── CONFUSION MATRIX ──")
print("Rows=Actual, Cols=Predicted | 0=ROUTINE 1=URGENT 2=EMERGENCY")
print(cm)

# Critical check — Emergency false negatives
emergency_actual = cm[2]  # actual Emergency row
emergency_fn = emergency_actual[0] + emergency_actual[1]  # classified as non-Emergency
print(f"\n── CRITICAL SAFETY METRIC ──")
print(f"Emergency false negatives (Emergency classified as non-Emergency): {emergency_fn}")
if emergency_fn == 0:
    print("✓ PASS — Zero Emergency false negatives")
else:
    print("⚠ WARNING — Emergency false negatives detected. Review threshold.")

overall_accuracy = (y_pred == y_test).mean()
print(f"\nOverall accuracy: {overall_accuracy:.4f} ({overall_accuracy*100:.1f}%)")
print("\n** RECORD THESE NUMBERS — THEY GO IN YOUR PORTFOLIO **")

# ── VERIFY SHAP ────────────────────────────────────────────────────────────

print("\n── SHAP VERIFICATION ──")
explainer = shap.TreeExplainer(clf)
sample = X_test[:1]
shap_values = explainer.shap_values(sample)
print(f"SHAP output shape: {[s.shape for s in shap_values]}")
print(f"Top feature for sample: {feature_names[np.argmax(np.abs(shap_values[2][0]))]}")
print("✓ SHAP working correctly")

# ── SAVE ───────────────────────────────────────────────────────────────────

model_data = {
    "classifier": clf,
    "explainer": explainer,
    "feature_names": feature_names,
    "label_map": {0: "ROUTINE", 1: "URGENT", 2: "EMERGENCY"},
    "accuracy": float(overall_accuracy),
    "emergency_fn": int(emergency_fn)
}

# protocol=5 recommended by scikit-learn docs for NumPy 2.x arrays — reduces memory, faster I/O
with open("triage_classifier.pkl", "wb") as f:
    pickle.dump(model_data, f, protocol=5)

print("\n✓ Saved: triage_classifier.pkl")
print("Download this file and commit to /backend/models/triage_classifier.pkl")
```

4. Download `triage_classifier.pkl` from Colab files panel
5. Record the accuracy and Emergency false negative numbers — you will need them

**DO NOT:**
- Skip the confusion matrix check
- Retrain during the sprint — the file is committed once
- Modify the feature order after training — the backend must use the exact same feature vector

---

### PRE-2 — Repository Setup

```cmd
cd C:\Projects\vitalnet

git init
git remote add origin https://github.com/yourusername/vitalnet.git
```

Create this exact folder structure:

```cmd
mkdir backend
mkdir backend\prompts
mkdir backend\models
mkdir frontend
mkdir colab
```

Place `triage_classifier.pkl` in `backend\models\`

Create `.gitignore` in root:

```
.env
venv/
__pycache__/
*.pyc
node_modules/
dist/
vitalnet.db
*.log
.env.local
```

Create `.env` in `backend\`:

```
GROQ_API_KEY=your_groq_key_here
DATABASE_URL=sqlite:///./vitalnet.db
ENVIRONMENT=development
```

**Initial commit:**

```cmd
git add .
git commit -m "init: project structure + trained classifier"
git push -u origin main
```

---

### PRE-SPRINT DELIVERABLE CHECK

Before starting Hour 0, verify all of these:

- [ ] `triage_classifier.pkl` is in `backend\models\` and is not empty (should be 1–5MB)
- [ ] Accuracy and Emergency FN numbers are recorded somewhere
- [ ] Folder structure matches the spec in Developer Context Section 7
- [ ] `.gitignore` exists and `.env` is listed in it
- [ ] Initial commit is pushed to GitHub
- [ ] Railway account is ready (no project created yet)
- [ ] Vercel account is ready (no project created yet)

**Do not start Hour 0 until all seven are checked.**

---

---

# PHASE 1 — Backend Foundation
## Hours 0–3 | Target complete by Hour 3

**Goal:** A FastAPI server that starts, connects to SQLite, loads the classifier, and returns a health check. Nothing more.

**The temptation to resist:** Adding LLM calls, SHAP, or any intelligence at this stage. The health check is the only deliverable. A server that starts and confirms all dependencies are loaded is more valuable at this point than a server that tries to do everything and fails silently.

---

### Step 1.1 — Virtual Environment and Dependencies

```cmd
cd backend
python -m venv venv
venv\Scripts\activate
```

Create `requirements.txt`:

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
pydantic==2.7.0
sqlalchemy==2.0.30
python-dotenv==1.0.1
groq>=0.9.0
scikit-learn>=1.5.2
shap>=0.45.0
numpy>=2.1.0
python-multipart==0.0.9
httpx>=0.27.0
```

Install:

```cmd
pip install -r requirements.txt
```

**This will take 5–10 minutes on your connection. Do not interrupt it.**

If any package fails, install it individually:
```cmd
pip install "packagename>=version"
```

> ⚠️ **Python 3.13 compatibility — critical:**
> `numpy>=2.1.0` and `scikit-learn>=1.5.2` are the minimum versions with Python 3.13 support. Earlier versions (1.26.4 / 1.5.0) will fail to install and burn Phase 1 time. `groq` is intentionally unpinned — the SDK evolves rapidly and a stale pin causes silent API incompatibilities discovered only during the LLM call in Phase 2.
>
> ⚠️ **Tailwind CSS v4:** This plan uses Tailwind v4 via `@tailwindcss/vite`. No `tailwind.config.js` needed. Use `@import "tailwindcss"` in CSS — not the v3 directives (`@tailwind base` etc).

**DO NOT:**
- Use `pip install --upgrade` on anything — let pip resolve within the `>=` constraints
- Skip the virtual environment — installing globally on Windows 3.13 will cause conflicts

---

### Step 1.2 — Database Setup

Create `backend\database.py`:

```python
# SQLAlchemy 2.x imports — Mapped + mapped_column is the modern non-deprecated style
from sqlalchemy import create_engine, Integer, String, Float, Boolean, DateTime, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from typing import Optional
from datetime import datetime, timezone
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./vitalnet.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}  # Required for SQLite
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


class CaseRecord(Base):
    __tablename__ = "cases"

    # SQLAlchemy 2.x modern Mapped style — type-annotated, no deprecation warnings
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    asha_id: Mapped[str] = mapped_column(String, nullable=False)
    location: Mapped[str] = mapped_column(String, nullable=False)
    patient_age: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    patient_sex: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    chief_complaint: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    complaint_duration: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    bp_systolic: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bp_diastolic: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    spo2: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    heart_rate: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    symptoms_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    observations: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    known_conditions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    current_medications: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    triage_level: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    risk_driver: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    briefing_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


def get_db():
    # FastAPI dependency injection pattern — one session per request, auto-cleanup on exit
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Annotated shorthand — use SessionDep instead of Session = Depends(get_db) in routes
# from typing import Annotated
# SessionDep = Annotated[Session, Depends(get_db)]


def init_db():
    Base.metadata.create_all(bind=engine)
```

---

### Step 1.3 — Pydantic Schemas

Create `backend\schemas.py`:

```python
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class IntakeForm(BaseModel):
    asha_id: str
    patient_age: int = Field(ge=0, le=120)
    patient_sex: str
    chief_complaint: str
    complaint_duration: str
    location: str

    bp_systolic: Optional[int] = Field(None, ge=50, le=250)
    bp_diastolic: Optional[int] = Field(None, ge=30, le=150)
    spo2: Optional[int] = Field(None, ge=70, le=100)
    heart_rate: Optional[int] = Field(None, ge=20, le=220)
    temperature: Optional[float] = Field(None, ge=30.0, le=45.0)

    symptoms: List[str] = []
    observations: Optional[str] = Field(None, max_length=500)
    known_conditions: Optional[str] = None
    current_medications: Optional[str] = None


class BriefingOutput(BaseModel):
    triage_level: str
    primary_risk_driver: str
    differential_diagnoses: List[str]
    red_flags: List[str]
    recommended_immediate_actions: List[str]
    recommended_tests: List[str]
    uncertainty_flags: str
    disclaimer: str


class SubmitResponse(BaseModel):
    case_id: int
    triage_level: str
    confidence_score: float
    risk_driver: str
    briefing: Optional[BriefingOutput]
    status: str


class CaseListItem(BaseModel):
    case_id: int
    created_at: datetime
    asha_id: str
    location: str
    patient_age: int
    patient_sex: str
    chief_complaint: str
    complaint_duration: str
    triage_level: str
    risk_driver: str
    briefing: Optional[BriefingOutput]
    reviewed: bool

    class Config:
        from_attributes = True


class ReviewUpdate(BaseModel):
    reviewed: bool
    review_notes: Optional[str] = None
```

---

### Step 1.4 — Classifier Wrapper

Create `backend\classifier.py`:

```python
import pickle
import numpy as np
import shap
from pathlib import Path
from typing import Optional

MODEL_PATH = Path(__file__).parent / "models" / "triage_classifier.pkl"

# Loaded once at startup — not per request
_model_data = None


def load_classifier():
    global _model_data
    with open(MODEL_PATH, "rb") as f:
        _model_data = pickle.load(f)  # Saved with protocol=5 — Python 3.8+ required to load
    print(f"✓ Classifier loaded — accuracy: {_model_data['accuracy']:.4f}")
    print(f"✓ Emergency false negatives in training: {_model_data['emergency_fn']}")
    return True


def build_feature_vector(form_data: dict) -> np.ndarray:
    """
    Build the feature vector in the exact order the classifier was trained on.
    Missing vitals use -1 as sentinel value.
    """
    symptoms = form_data.get("symptoms", [])

    features = [
        form_data.get("patient_age", 30),
        1 if form_data.get("patient_sex", "").lower() == "male" else 0,
        form_data.get("bp_systolic") if form_data.get("bp_systolic") is not None else -1,
        form_data.get("bp_diastolic") if form_data.get("bp_diastolic") is not None else -1,
        form_data.get("spo2") if form_data.get("spo2") is not None else -1,
        form_data.get("heart_rate") if form_data.get("heart_rate") is not None else -1,
        form_data.get("temperature") if form_data.get("temperature") is not None else -1,
        len(symptoms),
        1 if "chest_pain" in symptoms else 0,
        1 if "breathlessness" in symptoms else 0,
        1 if "altered_consciousness" in symptoms else 0,
        1 if "severe_bleeding" in symptoms else 0,
        1 if "seizure" in symptoms else 0,
        1 if "high_fever" in symptoms else 0,
    ]

    return np.array([features])


def run_triage(form_data: dict) -> dict:
    """
    Run classifier and SHAP explainer.
    Returns triage_level, confidence_score, risk_driver.
    """
    if _model_data is None:
        raise RuntimeError("Classifier not loaded — call load_classifier() at startup")

    clf = _model_data["classifier"]
    explainer = _model_data["explainer"]
    feature_names = _model_data["feature_names"]
    label_map = _model_data["label_map"]

    X = build_feature_vector(form_data)

    # Triage classification
    pred_class = int(clf.predict(X)[0])
    pred_proba = clf.predict_proba(X)[0]
    confidence = float(pred_proba[pred_class])
    triage_level = label_map[pred_class]

    # SHAP explanation
    shap_values = explainer.shap_values(X)
    class_shap = shap_values[pred_class][0]
    top_feature_idx = int(np.argmax(np.abs(class_shap)))
    top_feature = feature_names[top_feature_idx]
    top_value = X[0][top_feature_idx]

    risk_driver = _build_risk_driver_sentence(
        top_feature, top_value, triage_level, form_data
    )

    return {
        "triage_level": triage_level,
        "confidence_score": confidence,
        "risk_driver": risk_driver,
        "top_feature": top_feature,
    }


def _build_risk_driver_sentence(
    feature: str, value: float, triage_level: str, form_data: dict
) -> str:
    """Convert SHAP top feature into a plain English sentence."""
    age = form_data.get("patient_age", "unknown")
    sex = form_data.get("patient_sex", "patient")

    labels = {
        "spo2": f"SpO2 at {int(value)}%",
        "bp_systolic": f"Systolic BP at {int(value)} mmHg",
        "heart_rate": f"Heart rate at {int(value)} bpm",
        "temperature": f"Temperature at {value:.1f}°C",
        "age": f"Patient age ({int(value)} years)",
        "altered_consciousness": "Altered consciousness",
        "seizure": "Reported seizure",
        "severe_bleeding": "Reported severe bleeding",
        "chest_pain": "Chest pain",
        "breathlessness": "Breathlessness",
        "high_fever": "High fever",
    }

    signal = labels.get(feature, f"{feature} value")
    return (
        f"{signal} in a {age}-year-old {sex} was the primary signal "
        f"driving {triage_level} classification."
    )
```

---

### Step 1.5 — FastAPI App (Health Check Only)

Create `backend\main.py` — **health check only at this stage:**

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import os
from dotenv import load_dotenv

from database import init_db, get_db, CaseRecord
from classifier import load_classifier
from schemas import IntakeForm, SubmitResponse, CaseListItem, ReviewUpdate

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    load_classifier()
    print("✓ VitalNet API started")
    yield


app = FastAPI(title="VitalNet API", version="0.1.0", lifespan=lifespan)

# CORS — configure before anything else
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        os.getenv("FRONTEND_URL", "https://placeholder.vercel.app"),
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "classifier": "loaded",
        "db": "connected"
    }


# Placeholder routes — implemented in Phase 2
@app.post("/api/submit")
async def submit_case():
    return {"status": "not yet implemented"}


@app.get("/api/cases")
def get_cases():
    return []


@app.patch("/api/cases/{case_id}/review")
def review_case(case_id: int):
    return {"status": "not yet implemented"}
```

---

### Step 1.6 — Start and Verify

```cmd
cd backend
venv\Scripts\activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Open browser: `http://localhost:8000/api/health`

Expected response:
```json
{"status": "ok", "classifier": "loaded", "db": "connected"}
```

Also verify: `http://localhost:8000/docs` — FastAPI auto-docs should load.

---

### ✅ PHASE 1 DELIVERABLE

**Binary check — all must pass before moving to Phase 2:**

- [ ] `uvicorn main:app --reload` starts without errors
- [ ] `GET /api/health` returns `{"status": "ok", "classifier": "loaded", "db": "connected"}`
- [ ] FastAPI docs load at `http://localhost:8000/docs`
- [ ] No import errors in terminal output
- [ ] `vitalnet.db` file has been created in the backend folder

**If any check fails:** Fix it before Phase 2. A server that starts is the foundation everything else sits on.

---

---

# PHASE 2 — Intelligence Pipeline
## Hours 3–7 | Target complete by Hour 7

**Goal:** The `/api/submit` endpoint receives form data, runs the classifier, runs SHAP, calls Groq, writes to SQLite, and returns a complete response.

**The temptation to resist:** Frontend. Nothing frontend. The pipeline must work via the FastAPI docs UI before you write a single JSX file.

**The failure mode to watch for:** Groq returning malformed JSON. The LLM call uses `temperature=0.1` and a strict system prompt, but LLMs occasionally return JSON with extra prose or a missing field. The parser must handle this gracefully — never crash the endpoint because of a bad LLM response.

---

### Step 2.1 — System Prompt File

Create `backend\prompts\clinical_system_prompt.txt`:

```
You are a clinical decision support tool assisting PHC doctors in rural India.

ROLE:
- You assist qualified medical professionals — you do not replace them
- You flag, rank, and explain — you do not diagnose
- The doctor makes all clinical decisions

HARD RULES:
1. The triage_level in your output MUST match the triage_level provided in the patient context. You cannot override it under any circumstances.
2. The disclaimer field value is fixed. Output it exactly as shown in the schema. Do not modify it.
3. uncertainty_flags is mandatory. State explicitly what information is missing and how it affects your assessment.
4. Respond ONLY with the JSON schema below. No text before it, no text after it, no markdown code fences.
5. If you cannot generate a confident differential, output your best assessment with detailed uncertainty_flags. Do not refuse to respond.
6. Use qualified language: "may indicate", "consistent with", "warrants investigation" — never "is" or "confirms".

OUTPUT SCHEMA — respond with exactly this structure:
{
  "triage_level": "[copy from patient context — do not change]",
  "primary_risk_driver": "one sentence in plain English explaining the primary clinical signal",
  "differential_diagnoses": ["most likely diagnosis", "second", "third"],
  "red_flags": ["specific red flag 1", "specific red flag 2"],
  "recommended_immediate_actions": ["action 1", "action 2", "action 3"],
  "recommended_tests": ["test 1", "test 2"],
  "uncertainty_flags": "explicit statement of what is missing and how it affects this assessment",
  "disclaimer": "AI-generated clinical briefing for decision support only. Requires qualified medical examination and physician judgment before any clinical action."
}
```

---

### Step 2.2 — LLM Module

Create `backend\llm.py`:

```python
import os
import json
import groq
import httpx
from pathlib import Path
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

SYSTEM_PROMPT_PATH = Path(__file__).parent / "prompts" / "clinical_system_prompt.txt"

FIXED_DISCLAIMER = (
    "AI-generated clinical briefing for decision support only. "
    "Requires qualified medical examination and physician judgment "
    "before any clinical action."
)


def _load_system_prompt() -> str:
    with open(SYSTEM_PROMPT_PATH, "r") as f:
        return f.read()


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


def generate_briefing(form_data: dict, triage_result: dict) -> dict:
    """
    Call Groq Llama-3.3-70B and return parsed briefing JSON.
    On any failure, returns a safe error state — does NOT raise.
    """
    system_prompt = _load_system_prompt()
    patient_context = _build_patient_context(form_data, triage_result)

    try:
        response = client.with_options(timeout=httpx.Timeout(8.0)).chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": patient_context},
            ],
            response_format={"type": "json_object"},  # Forces valid JSON — no fences needed
            temperature=0.1,
            max_tokens=1000,
        )

        raw = response.choices[0].message.content.strip()
        briefing = json.loads(raw)

        # Safety enforcement — triage level cannot be overridden
        briefing["triage_level"] = triage_result["triage_level"]

        # Disclaimer cannot be modified
        briefing["disclaimer"] = FIXED_DISCLAIMER

        # Ensure all required fields exist
        required_fields = [
            "triage_level", "primary_risk_driver", "differential_diagnoses",
            "red_flags", "recommended_immediate_actions", "recommended_tests",
            "uncertainty_flags", "disclaimer"
        ]
        for field in required_fields:
            if field not in briefing:
                briefing[field] = "Not available" if isinstance(
                    briefing.get(field, ""), str
                ) else []

        return briefing

    except groq.RateLimitError as e:
        print(f"Groq rate limit (429) — using fallback briefing: {e.status_code}")
        return _fallback_briefing(triage_result)
    except groq.APIConnectionError as e:
        print(f"Groq connection error — using fallback briefing: {e.__cause__}")
        return _fallback_briefing(triage_result)
    except groq.InternalServerError as e:
        print(f"Groq server error (5xx) — using fallback briefing: {e.status_code}")
        return _fallback_briefing(triage_result)
    except Exception as e:
        print(f"LLM call failed unexpectedly — using fallback briefing: {e}")
        return _fallback_briefing(triage_result)


def _fallback_briefing(triage_result: dict) -> dict:
    """Safe fallback when LLM is unavailable. Triage badge still shows correctly."""
    return {
            "triage_level": triage_result["triage_level"],
            "primary_risk_driver": triage_result["risk_driver"],
            "differential_diagnoses": ["Briefing unavailable — triage classification intact"],
            "red_flags": [],
            "recommended_immediate_actions": ["Refer to PHC for evaluation"],
            "recommended_tests": [],
            "uncertainty_flags": "LLM briefing generation failed. Triage classification from ML classifier is valid.",
            "disclaimer": FIXED_DISCLAIMER,
        }
```

---

### Step 2.3 — Wire Up /api/submit

Replace the placeholder `/api/submit` in `main.py` with:

```python
import json as json_lib
from datetime import datetime

from classifier import run_triage
from llm import generate_briefing


@app.post("/api/submit", response_model=SubmitResponse)
async def submit_case(form: IntakeForm, db: Session = Depends(get_db)):
    form_data = form.model_dump()

    # Step 1: Classifier + SHAP (always runs)
    triage_result = run_triage(form_data)

    # Step 2: LLM briefing (may fail gracefully)
    briefing = generate_briefing(form_data, triage_result)

    # Step 3: Write to SQLite (always runs, even if LLM failed)
    record = CaseRecord(
        asha_id=form.asha_id,
        location=form.location,
        patient_age=form.patient_age,
        patient_sex=form.patient_sex,
        chief_complaint=form.chief_complaint,
        complaint_duration=form.complaint_duration,
        bp_systolic=form.bp_systolic,
        bp_diastolic=form.bp_diastolic,
        spo2=form.spo2,
        heart_rate=form.heart_rate,
        temperature=form.temperature,
        symptoms_json=json_lib.dumps(form.symptoms),
        observations=form.observations,
        known_conditions=form.known_conditions,
        current_medications=form.current_medications,
        triage_level=triage_result["triage_level"],
        confidence_score=triage_result["confidence_score"],
        risk_driver=triage_result["risk_driver"],
        briefing_json=json_lib.dumps(briefing),
    )

    db.add(record)
    db.commit()
    db.refresh(record)

    return SubmitResponse(
        case_id=record.id,
        triage_level=triage_result["triage_level"],
        confidence_score=triage_result["confidence_score"],
        risk_driver=triage_result["risk_driver"],
        briefing=briefing,
        status="success",
    )
```

---

### Step 2.4 — Wire Up /api/cases and /api/cases/{id}/review

```python
@app.get("/api/cases")
def get_cases(db: Session = Depends(get_db)):
    # Sort: EMERGENCY first, then URGENT, then ROUTINE, then by time
    triage_order = {"EMERGENCY": 0, "URGENT": 1, "ROUTINE": 2}
    records = db.query(CaseRecord).all()
    records.sort(key=lambda r: (
        triage_order.get(r.triage_level, 9),
        r.created_at
    ), reverse=False)

    result = []
    for r in records:
        briefing = None
        if r.briefing_json:
            try:
                briefing = json_lib.loads(r.briefing_json)
            except Exception:
                briefing = None

        result.append({
            "case_id": r.id,
            "created_at": r.created_at.isoformat(),
            "asha_id": r.asha_id,
            "location": r.location,
            "patient_age": r.patient_age,
            "patient_sex": r.patient_sex,
            "chief_complaint": r.chief_complaint,
            "complaint_duration": r.complaint_duration,
            "triage_level": r.triage_level,
            "risk_driver": r.risk_driver,
            "briefing": briefing,
            "reviewed": r.reviewed,
        })

    return result


@app.patch("/api/cases/{case_id}/review")
def review_case(
    case_id: int,
    update: ReviewUpdate,
    db: Session = Depends(get_db)
):
    record = db.query(CaseRecord).filter(CaseRecord.id == case_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="Case not found")

    record.reviewed = update.reviewed
    record.review_notes = update.review_notes
    db.commit()

    return {"status": "updated"}
```

---

### Step 2.5 — Test the Full Pipeline

With the server running, open `http://localhost:8000/docs` and test `/api/submit` with this body:

```json
{
  "asha_id": "ASHA-001",
  "patient_age": 55,
  "patient_sex": "male",
  "chief_complaint": "Chest pain / tightness",
  "complaint_duration": "2 hours",
  "location": "Rampur Village",
  "bp_systolic": 165,
  "bp_diastolic": 100,
  "spo2": 91,
  "heart_rate": 110,
  "temperature": 37.2,
  "symptoms": ["chest_pain", "breathlessness"],
  "observations": "Patient appears distressed, clutching chest"
}
```

Expected response:
- `triage_level`: `"EMERGENCY"`
- `confidence_score`: > 0.8
- `risk_driver`: A sentence mentioning SpO2 or heart rate
- `briefing`: Full JSON with all required fields
- `status`: `"success"`

Then test `GET /api/cases` — should return an array with the submitted case.

---

### ✅ PHASE 2 DELIVERABLE

- [ ] `POST /api/submit` with the test payload returns a complete response with triage level, risk driver, and briefing
- [ ] `GET /api/cases` returns the submitted case
- [ ] `PATCH /api/cases/1/review` with `{"reviewed": true}` returns `{"status": "updated"}`
- [ ] Server does not crash when `spo2` field is omitted from the submit payload (missing vitals test)
- [ ] Server returns a response even when Groq is slow (verify the fallback by temporarily setting timeout to 0.001 in llm.py, then reverting)
- [ ] `vitalnet.db` contains a record after submission (open with DB Browser for SQLite to verify)

---

---

# PHASE 3 — Frontend: ASHA Intake Form
## Hours 7–11 | Target complete by Hour 11

**Goal:** A React form that submits to the backend and shows a success state with the triage badge. No dashboard yet. One page. One job.

**The temptation to resist:** Building the dashboard simultaneously. Build the form first, confirm end-to-end submission works via the UI, then build the dashboard.

**Mobile-first is non-negotiable.** The ASHA worker uses a phone. Test in Chrome DevTools mobile view throughout.

---

### Step 3.1 — React Project Setup

Open a new terminal (keep the backend terminal running):

```cmd
cd C:\Projects\vitalnet\frontend
npm create vite@latest . -- --template react
npm install
npm install tailwindcss @tailwindcss/vite axios
```

Configure Tailwind — replace `vite.config.js`:

```javascript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
  ],
  server: {
    proxy: {
      '/api': 'http://localhost:8000'
    }
  }
})
```

Add to `src/index.css` (top of file):

```css
@import "tailwindcss";
```

Start the dev server:

```cmd
npm run dev
```

Verify: `http://localhost:5173` loads the default Vite page.

---

### Step 3.2 — App Router Structure

Replace `src/App.jsx`:

```jsx
import { useState } from 'react'
import IntakeForm from './pages/IntakeForm'
import Dashboard from './pages/Dashboard'

export default function App() {
  const [page, setPage] = useState('form')

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Navigation */}
      <nav className="bg-blue-700 text-white px-4 py-3 flex gap-4">
        <span className="font-bold text-lg">VitalNet</span>
        <button
          onClick={() => setPage('form')}
          className={`px-3 py-1 rounded text-sm ${page === 'form' ? 'bg-blue-900' : 'hover:bg-blue-600'}`}
        >
          ASHA Intake
        </button>
        <button
          onClick={() => setPage('dashboard')}
          className={`px-3 py-1 rounded text-sm ${page === 'dashboard' ? 'bg-blue-900' : 'hover:bg-blue-600'}`}
        >
          Doctor Dashboard
        </button>
      </nav>

      {page === 'form' ? <IntakeForm /> : <Dashboard />}
    </div>
  )
}
```

---

### Step 3.3 — Intake Form Page

Create `src/pages/IntakeForm.jsx`:

```jsx
import { useState } from 'react'
import axios from 'axios'

const COMPLAINTS = [
  "Chest pain / tightness",
  "Breathlessness / difficulty breathing",
  "Fever",
  "Abdominal pain",
  "Headache / dizziness",
  "Weakness / fatigue",
  "Altered consciousness / confusion",
  "Seizure",
  "Severe bleeding",
  "Nausea / vomiting",
  "Baby / child unwell",
  "Pregnancy complication",
  "Injury / trauma",
  "Other",
]

const DURATIONS = [
  "Less than 1 hour",
  "1–6 hours",
  "6–24 hours",
  "1–3 days",
  "More than 3 days",
]

const SYMPTOM_OPTIONS = [
  { id: "chest_pain", label: "Chest pain" },
  { id: "breathlessness", label: "Breathlessness" },
  { id: "high_fever", label: "High fever (>102°F)" },
  { id: "altered_consciousness", label: "Altered consciousness" },
  { id: "seizure", label: "Seizure" },
  { id: "severe_bleeding", label: "Severe bleeding" },
  { id: "severe_abdominal_pain", label: "Severe abdominal pain" },
  { id: "persistent_vomiting", label: "Persistent vomiting" },
  { id: "severe_headache", label: "Severe headache" },
  { id: "weakness_one_side", label: "Weakness on one side" },
  { id: "difficulty_speaking", label: "Difficulty speaking" },
  { id: "swelling_face_throat", label: "Swelling of face/throat" },
]

const BADGE_COLORS = {
  EMERGENCY: "bg-red-600 text-white",
  URGENT: "bg-amber-500 text-gray-900",
  ROUTINE: "bg-green-600 text-white",
}

const emptyForm = {
  asha_id: "",
  patient_age: "",
  patient_sex: "",
  chief_complaint: "",
  complaint_duration: "",
  location: "",
  bp_systolic: "",
  bp_diastolic: "",
  spo2: "",
  heart_rate: "",
  temperature: "",
  symptoms: [],
  observations: "",
  known_conditions: "",
  current_medications: "",
}

export default function IntakeForm() {
  const [form, setForm] = useState(emptyForm)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const handleChange = (e) => {
    setForm(prev => ({ ...prev, [e.target.name]: e.target.value }))
  }

  const handleSymptom = (symptomId) => {
    setForm(prev => ({
      ...prev,
      symptoms: prev.symptoms.includes(symptomId)
        ? prev.symptoms.filter(s => s !== symptomId)
        : [...prev.symptoms, symptomId]
    }))
  }

  const handleSubmit = async () => {
    setError(null)

    // Required field validation
    if (!form.asha_id || !form.patient_age || !form.patient_sex ||
        !form.chief_complaint || !form.complaint_duration || !form.location) {
      setError("Please fill all required fields (marked with *)")
      return
    }

    setLoading(true)

    const payload = {
      ...form,
      patient_age: parseInt(form.patient_age),
      bp_systolic: form.bp_systolic ? parseInt(form.bp_systolic) : null,
      bp_diastolic: form.bp_diastolic ? parseInt(form.bp_diastolic) : null,
      spo2: form.spo2 ? parseInt(form.spo2) : null,
      heart_rate: form.heart_rate ? parseInt(form.heart_rate) : null,
      temperature: form.temperature ? parseFloat(form.temperature) : null,
    }

    try {
      const API_BASE = import.meta.env.VITE_API_BASE_URL || ''
      const res = await axios.post(`${API_BASE}/api/submit`, payload)
      setResult(res.data)
      setForm(emptyForm)
    } catch (err) {
      setError(err.response?.data?.detail || "Submission failed. Check connection.")
    } finally {
      setLoading(false)
    }
  }

  if (result) {
    return (
      <div className="max-w-lg mx-auto p-4 mt-6">
        <div className="bg-white rounded-lg shadow p-6 text-center">
          <div className={`inline-block px-4 py-2 rounded-full font-bold text-lg mb-4 ${BADGE_COLORS[result.triage_level]}`}>
            {result.triage_level}
          </div>
          <p className="text-gray-700 mb-2 font-medium">Case #{result.case_id} submitted</p>
          <p className="text-gray-600 text-sm mb-6">{result.risk_driver}</p>
          <button
            onClick={() => setResult(null)}
            className="bg-blue-700 text-white px-6 py-2 rounded-lg font-medium"
          >
            Submit Another Case
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-lg mx-auto p-4 pb-20">
      <h1 className="text-xl font-bold text-gray-800 mt-4 mb-6">Patient Intake Form</h1>

      {error && (
        <div className="bg-red-50 border border-red-300 text-red-700 px-4 py-3 rounded mb-4 text-sm">
          {error}
        </div>
      )}

      {/* ASHA Identity */}
      <Section title="ASHA Details">
        <Field label="ASHA ID *">
          <input name="asha_id" value={form.asha_id} onChange={handleChange}
            placeholder="e.g. ASHA-001" className={inputClass} />
        </Field>
        <Field label="Location / Village *">
          <input name="location" value={form.location} onChange={handleChange}
            placeholder="e.g. Rampur Village" className={inputClass} />
        </Field>
      </Section>

      {/* Patient */}
      <Section title="Patient Details">
        <Field label="Age (years) *">
          <input name="patient_age" type="number" value={form.patient_age}
            onChange={handleChange} placeholder="e.g. 45" className={inputClass} />
        </Field>
        <Field label="Sex *">
          <div className="flex gap-4 mt-1">
            {["male", "female", "other"].map(s => (
              <label key={s} className="flex items-center gap-2 cursor-pointer">
                <input type="radio" name="patient_sex" value={s}
                  checked={form.patient_sex === s} onChange={handleChange} />
                <span className="capitalize text-sm">{s}</span>
              </label>
            ))}
          </div>
        </Field>
      </Section>

      {/* Complaint */}
      <Section title="Chief Complaint">
        <Field label="Primary Complaint *">
          <select name="chief_complaint" value={form.chief_complaint}
            onChange={handleChange} className={inputClass}>
            <option value="">Select complaint</option>
            {COMPLAINTS.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </Field>
        <Field label="Duration *">
          <select name="complaint_duration" value={form.complaint_duration}
            onChange={handleChange} className={inputClass}>
            <option value="">Select duration</option>
            {DURATIONS.map(d => <option key={d} value={d}>{d}</option>)}
          </select>
        </Field>
      </Section>

      {/* Vitals */}
      <Section title="Vitals (optional — record what is available)">
        <div className="grid grid-cols-2 gap-3">
          <Field label="BP Systolic (mmHg)">
            <input name="bp_systolic" type="number" value={form.bp_systolic}
              onChange={handleChange} placeholder="e.g. 120" className={inputClass} />
          </Field>
          <Field label="BP Diastolic (mmHg)">
            <input name="bp_diastolic" type="number" value={form.bp_diastolic}
              onChange={handleChange} placeholder="e.g. 80" className={inputClass} />
          </Field>
          <Field label="SpO2 (%)">
            <input name="spo2" type="number" value={form.spo2}
              onChange={handleChange} placeholder="e.g. 98" className={inputClass} />
          </Field>
          <Field label="Heart Rate (bpm)">
            <input name="heart_rate" type="number" value={form.heart_rate}
              onChange={handleChange} placeholder="e.g. 72" className={inputClass} />
          </Field>
          <Field label="Temperature (°C)">
            <input name="temperature" type="number" step="0.1" value={form.temperature}
              onChange={handleChange} placeholder="e.g. 37.2" className={inputClass} />
          </Field>
        </div>
      </Section>

      {/* Symptoms */}
      <Section title="Symptoms (select all that apply)">
        <div className="grid grid-cols-2 gap-2">
          {SYMPTOM_OPTIONS.map(s => (
            <label key={s.id} className="flex items-center gap-2 cursor-pointer p-2 rounded hover:bg-gray-50">
              <input type="checkbox" checked={form.symptoms.includes(s.id)}
                onChange={() => handleSymptom(s.id)}
                className="w-4 h-4 accent-blue-600" />
              <span className="text-sm text-gray-700">{s.label}</span>
            </label>
          ))}
        </div>
      </Section>

      {/* Observations */}
      <Section title="Observations (optional)">
        <textarea name="observations" value={form.observations} onChange={handleChange}
          placeholder="Any additional observations about the patient's condition..."
          rows={3} className={`${inputClass} resize-none`} maxLength={500} />
        <Field label="Known Conditions">
          <input name="known_conditions" value={form.known_conditions}
            onChange={handleChange} placeholder="e.g. diabetes, hypertension"
            className={inputClass} />
        </Field>
        <Field label="Current Medications">
          <input name="current_medications" value={form.current_medications}
            onChange={handleChange} placeholder="e.g. metformin, amlodipine"
            className={inputClass} />
        </Field>
      </Section>

      {/* Submit */}
      <button
        onClick={handleSubmit}
        disabled={loading}
        className="w-full bg-blue-700 text-white py-4 rounded-lg font-bold text-lg mt-4 disabled:opacity-60 active:bg-blue-800"
      >
        {loading ? "Submitting..." : "Submit Case"}
      </button>
    </div>
  )
}

// Utility components
const inputClass = "w-full border border-gray-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-blue-500 bg-white"

function Section({ title, children }) {
  return (
    <div className="mb-6">
      <h2 className="text-sm font-semibold text-blue-700 uppercase tracking-wide mb-3 border-b border-blue-100 pb-1">
        {title}
      </h2>
      <div className="space-y-3">{children}</div>
    </div>
  )
}

function Field({ label, children }) {
  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      {children}
    </div>
  )
}
```

---

### Step 3.4 — Create Empty Dashboard Placeholder

Create `src/pages/Dashboard.jsx`:

```jsx
export default function Dashboard() {
  return (
    <div className="max-w-2xl mx-auto p-4 mt-6">
      <p className="text-gray-500 text-center">Dashboard — coming in Phase 4</p>
    </div>
  )
}
```

---

### Step 3.5 — End-to-End Test via UI

1. Open `http://localhost:5173`
2. Fill the form with the cardiac case (55M, chest pain, SpO2 91%)
3. Click Submit
4. Verify the success state shows EMERGENCY badge and risk driver sentence

**Test missing vitals:** Submit a case with no vitals fields filled. Should still succeed with a valid triage level.

---

### ✅ PHASE 3 DELIVERABLE

- [ ] React app loads at `http://localhost:5173`
- [ ] Form submits successfully and shows triage badge in success state
- [ ] Form resets after successful submission
- [ ] Error state shows when required fields are missing
- [ ] Missing vitals submission works (no 422 error)
- [ ] Form is usable on mobile view in Chrome DevTools (375px width)
- [ ] Network tab in browser DevTools shows `POST /api/submit` returning 200

---

---

# PHASE 4 — Frontend: Doctor Dashboard
## Hours 11–15 | Target complete by Hour 15

**Goal:** The doctor dashboard fetches all cases from `/api/cases`, sorts them by triage level, and renders a briefing card for each case. The Mark Reviewed button works.

**The temptation to resist:** Design polish at this stage. The card must be functional and readable. It does not need to be beautiful yet. Beauty is Phase 5.

---

### Step 4.1 — Triage Badge Component

Create `src/components/TriageBadge.jsx`:

```jsx
const COLORS = {
  EMERGENCY: "bg-red-600 text-white",
  URGENT: "bg-amber-500 text-gray-900",
  ROUTINE: "bg-green-600 text-white",
}

export default function TriageBadge({ level }) {
  return (
    <span className={`inline-block px-3 py-1 rounded-full text-sm font-bold ${COLORS[level] || "bg-gray-200 text-gray-700"}`}>
      {level}
    </span>
  )
}
```

---

### Step 4.2 — Briefing Card Component

Create `src/components/BriefingCard.jsx`:

```jsx
import { useState } from 'react'
import axios from 'axios'
import TriageBadge from './TriageBadge'

export default function BriefingCard({ caseData, onReviewed }) {
  const [expanded, setExpanded] = useState(caseData.triage_level === 'EMERGENCY')
  const [marking, setMarking] = useState(false)
  const [reviewed, setReviewed] = useState(caseData.reviewed)

  const b = caseData.briefing

  const handleMarkReviewed = async () => {
    setMarking(true)
    try {
      await axios.patch(`${import.meta.env.VITE_API_BASE_URL || ''}/api/cases/${caseData.case_id}/review`, { reviewed: true })
      setReviewed(true)
      if (onReviewed) onReviewed(caseData.case_id)
    } catch (e) {
      console.error("Review update failed", e)
    } finally {
      setMarking(false)
    }
  }

  const timeStr = new Date(caseData.created_at).toLocaleTimeString([], {
    hour: '2-digit', minute: '2-digit'
  })

  return (
    <div className={`bg-white rounded-lg shadow border-l-4 mb-4 overflow-hidden
      ${caseData.triage_level === 'EMERGENCY' ? 'border-red-500' :
        caseData.triage_level === 'URGENT' ? 'border-amber-500' : 'border-green-500'}
      ${reviewed ? 'opacity-70' : ''}
    `}>
      {/* Header — always visible */}
      <div
        className="p-4 cursor-pointer flex items-start justify-between"
        onClick={() => setExpanded(!expanded)}
      >
        <div className="flex-1">
          <div className="flex items-center gap-2 mb-1">
            <TriageBadge level={caseData.triage_level} />
            {reviewed && (
              <span className="text-xs text-gray-500 bg-gray-100 px-2 py-0.5 rounded">
                Reviewed
              </span>
            )}
          </div>
          <p className="text-sm font-medium text-gray-800">
            {caseData.patient_age}
            {caseData.patient_sex === 'male' ? 'M' : caseData.patient_sex === 'female' ? 'F' : ''}
            {" · "}{caseData.location}
          </p>
          <p className="text-sm text-gray-600">{caseData.chief_complaint}</p>
          <p className="text-xs text-gray-400 mt-1">
            {timeStr} · ASHA {caseData.asha_id}
          </p>
        </div>
        <span className="text-gray-400 ml-2">{expanded ? "▲" : "▼"}</span>
      </div>

      {/* Expanded briefing */}
      {expanded && b && (
        <div className="px-4 pb-4 border-t border-gray-100 pt-3 space-y-3">

          <BriefingSection title="Primary Signal">
            <p className="text-sm text-gray-700">{b.primary_risk_driver}</p>
          </BriefingSection>

          <BriefingSection title="Differential Diagnoses">
            <ul className="text-sm text-gray-700 space-y-1">
              {(b.differential_diagnoses || []).map((d, i) => (
                <li key={i} className="flex gap-2">
                  <span className="text-blue-500 font-bold">{i + 1}.</span> {d}
                </li>
              ))}
            </ul>
          </BriefingSection>

          {b.red_flags?.length > 0 && (
            <BriefingSection title="⚠ Red Flags">
              <ul className="text-sm text-red-700 space-y-1">
                {b.red_flags.map((f, i) => (
                  <li key={i}>· {f}</li>
                ))}
              </ul>
            </BriefingSection>
          )}

          <BriefingSection title="Immediate Actions">
            <ul className="text-sm text-gray-700 space-y-1">
              {(b.recommended_immediate_actions || []).map((a, i) => (
                <li key={i} className="flex gap-2">
                  <span className="text-green-600">→</span> {a}
                </li>
              ))}
            </ul>
          </BriefingSection>

          {b.recommended_tests?.length > 0 && (
            <BriefingSection title="Recommended Tests">
              <ul className="text-sm text-gray-700 space-y-1">
                {b.recommended_tests.map((t, i) => (
                  <li key={i}>· {t}</li>
                ))}
              </ul>
            </BriefingSection>
          )}

          <BriefingSection title="Uncertainty Flags">
            <p className="text-sm text-amber-700">{b.uncertainty_flags}</p>
          </BriefingSection>

          {/* Disclaimer — non-removable */}
          <div className="bg-gray-50 border border-gray-200 rounded p-2">
            <p className="text-xs text-gray-500">⚠ {b.disclaimer}</p>
          </div>

          {/* Actions */}
          {!reviewed && (
            <button
              onClick={handleMarkReviewed}
              disabled={marking}
              className="w-full bg-blue-700 text-white py-2.5 rounded-lg text-sm font-medium disabled:opacity-60 mt-2"
            >
              {marking ? "Updating..." : "Mark Reviewed"}
            </button>
          )}
        </div>
      )}
    </div>
  )
}

function BriefingSection({ title, children }) {
  return (
    <div>
      <p className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-1">{title}</p>
      {children}
    </div>
  )
}
```

---

### Step 4.3 — Dashboard Page

Replace `src/pages/Dashboard.jsx`:

```jsx
import { useState, useEffect } from 'react'
import axios from 'axios'
import BriefingCard from '../components/BriefingCard'

export default function Dashboard() {
  const [cases, setCases] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchCases = async () => {
    try {
      const API_BASE = import.meta.env.VITE_API_BASE_URL || ''
      const res = await axios.get(`${API_BASE}/api/cases`)
      setCases(res.data)
      setError(null)
    } catch (e) {
      setError("Failed to load cases. Check backend connection.")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchCases()
    // Poll every 30 seconds
    const interval = setInterval(fetchCases, 30000)
    return () => clearInterval(interval)
  }, [])

  const emergency = cases.filter(c => c.triage_level === 'EMERGENCY')
  const urgent = cases.filter(c => c.triage_level === 'URGENT')
  const routine = cases.filter(c => c.triage_level === 'ROUTINE')

  if (loading) {
    return (
      <div className="max-w-2xl mx-auto p-4 mt-8 text-center text-gray-500">
        Loading cases...
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto p-4 mt-4">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-xl font-bold text-gray-800">Doctor Dashboard</h1>
        <button onClick={fetchCases} className="text-sm text-blue-600 hover:underline">
          Refresh
        </button>
      </div>

      {error && (
        <div className="bg-red-50 border border-red-300 text-red-700 px-4 py-3 rounded mb-4 text-sm">
          {error}
        </div>
      )}

      {cases.length === 0 && !error && (
        <div className="text-center text-gray-500 mt-12">
          <p className="text-lg">No cases yet</p>
          <p className="text-sm mt-1">Cases submitted via the ASHA intake form will appear here</p>
        </div>
      )}

      {/* Emergency first */}
      {emergency.length > 0 && (
        <div className="mb-6">
          <h2 className="text-sm font-bold text-red-600 uppercase tracking-wide mb-2">
            Emergency ({emergency.length})
          </h2>
          {emergency.map(c => (
            <BriefingCard key={c.case_id} caseData={c} onReviewed={fetchCases} />
          ))}
        </div>
      )}

      {urgent.length > 0 && (
        <div className="mb-6">
          <h2 className="text-sm font-bold text-amber-600 uppercase tracking-wide mb-2">
            Urgent ({urgent.length})
          </h2>
          {urgent.map(c => (
            <BriefingCard key={c.case_id} caseData={c} onReviewed={fetchCases} />
          ))}
        </div>
      )}

      {routine.length > 0 && (
        <div className="mb-6">
          <h2 className="text-sm font-bold text-green-700 uppercase tracking-wide mb-2">
            Routine ({routine.length})
          </h2>
          {routine.map(c => (
            <BriefingCard key={c.case_id} caseData={c} onReviewed={fetchCases} />
          ))}
        </div>
      )}
    </div>
  )
}
```

---

### ✅ PHASE 4 DELIVERABLE

- [ ] Dashboard loads and displays submitted cases sorted by triage level
- [ ] Emergency cards are expanded by default; Urgent and Routine are collapsed
- [ ] Briefing card shows all sections: primary signal, differentials, red flags, actions, tests, uncertainty, disclaimer
- [ ] Mark Reviewed button updates the card state without page reload
- [ ] Dashboard auto-refreshes every 30 seconds (submit a case and wait — it should appear without manual refresh)
- [ ] Dashboard works on mobile view (375px)

---

---

# PHASE 5 — Polish and Hardening
## Hours 15–18 | Target complete by Hour 18

**Goal:** Close all rough edges. Verify the complete flow works end-to-end. Fix any bugs discovered during testing. Light visual polish — not a redesign.

**The temptation to resist:** New features. If you think "I should add X" during this phase, write it down and add it after the sprint. Adding features at hour 15 is how sprints fail.

---

### Step 5.1 — Loading States and Error Handling

Verify every async operation has a visible loading state and a non-crashing error state:

- Form submit button shows "Submitting..." during the API call
- Dashboard shows "Loading cases..." on first load
- Network failure during dashboard fetch shows error message, does not crash

**Test network failure:** Stop the FastAPI server while the dashboard is open. Verify the dashboard shows an error message and does not show a blank white page.

---

### Step 5.2 — Mobile Testing Checklist

Open Chrome DevTools → Toggle Device Toolbar → iPhone SE (375px):

- [ ] Form fields have minimum tap target height of 44px
- [ ] Submit button is full width and easily tappable
- [ ] No horizontal scroll on any page
- [ ] Text is readable without zooming
- [ ] Dashboard cards are readable at 375px width
- [ ] Briefing card sections don't overflow

---

### Step 5.3 — Edge Cases to Verify

Test each of these manually:

1. **All vitals missing** — submit a form with only required fields. Should return a valid ROUTINE or URGENT case.
2. **Groq timeout simulation** — temporarily set timeout to 0.001 in `llm.py`. Submit a case. The response should return with fallback briefing, triage badge still visible.
3. **Very young patient** — submit with age 2, chief complaint "Baby / child unwell", altered_consciousness checked. Should return EMERGENCY.
4. **Multiple rapid submissions** — submit three cases in quick succession. All should appear in the dashboard.
5. **PATCH after refresh** — mark a case as reviewed, refresh the page. The "Reviewed" tag should persist.

---

### Step 5.4 — README

Create `README.md` in the project root:

```markdown
# VitalNet — AI Diagnostic Layer

Clinical intelligence bridge between ASHA workers in the field and PHC doctors at the clinic.

## What it does

An ASHA worker fills a structured intake form on her Android phone. A doctor receives a structured clinical briefing with triage classification before the patient arrives.

## Flow

ASHA Form → FastAPI → GBM Classifier → SHAP → Groq LLM → SQLite → Doctor Dashboard

## Stack

- Backend: FastAPI + Python 3.13, scikit-learn, SHAP, Groq SDK, SQLite
- Frontend: React 18, Vite, Tailwind CSS
- Deployment: Railway (backend), Vercel (frontend)

## Run locally

Backend:
```
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Frontend:
```
cd frontend
npm install
npm run dev
```

## Architecture decisions

See `/backend/prompts/clinical_system_prompt.txt` for the three-layer prompt architecture.
Classifier trained on synthetic data — validation metrics in training notebook at `/colab/`.
```

---

### ✅ PHASE 5 DELIVERABLE

- [ ] All five edge cases from Step 5.3 pass without crashes
- [ ] Mobile display passes all checks in Step 5.2
- [ ] README exists and describes how to run the project
- [ ] Full end-to-end flow works: form → submit → dashboard displays briefing card → mark reviewed → persists on refresh

---

---

# PHASE 6 — Deployment
## Hours 18–22 | Target complete by Hour 22

**Goal:** Live URLs. One for the backend on Railway, one for the frontend on Vercel. Both work from a phone browser with zero local setup.

**The temptation to resist:** Debugging deployment while local isn't working. Deployment only starts when Phase 5 deliverables are all checked. Deploying broken code to Railway wastes 30 minutes per iteration.

---

### Step 6.1 — Dockerfile

Create `backend\Dockerfile`:

```dockerfile
FROM python:3.13-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

Create `backend\.dockerignore`:

```
.env
venv/
__pycache__/
*.pyc
vitalnet.db
*.log
```

---

### Step 6.2 — Railway Deployment

1. Go to railway.app → New Project → Deploy from GitHub repo
2. Select your repo → select `backend` as the root directory
3. Railway auto-detects Dockerfile
4. In Railway dashboard → Variables, add:
   ```
   GROQ_API_KEY=your_key
   DATABASE_URL=sqlite:///./vitalnet.db
   ENVIRONMENT=production
   ```
5. Add your Vercel URL once you have it:
   ```
   FRONTEND_URL=https://your-app.vercel.app
   ```
6. Railway builds and deploys automatically on every push to main

**Test Railway URL:**
```
https://your-app.railway.app/api/health
```
Expected: `{"status": "ok", "classifier": "loaded", "db": "connected"}`

**If Railway build fails:** Check build logs. Most common failures:
- `triage_classifier.pkl` not in repo — verify it was committed
- Package version conflict — check requirements.txt against Python 3.13 compatibility
- Missing environment variable — check Railway Variables dashboard

---

### Step 6.3 — Vercel Deployment

**No `vite.config.js` changes needed.** The `API_BASE` pattern was built into all frontend axios calls from Phase 3. The Vite dev proxy handles local development (`/api` → `localhost:8000`), and the `VITE_API_BASE_URL` env var handles production routing on Vercel. Do not remove the proxy — it is harmless in production builds and keeps local dev working.

3. Go to vercel.com → New Project → Import from GitHub
4. Select the repo → set **Root Directory** to `frontend`
5. In Environment Variables, add:
   ```
   VITE_API_BASE_URL=https://your-app.railway.app
   ```
6. Deploy

**Test Vercel URL on your phone browser** — open the URL, fill the form, submit a case, check the dashboard.

---

### Step 6.4 — Update Railway CORS

Now that you have the Vercel URL, update the CORS configuration in `main.py`:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://your-actual-app.vercel.app",  # Update this
    ],
    ...
)
```

Push to GitHub → Railway redeploys automatically.

---

### ✅ PHASE 6 DELIVERABLE

- [ ] `https://your-app.railway.app/api/health` returns 200 from a browser on your phone
- [ ] `https://your-app.vercel.app` renders the intake form on your phone browser
- [ ] Submit a case via the Vercel URL — it appears on the dashboard via the Railway backend
- [ ] Mark Reviewed works via the deployed URLs
- [ ] No CORS errors in browser console

---

---

# PHASE 7 — Verification and Wrap
## Hours 22–24 | Final phase

**Goal:** Complete the definition of done checklist. Record the latency numbers. Clean up the repository.

---

### Step 7.1 — Definition of Done

Run through every item. No partial credit.

- [ ] `GET /api/health` returns `{"status": "ok", "classifier": "loaded", "db": "connected"}`
- [ ] Submitting the intake form via the React UI creates a record in SQLite
- [ ] The classifier returns a triage level for every submission
- [ ] The SHAP explainer returns a plain-English risk driver sentence
- [ ] The Groq LLM returns a valid briefing JSON matching the output schema
- [ ] The doctor dashboard displays the submitted case with triage badge and briefing card
- [ ] The "Mark Reviewed" button updates the case record in SQLite and persists on refresh
- [ ] The deployed Railway URL returns a valid API response
- [ ] The deployed Vercel URL renders the intake form and dashboard
- [ ] End-to-end flow works on mobile browser (test on your actual phone)

---

### Step 7.2 — Record Your Numbers

Measure and record before closing the laptop:

- Classifier accuracy: \_\_\_\_% (from Colab training output)
- Emergency false negatives: \_\_\_\_ (from Colab confusion matrix)
- End-to-end latency (form submit → briefing visible): \_\_\_\_ seconds (measure with stopwatch 3 times, take average)
- Railway backend URL: \_\_\_\_
- Vercel frontend URL: \_\_\_\_

---

### Step 7.3 — Final Commit

```cmd
git add .
git commit -m "feat: complete 24hr sprint — deployed VitalNet AI Diagnostic Layer"
git push
```

---

### ✅ SPRINT COMPLETE

When all ten Definition of Done items are checked and the numbers are recorded, the sprint is done.

---

---

## WHAT HAPPENS AFTER THE SPRINT

These are the refinements that follow. Do not think about them during the sprint.

**Phase 2 features (next sprint or hackathon):**
- Sarvam AI voice input with Whisper fallback
- Three-tier LLM fallback chain (Groq → Gemini Flash → Flash-Lite → cached)
- Hindi and Tamil form localization
- Emergency SMS notification via Twilio + Android `sms:` URI offline fallback
- ONNX browser-side classifier inference

**Portfolio additions:**
- 60-second demo video (form → Emergency triage → briefing card)
- Architecture diagram slide
- Classifier validation metrics displayed on dashboard health page

**Before any competition submission:**
- Run full adversarial review using the three audit files
- Verify the GitHub repo has the system prompt at the committed path
- Record fresh latency and accuracy numbers

---

## ABSOLUTE DO NOT LIST

These apply for the entire 24 hours. No exceptions.

- **Do not add voice input** — it breaks the scope and will consume 4 hours
- **Do not implement authentication** — no JWT, no login page, no sessions
- **Do not run Tailwind build separately** — Vite + `@tailwindcss/vite` handles it
- **Do not use `async` in SQLAlchemy without the async engine** — use the sync engine configured in Phase 1
- **Do not move to the next phase without checking the deliverable** — a broken foundation compounds
- **Do not install packages globally** — always inside the virtual environment
- **Do not commit `.env`** — API keys stay local and in Railway/Vercel dashboards
- **Do not retrain the classifier** — the `.pkl` is committed once in pre-sprint
- **Do not add a fourth page or route** — two pages only: intake form and dashboard
- **Do not skip the mobile test** — the ASHA worker uses a phone, not a laptop

---

*Sprint plan version: 1.0*
*Project: VitalNet — AI Diagnostic Layer*
*Total duration: 24 hours from Hour 0*
*Dev machine: Windows 10 | Python 3.13.7 | Node v22.17.0*
