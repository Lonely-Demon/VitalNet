// Ported from protocol_routes.py. Tranche A shipped GET /api/protocol/questions
// only; Phase 4 (Tranche B) adds POST /ask and PATCH /questions/:id/curate,
// which needed _shared/llm.ts's generateProtocolAnswer() (the 4-tier
// Groq/Gemini fallback) to exist first. This route module uses genuine
// Postgres RLS via the caller's own client throughout (protocol_questions
// carries no PHI, unlike case_records — see the Python original for the
// full rationale), not a SECURITY DEFINER function.
import { Hono } from "hono";
import { z } from "zod";
import { requireRole } from "../_shared/auth.ts";
import { rateLimit } from "../_shared/rateLimit.ts";
import { getSupabaseForUser, HttpError } from "../_shared/database.ts";
import { generateProtocolAnswer } from "../_shared/llm.ts";
import type { AppEnv } from "../_shared/types.ts";

export const protocol = new Hono<AppEnv>();

const ALL_ROLES = ["asha_worker", "doctor", "supervisor", "admin"];
const CURATOR_ROLES = ["doctor", "supervisor", "admin"];
const VALID_STATUSES = new Set(["answered", "pending_curation", "curated"]);

const askProtocolQuestionSchema = z.object({
  question_text: z.string().min(1).max(500),
  language: z.enum(["en", "hi", "ta"]).default("en"),
});

const curateProtocolAnswerSchema = z.object({
  curator_answer_text: z.string().min(1).max(2000),
});

async function readJsonBody(c: { req: { json: () => Promise<unknown> } }): Promise<unknown> {
  try {
    return await c.req.json();
  } catch {
    throw new HttpError(400, "Invalid JSON body");
  }
}

// Asks a general protocol/guideline question. Answered inline when the LLM
// finds it in the curated reference material; otherwise queued for
// asynchronous curation by a supervisor/doctor/admin at the same facility
// — never a synchronous multi-reviewer gate (ASHABot's own published data
// found that mechanism averaged ~60h, too slow to be useful).
protocol.post("/api/protocol/ask", rateLimit(20, 60), requireRole(...ALL_ROLES), async (c) => {
  const user = c.get("user");
  const facilityId = user.resolvedFacilityId;
  if (!facilityId) {
    throw new HttpError(400, "Account has no facility assigned");
  }

  const parsed = askProtocolQuestionSchema.safeParse(await readJsonBody(c));
  if (!parsed.success) {
    throw new HttpError(400, parsed.error.issues.map((i) => i.message).join("; "));
  }
  const body = parsed.data;

  const db = getSupabaseForUser(user.token);
  const result = await generateProtocolAnswer(body.question_text, body.language);

  const row = {
    asked_by: user.sub,
    facility_id: facilityId,
    question_text: body.question_text,
    language: body.language,
    llm_answer_text: result.answer,
    llm_grounded: result.grounded,
    status: result.grounded ? "answered" : "pending_curation",
  };

  const { data, error } = await db.from("protocol_questions").insert(row).select();
  if (error) {
    console.warn("Protocol question insert failed:", error);
    throw new HttpError(502, "Could not save your question — try again");
  }

  return c.json((data && data[0]) || row);
});

protocol.get("/api/protocol/questions", rateLimit(60, 60), requireRole(...ALL_ROLES), async (c) => {
  const user = c.get("user");
  const db = getSupabaseForUser(user.token);

  const status = c.req.query("status");
  const facilityId = c.req.query("facility_id");

  let query = db.from("protocol_questions").select("*").order("created_at", { ascending: false });
  if (status) {
    if (!VALID_STATUSES.has(status)) {
      throw new HttpError(400, "Invalid status");
    }
    query = query.eq("status", status);
  }
  if (facilityId) {
    query = query.eq("facility_id", facilityId);
  }

  const { data, error } = await query;
  if (error) {
    console.warn("Protocol question list query failed:", error);
    throw new HttpError(502, "Could not load questions — try again");
  }

  return c.json({ questions: data ?? [] });
});

// Records a human curator's answer for a question the LLM couldn't ground.
// RLS (protocol_questions_update_policy) is the real access boundary — a
// supervisor/doctor can only reach rows at their own facility; requireRole
// here is a clean 403 for other roles, not the enforcement itself.
protocol.patch(
  "/api/protocol/questions/:question_id/curate",
  rateLimit(30, 60),
  requireRole(...CURATOR_ROLES),
  async (c) => {
    const user = c.get("user");
    const questionId = c.req.param("question_id")!;
    const parsed = curateProtocolAnswerSchema.safeParse(await readJsonBody(c));
    if (!parsed.success) {
      throw new HttpError(400, parsed.error.issues.map((i) => i.message).join("; "));
    }
    const body = parsed.data;

    const db = getSupabaseForUser(user.token);
    const update = {
      curator_answer_text: body.curator_answer_text,
      curated_by: user.sub,
      curated_at: new Date().toISOString(),
      status: "curated",
    };

    const { data, error } = await db.from("protocol_questions").update(update).eq("id", questionId).select();
    if (error) {
      console.warn("Protocol question curation update failed:", error);
      throw new HttpError(502, "Could not save your answer — try again");
    }
    if (!data || data.length === 0) {
      throw new HttpError(404, "Question not found or not accessible");
    }

    return c.json(data[0]);
  },
);
