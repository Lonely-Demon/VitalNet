// Idempotency middleware for the unified offline outbox (Round 6 rebuild
// plan, Phase 5). A retried request carrying X-Event-Id replays the
// STORED response from client_events instead of re-running the handler —
// skipping triage/the LLM briefing call entirely for a case that already
// exists, not just skipping the DB write (case_records.client_id's own
// upsert-with-ignore-duplicates, Phase 4, already handled that narrower
// case — this is a strict efficiency improvement on top, not a
// replacement: both stay in place as independent, defense-in-depth
// idempotency guarantees).
//
// Uses the CALLER's own RLS-scoped client throughout: the lookup relies on
// client_events' existing SELECT policy (submitted_by = auth.uid() OR
// admin — phase29_events_and_advisory_model.sql), and the write goes
// through fn_client_event_record (phase31_client_event_record_fn.sql), a
// SECURITY DEFINER function that sets submitted_by from the caller's own
// JWT rather than a client-supplied value. No service-role client
// anywhere in this file — see _shared/database.ts's header for why that
// matters (service-role usage is meant to stay confined to /api/admin +
// audit writes).
import type { Context, Next } from "hono";
import { getSupabaseForUser } from "./database.ts";
import type { AppEnv } from "./types.ts";

const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * Hono middleware factory. Usage:
 *   app.post("/api/submit", rateLimit(...), requireRole(...), idempotent("case.submit"), handler)
 * Must be registered AFTER requireRole() — it reads c.get("user").
 *
 * No X-Event-Id header (or a malformed one) simply skips idempotency
 * entirely — every route this is attached to must remain correct without
 * an event id, since not every caller of a shared client (e.g. a manual
 * curl test) sends one.
 */
export function idempotent(eventType: string) {
  return async (c: Context<AppEnv>, next: Next) => {
    const eventId = c.req.header("X-Event-Id");
    if (!eventId || !UUID_RE.test(eventId)) {
      await next();
      return;
    }

    const user = c.get("user");
    const db = getSupabaseForUser(user.token);

    const { data: existing, error: lookupError } = await db
      .from("client_events")
      .select("response")
      .eq("event_id", eventId)
      .maybeSingle();
    if (lookupError) {
      // Fail open — an infra hiccup on the dedup lookup should not block a
      // real submission. Logged so a persistent failure is visible.
      console.warn("client_events lookup failed — proceeding without idempotency replay:", lookupError);
    } else if (existing) {
      return c.json(existing.response as Record<string, unknown>);
    }

    await next();

    if (c.res.status >= 200 && c.res.status < 300) {
      try {
        const body = await c.res.clone().json();
        const { error: recordError } = await db.rpc("fn_client_event_record", {
          p_event_id: eventId,
          p_event_type: eventType,
          p_response: body,
        });
        if (recordError) {
          console.warn("fn_client_event_record failed — this event won't replay on retry:", recordError);
        }
      } catch (e) {
        console.warn("Failed to capture response for client_events:", e);
      }
    }
  };
}
