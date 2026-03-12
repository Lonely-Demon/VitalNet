from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
import os
import uuid as uuid_lib
from datetime import datetime, timezone
from dotenv import load_dotenv

from database import supabase, get_supabase_for_user
from classifier import load_classifier, run_triage
from llm import generate_briefing
from auth import get_current_user, require_role
from schemas import IntakeForm

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_classifier()
    print("[OK] VitalNet API started")
    yield


app = FastAPI(title="VitalNet API", version="0.2.0", lifespan=lifespan)

# CORS — restricted to known origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        'http://localhost:5173',
        os.getenv('FRONTEND_URL', ''),
    ],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


# ── Health Check ───────────────────────────────────────────────────────────

@app.get('/api/health')
async def health():
    try:
        supabase.table('facilities').select('id').limit(1).execute()
        db_status = 'connected'
    except Exception as e:
        db_status = f'error: {str(e)}'
    return {
        'status': 'ok',
        'database': db_status,
        'classifier': 'loaded',
    }


# ── Submit Case ────────────────────────────────────────────────────────────

@app.post('/api/submit')
async def submit_case(
    form: IntakeForm,
    authorization: str = Header(None),
    user: dict = Depends(require_role('asha_worker', 'admin')),
):
    form_data = form.model_dump()

    # Step 1: Classifier + SHAP (always runs — LLM-independent)
    triage_result = run_triage(form_data)

    # Step 2: LLM briefing (may fail gracefully)
    briefing = generate_briefing(form_data, triage_result)

    # Step 3: Write to Supabase via user-scoped client (RLS enforced)
    raw_token = authorization.split(' ', 1)[1]
    db = get_supabase_for_user(raw_token)

    record = {
        'client_id':           str(form.client_id or uuid_lib.uuid4()),
        'submitted_by':        user['sub'],
        'facility_id':         user.get('user_metadata', {}).get('facility_id') or None,
        'patient_age':         form.patient_age,
        'patient_sex':         form.patient_sex,
        'patient_location':    form.location,
        'bp_systolic':         form.bp_systolic,
        'bp_diastolic':        form.bp_diastolic,
        'spo2':                form.spo2,
        'heart_rate':          form.heart_rate,
        'temperature':         float(form.temperature) if form.temperature is not None else None,
        'chief_complaint':     form.chief_complaint,
        'complaint_duration':  form.complaint_duration,
        'symptoms':            form.symptoms or [],
        'observations':        form.observations,
        'known_conditions':    form.known_conditions,
        'current_medications': form.current_medications,
        'triage_level':        triage_result['triage_level'],
        'triage_confidence':   triage_result['confidence_score'],
        'risk_driver':         triage_result['risk_driver'],
        'briefing':            briefing,
        'llm_model_used':      briefing.get('_model_used', 'unknown'),
        'created_offline':     False,
        'client_submitted_at': form.client_submitted_at.isoformat() if form.client_submitted_at else None,
    }

    result = db.table('case_records').insert(record).execute()
    return result.data[0]


# ── Get Cases ──────────────────────────────────────────────────────────────

@app.get('/api/cases')
async def get_cases(
    authorization: str = Header(None),
    user: dict = Depends(require_role('doctor', 'admin')),
):
    raw_token = authorization.split(' ', 1)[1]
    db = get_supabase_for_user(raw_token)

    result = (
        db.table('case_records')
        .select('*')
        .is_('deleted_at', 'null')
        .order('created_at', desc=True)
        .execute()
    )
    cases = result.data
    order = {'EMERGENCY': 0, 'URGENT': 1, 'ROUTINE': 2}
    cases.sort(key=lambda c: order.get(c.get('triage_level', 'ROUTINE'), 2))
    return cases


# ── Review Case ────────────────────────────────────────────────────────────

@app.patch('/api/cases/{case_id}/review')
async def review_case(
    case_id: str,
    authorization: str = Header(None),
    user: dict = Depends(require_role('doctor', 'admin')),
):
    raw_token = authorization.split(' ', 1)[1]
    db = get_supabase_for_user(raw_token)

    db.table('case_records').update({
        'reviewed_by': user['sub'],
        'reviewed_at': datetime.now(timezone.utc).isoformat(),
    }).eq('id', case_id).execute()
    return {'status': 'reviewed'}
