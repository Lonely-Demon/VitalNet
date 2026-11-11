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
import { ALLOWED_PUSH_HOST_SUFFIXES, pushEmergencyAlert, validatePushEndpoint } from "../_shared/webpush.ts";
import type { AppEnv } from "../_shared/types.ts";
import { isGlobalScope } from "../_shared/scoping.ts";

export { ALLOWED_PUSH_HOST_SUFFIXES, validatePushEndpoint };

export function constantTimeEqual(a: string, b: string): boolean {
  if (typeof a !== "string" || typeof b !== "string") {
    return false;
  }
  const encoder = new TextEncoder();
  const aBuf = encoder.encode(a);
  const bBuf = encoder.encode(b);
  const len = Math.max(aBuf.byteLength, bBuf.byteLength);
  let diff = aBuf.byteLength ^ bBuf.byteLength;
  for (let i = 0; i < len; i++) {
    const aByte = i < aBuf.byteLength ? aBuf[i]! : 0;
    const bByte = i < bBuf.byteLength ? bBuf[i]! : 0;
    diff |= aByte ^ bByte;
  }
  return diff === 0;
}

export function verifySchedulerToken(c: { req: { header: (name: string) => string | undefined } }): void {
  const config = getConfig();
  const expectedToken = config.internalSchedulerToken;
  if (!expectedToken) {
    throw new HttpError(
      503,
      "Escalation scheduler endpoint disabled: INTERNAL_SCHEDULER_TOKEN not configured",
    );
  }

  const schedulerToken = c.req.header("x-internal-scheduler-token");
  if (!schedulerToken || !constantTimeEqual(schedulerToken, expectedToken)) {
    throw new HttpError(403, "Invalid or missing scheduler token");
  }
}

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

  // SSRF defense: endpoint must be HTTPS and host must end with recognized push service suffix
  validatePushEndpoint(body.endpoint);

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

  // Bound active subscriptions per user to 5, pruning oldest on insert (BUG-33)
  const MAX_ACTIVE_SUBSCRIPTIONS = 5;
  const { data: userSubs } = await db
    .from("push_subscriptions")
    .select("id, created_at")
    .eq("user_id", user.sub)
    .order("created_at", { ascending: false });

  if (userSubs && userSubs.length > MAX_ACTIVE_SUBSCRIPTIONS) {
    const toPrune = userSubs.slice(MAX_ACTIVE_SUBSCRIPTIONS).map((s: { id: string }) => s.id);
    if (toPrune.length > 0) {
      await db.from("push_subscriptions").delete().in("id", toPrune);
    }
  }

  return c.json({ status: "subscribed" });
});

push.delete("/api/push/subscribe", rateLimit(10, 60), requireRole("doctor", "admin"), async (c) => {
  const user = c.get("user");
  const endpoint = c.req.query("endpoint");
  if (!endpoint) throw new HttpError(400, "Missing endpoint query parameter");

  // Validate endpoint format on unsubscribe as well
  validatePushEndpoint(endpoint);

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
  triage_level: string;
  overridden_triage: string | null;
}

push.post(
  "/api/push/check-emergency-escalations",
  rateLimit(6, 60),
  requireRole("admin", "supervisor", "super_admin"),
  async (c) => {
    const user = c.get("user");
    verifySchedulerToken(c);

    const threshold = new Date(Date.now() - ESCALATION_THRESHOLD_MINUTES * 60 * 1000).toISOString();
    const svc = getSupabaseAdmin();

    let query = svc
      .from("case_records")
      .select(
        "id, facility_id, chief_complaint, risk_driver, created_at, last_escalated_at, triage_level, overridden_triage",
      )
      .or("triage_level.eq.EMERGENCY,overridden_triage.eq.EMERGENCY")
      .is("reviewed_at", null)
      .is("deleted_at", null)
      .lt("created_at", threshold);

    // Scope query by facility for facility-scoped admin; supervisors scan all facilities
    if (!isGlobalScope(user.resolvedRole) && user.resolvedFacilityId) {
      query = query.eq("facility_id", user.resolvedFacilityId);
    }

    const { data, error } = await query;
    if (error) throw error;

    const candidates = (data ?? []) as EscalationCandidate[];
    const escalated: string[] = [];

    for (const candidate of candidates) {
      const effectiveTriage = candidate.overridden_triage ?? candidate.triage_level;
      if (effectiveTriage !== "EMERGENCY") {
        continue;
      }
      if (candidate.last_escalated_at && candidate.last_escalated_at > threshold) {
        continue; // already escalated within this threshold window
      }

      await pushEmergencyAlert(
        candidate.facility_id,
        "EMERGENCY case still unreviewed",
        `${candidate.chief_complaint ?? ""} — ${candidate.risk_driver ?? ""}`.slice(0, 150),
        candidate.id,
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
  },
);
