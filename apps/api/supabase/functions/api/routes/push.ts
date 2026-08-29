// Ported from app/api/routes/push_routes.py — Web Push subscription
// management and the unreviewed-EMERGENCY escalation sweep. The actual
// send logic lives in _shared/webpush.ts (called from routes/cases.ts as a
// background task, and from the escalation check below) — this module
// owns the endpoints only.
import { Hono } from "hono";
import { z } from "zod";
import { requireRole } from "../_shared/auth.ts";
import { rateLimit } from "../_shared/rateLimit.ts";
import { extractBearerToken, getSupabaseAdmin, getSupabaseForUser, HttpError } from "../_shared/database.ts";
import { getConfig } from "../_shared/config.ts";
import { pushEmergencyAlert } from "../_shared/webpush.ts";
import type { AppEnv } from "../_shared/types.ts";

export const push = new Hono<AppEnv>();

// Re-alert an unreviewed EMERGENCY case once it's sat this long without
// being reviewed, and again on the same interval after each escalation
// (tracked via last_escalated_at) so a case doesn't get re-notified on
// every scheduler tick.
const ESCALATION_THRESHOLD_MINUTES = 15;

const pushSubscriptionSchema = z.object({
  endpoint: z.string().min(1).max(2000),
  p256dh_key: z.string().min(1).max(500),
  auth_key: z.string().min(1).max(500),
});

async function readJsonBody(c: { req: { json: () => Promise<unknown> } }): Promise<unknown> {
  try {
    return await c.req.json();
  } catch {
    throw new HttpError(400, "Invalid JSON body");
  }
}

push.post("/api/push/subscribe", rateLimit(10, 60), requireRole("doctor", "admin"), async (c) => {
  const user = c.get("user");
  const config = getConfig();
  if (!config.vapidPublicKey || !config.vapidPrivateKey) {
    throw new HttpError(503, "Push notifications are not configured on this server");
  }

  const parsed = pushSubscriptionSchema.safeParse(await readJsonBody(c));
  if (!parsed.success) {
    throw new HttpError(400, parsed.error.issues.map((i) => i.message).join("; "));
  }
  const body = parsed.data;

  const rawToken = extractBearerToken(c.req.header("authorization"));
  const db = getSupabaseForUser(rawToken);

  const { error } = await db.from("push_subscriptions").upsert(
    {
      user_id: user.sub,
      facility_id: user.resolvedFacilityId,
      endpoint: body.endpoint,
      p256dh_key: body.p256dh_key,
      auth_key: body.auth_key,
    },
    { onConflict: "endpoint" },
  );
  if (error) throw error;

  return c.json({ status: "subscribed" });
});

push.delete("/api/push/subscribe", rateLimit(10, 60), requireRole("doctor", "admin"), async (c) => {
  const user = c.get("user");
  const endpoint = c.req.query("endpoint");
  if (!endpoint) throw new HttpError(400, "Missing endpoint query parameter");

  const rawToken = extractBearerToken(c.req.header("authorization"));
  const db = getSupabaseForUser(rawToken);

  const { error } = await db.from("push_subscriptions").delete().eq("endpoint", endpoint).eq("user_id", user.sub);
  if (error) throw error;

  return c.json({ status: "unsubscribed" });
});

interface EscalationCandidate {
  id: string;
  facility_id: string | null;
  chief_complaint: string | null;
  risk_driver: string | null;
  created_at: string;
  last_escalated_at: string | null;
}

push.post("/api/push/check-emergency-escalations", rateLimit(6, 60), requireRole("admin"), async (c) => {
  const threshold = new Date(Date.now() - ESCALATION_THRESHOLD_MINUTES * 60 * 1000).toISOString();
  const svc = getSupabaseAdmin();

  const { data, error } = await svc
    .from("case_records")
    .select("id, facility_id, chief_complaint, risk_driver, created_at, last_escalated_at")
    .eq("triage_level", "EMERGENCY")
    .is("reviewed_at", null)
    .is("deleted_at", null)
    .lt("created_at", threshold);
  if (error) throw error;

  const candidates = (data ?? []) as EscalationCandidate[];
  const escalated: string[] = [];

  for (const candidate of candidates) {
    if (candidate.last_escalated_at && candidate.last_escalated_at > threshold) {
      continue; // already escalated within this threshold window
    }

    await pushEmergencyAlert(
      candidate.facility_id,
      "EMERGENCY case still unreviewed",
      `${candidate.chief_complaint ?? ""} — ${candidate.risk_driver ?? ""}`.slice(0, 150),
    );

    const { error: updateError } = await svc
      .from("case_records")
      .update({ last_escalated_at: new Date().toISOString() })
      .eq("id", candidate.id);
    if (updateError) throw updateError;

    escalated.push(candidate.id);
  }

  if (escalated.length) {
    console.info(`Escalated ${escalated.length} unreviewed EMERGENCY case(s): ${escalated.join(", ")}`);
  }

  return c.json({ checked: candidates.length, escalated: escalated.length });
});
