from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
import json as json_lib
import os
from dotenv import load_dotenv

from database import init_db, get_db, CaseRecord
from classifier import load_classifier, run_triage
from llm import generate_briefing
from schemas import IntakeForm, SubmitResponse, ReviewUpdate

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    load_classifier()
    print("[OK] VitalNet API started")
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


# ── Health Check ───────────────────────────────────────────────────────────

@app.get("/api/health")
def health_check():
    return {
        "status": "ok",
        "classifier": "loaded",
        "db": "connected"
    }


# ── Submit Case ────────────────────────────────────────────────────────────

@app.post("/api/submit", response_model=SubmitResponse)
async def submit_case(form: IntakeForm, db: Session = Depends(get_db)):
    form_data = form.model_dump()

    # Step 1: Classifier + SHAP (always runs — LLM-independent)
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


# ── Get Cases ──────────────────────────────────────────────────────────────

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
            "created_at": r.created_at.isoformat() if r.created_at else None,
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


# ── Review Case ────────────────────────────────────────────────────────────

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
