from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
import os
import uuid as uuid_lib
from datetime import datetime, timezone
from dotenv import load_dotenv

from database import supabase_anon, get_supabase_for_user
from admin_routes import router as admin_router
from analytics_routes import router as analytics_router
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
app.include_router(admin_router)
app.include_router(analytics_router)

# CORS — restricted to known origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        os.getenv("FRONTEND_URL", "").rstrip("/"),
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health Check ───────────────────────────────────────────────────────────


@app.get("/api/health")
async def health():
    try:
        supabase_anon.table("facilities").select("id").limit(1).execute()
        db_status = "connected"
    except Exception as e:
        db_status = f"error: {str(e)}"
    return {
        "status": "ok",
        "database": db_status,
        "classifier": "loaded",
    }


# ── Submit Case ────────────────────────────────────────────────────────────


@app.post("/api/submit")
async def submit_case(
    form: IntakeForm,
    authorization: str = Header(None),
    user: dict = Depends(require_role("asha_worker", "admin")),
):
    form_data = form.model_dump()

    # Step 1: Classifier + SHAP (always runs — LLM-independent)
    try:
        triage_result = run_triage(form_data)
        briefing = await generate_briefing(form_data, triage_result)
        raw_token = (authorization or "").split(" ", 1)[-1]
        db = get_supabase_for_user(raw_token)
        
        record = {
            "client_id": str(form.client_id or uuid_lib.uuid4()),
            "submitted_by": user["sub"],
            "facility_id": user.get("user_metadata", {}).get("facility_id") or None,
            "patient_name": form.patient_name,
            "patient_age": form.patient_age,
            "patient_sex": form.patient_sex,
            "patient_location": form.location,
            "bp_systolic": form.bp_systolic,
            "bp_diastolic": form.bp_diastolic,
            "spo2": form.spo2,
            "heart_rate": form.heart_rate,
            "temperature": float(form.temperature)
            if form.temperature is not None
            else None,
            "chief_complaint": form.chief_complaint,
            "complaint_duration": form.complaint_duration,
            "symptoms": form.symptoms or [],
            "observations": form.observations,
            "known_conditions": form.known_conditions,
            "current_medications": form.current_medications,
            "triage_level": triage_result["triage_level"],
            "triage_confidence": triage_result["confidence_score"],
            "risk_driver": triage_result["risk_driver"],
            "briefing": briefing,
            "llm_model_used": briefing.get("_model_used", "unknown"),
            "created_offline": form.created_offline,
            "client_submitted_at": form.client_submitted_at.isoformat()
            if form.client_submitted_at
            else None,
        }

        result = (
            db.table("case_records")
            .upsert(record, on_conflict="client_id", ignore_duplicates=True)
            .execute()
        )
        if not result.data:
            # Upsert ignored the duplicate; fetch the existing row to return to client
            existing = db.table("case_records").select("*").eq("client_id", record["client_id"]).execute()
            return existing.data[0] if existing.data else record
        return result.data[0]
    except Exception as e:
        import traceback
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail={"error": str(e), "traceback": traceback.format_exc()})


# ── Get Cases ──────────────────────────────────────────────────────────────


@app.get("/api/cases")
async def get_cases(
    authorization: str = Header(None),
    user: dict = Depends(require_role("doctor", "admin")),
    before: str = None,   # ISO timestamp cursor — fetch cases older than this
    limit: int = 25,      # Page size; capped at 100 to prevent abuse
):
    """
    Cursor-based pagination for the Doctor Dashboard.
    Use `before=<created_at ISO string>` to fetch the next page.
    Each page returns up to `limit` cases sorted EMERGENCY → URGENT → ROUTINE,
    then by created_at DESC within each tier.

    Unlike offset pagination, this is safe alongside Supabase Realtime:
    new inserts at the top of the queue don't shift rows into already-fetched pages.
    """
    raw_token = (authorization or "").split(" ", 1)[-1]
    db = get_supabase_for_user(raw_token)

    # Safety cap
    limit = max(1, min(limit, 100))

    query = (
        db.table("case_records")
        .select("id, patient_name, patient_age, patient_sex, triage_level, triage_confidence, risk_driver, created_at, reviewed_at, reviewed_by, facility_id, created_offline")
        .is_("deleted_at", "null")
        .order("created_at", desc=True)
        .limit(limit + 1)   # Fetch one extra to determine hasMore
    )

    if before:
        # Fetch rows strictly older than the cursor timestamp
        query = query.lt("created_at", before)

    result = query.execute()
    rows = result.data

    has_more = len(rows) > limit
    cases = rows[:limit]

    # Sort fetched page by triage priority (EMERGENCY first), then by created_at DESC
    order = {"EMERGENCY": 0, "URGENT": 1, "ROUTINE": 2}
    cases.sort(key=lambda c: (order.get(c.get("triage_level", "ROUTINE"), 2)))

    return {
        "cases": cases,
        "hasMore": has_more,
        # Cursor for next page — oldest created_at in this batch
        "nextCursor": cases[-1]["created_at"] if has_more and cases else None,
    }



# ── Review Case ────────────────────────────────────────────────────────────


@app.patch("/api/cases/{case_id}/review")
async def review_case(
    case_id: str,
    authorization: str = Header(None),
    user: dict = Depends(require_role("doctor", "admin")),
):
    raw_token = (authorization or "").split(" ", 1)[-1]
    db = get_supabase_for_user(raw_token)

    db.table("case_records").update(
        {
            "reviewed_by": user["sub"],
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        }
    ).eq("id", case_id).execute()
    return {"status": "reviewed"}


# ── ASHA: My Submissions ───────────────────────────────────────────────────


@app.get("/api/cases/mine")
async def get_my_cases(
    authorization: str = Header(None),
    user: dict = Depends(require_role("asha_worker", "admin")),
):
    """
    Returns only the calling user's own submitted cases.
    RLS enforces this at DB level; the explicit filter is for clarity.
    Returns a limited column set — full briefing JSONB is doctor-facing only.
    """
    raw_token = (authorization or "").split(" ", 1)[-1]
    db = get_supabase_for_user(raw_token)
    result = (
        db.table("case_records")
        .select(
            "id, chief_complaint, triage_level, created_at, reviewed_at, patient_age, patient_sex"
        )
        .eq("submitted_by", user["sub"])
        .is_("deleted_at", "null")
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


# ── Get Case Detail ───────────────────────────────────────────────────────────


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
