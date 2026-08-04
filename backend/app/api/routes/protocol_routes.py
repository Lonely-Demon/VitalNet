"""
Protocol Routes — a grounded, non-clinical guideline lookup assistant
(docs/DECISIONS.md §27), informed by ASHABot's own published design
(Khushi Baby + Microsoft Research India, CHI 2025).

Structurally separate from the triage pipeline: never takes patient
vitals/symptoms as input, never produces a triage-like output — the LLM
call (app/services/llm.py::generate_protocol_answer) uses its own
context-stuffed knowledge base and refuses patient-specific questions.

Unlike case_records, `protocol_questions` carries no PHI at all, so it uses
genuine Postgres RLS via get_supabase_for_user — NOT the supabase_admin
aggregate-only exception used by supervisor_routes.py/outbreak_routes.py.
The SELECT policy is intentionally facility-wide for every role (asha_worker
included): that's what makes a shared, growing FAQ possible.
"""
import logging
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.auth import require_role
from app.core.database import get_supabase_for_user, extract_bearer_token
from app.services.llm import generate_protocol_answer
from app.api.routes.cases import limiter

logger = logging.getLogger("vitalnet")

router = APIRouter(prefix="/api/protocol", tags=["protocol"])

ALL_ROLES = ("asha_worker", "doctor", "supervisor", "admin")
CURATOR_ROLES = ("doctor", "supervisor", "admin")


class AskProtocolQuestionRequest(BaseModel):
    question_text: str = Field(min_length=1, max_length=500)
    language: Literal["en", "hi", "ta"] = "en"


class CurateProtocolAnswerRequest(BaseModel):
    curator_answer_text: str = Field(min_length=1, max_length=2000)


@router.post("/ask")
@limiter.limit("20/minute")
async def ask_protocol_question(
    request: Request,
    body: AskProtocolQuestionRequest,
    authorization: str = Header(None),
    user: dict = Depends(require_role(*ALL_ROLES)),
):
    """
    Asks a general protocol/guideline question. Answered inline when the LLM
    finds it in the curated reference material; otherwise queued for
    asynchronous curation by a supervisor/doctor/admin at the same facility
    — never a synchronous multi-reviewer gate (ASHABot's own published data
    found that mechanism averaged ~60h, too slow to be useful).
    """
    facility_id = user.get("resolved_facility_id")
    if not facility_id:
        raise HTTPException(status_code=400, detail="Account has no facility assigned")

    raw_token = extract_bearer_token(authorization)
    db = get_supabase_for_user(raw_token)

    result = await generate_protocol_answer(body.question_text, body.language)

    row = {
        "asked_by": user.get("sub"),
        "facility_id": facility_id,
        "question_text": body.question_text,
        "language": body.language,
        "llm_answer_text": result["answer"],
        "llm_grounded": result["grounded"],
        "status": "answered" if result["grounded"] else "pending_curation",
    }

    try:
        res = db.table("protocol_questions").insert(row).execute()
    except Exception as e:
        logger.warning("Protocol question insert failed: %s", e)
        raise HTTPException(status_code=502, detail="Could not save your question — try again")

    return (res.data or [row])[0]


@router.get("/questions")
@limiter.limit("60/minute")
async def list_protocol_questions(
    request: Request,
    status: Optional[Literal["answered", "pending_curation", "curated"]] = None,
    facility_id: Optional[str] = None,
    authorization: str = Header(None),
    user: dict = Depends(require_role(*ALL_ROLES)),
):
    """
    Lists protocol questions visible to the caller — the shared, growing
    facility FAQ. RLS (protocol_questions_select_policy) is the real access
    boundary: facility-wide for every role, or global for admin; the
    `facility_id`/`status` params here are just query narrowing, not an
    access grant.
    """
    raw_token = extract_bearer_token(authorization)
    db = get_supabase_for_user(raw_token)

    query = db.table("protocol_questions").select("*").order("created_at", desc=True)
    if status:
        query = query.eq("status", status)
    if facility_id:
        query = query.eq("facility_id", facility_id)

    try:
        res = query.execute()
    except Exception as e:
        logger.warning("Protocol question list query failed: %s", e)
        raise HTTPException(status_code=502, detail="Could not load questions — try again")

    return {"questions": res.data or []}


@router.patch("/questions/{question_id}/curate")
@limiter.limit("30/minute")
async def curate_protocol_answer(
    request: Request,
    question_id: str,
    body: CurateProtocolAnswerRequest,
    authorization: str = Header(None),
    user: dict = Depends(require_role(*CURATOR_ROLES)),
):
    """
    Records a human curator's answer for a question the LLM couldn't
    ground. RLS (protocol_questions_update_policy) is the real access
    boundary — a supervisor/doctor can only reach rows at their own
    facility; require_role here is a clean 403 for other roles, not the
    enforcement itself.
    """
    raw_token = extract_bearer_token(authorization)
    db = get_supabase_for_user(raw_token)

    update = {
        "curator_answer_text": body.curator_answer_text,
        "curated_by": user.get("sub"),
        "curated_at": datetime.now(timezone.utc).isoformat(),
        "status": "curated",
    }

    try:
        res = (
            db.table("protocol_questions")
            .update(update)
            .eq("id", question_id)
            .execute()
        )
    except Exception as e:
        logger.warning("Protocol question curation update failed: %s", e)
        raise HTTPException(status_code=502, detail="Could not save your answer — try again")

    if not res.data:
        raise HTTPException(status_code=404, detail="Question not found or not accessible")

    return res.data[0]
