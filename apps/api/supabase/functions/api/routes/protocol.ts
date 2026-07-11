// Ported from protocol_routes.py — GET /api/protocol/questions only
// (Tranche A). POST /ask and PATCH /questions/:id/curate are writes that
// also need app/services/llm.py's 4-tier Groq/Gemini fallback ported
// (a substantial separate piece — see the "Runtime surface to port"
// section of the migration plan) — grouped into Tranche B (Phase 4)
// alongside voice, the other LLM/external-API-heavy write surface,
// rather than force-fit here just because they live in the same Python
// module. This one endpoint uses genuine Postgres RLS via the caller's
// own client (protocol_questions carries no PHI, unlike case_records —
// see this file's Python original for the full rationale), not a
// SECURITY DEFINER function.
import { Hono } from "hono";
import { requireRole } from "../_shared/auth.ts";
import { getSupabaseForUser, HttpError } from "../_shared/database.ts";
import type { AppEnv } from "../_shared/types.ts";

export const protocol = new Hono<AppEnv>();

const ALL_ROLES = ["asha_worker", "doctor", "supervisor", "admin"];
const VALID_STATUSES = new Set(["answered", "pending_curation", "curated"]);

protocol.get("/api/protocol/questions", requireRole(...ALL_ROLES), async (c) => {
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
