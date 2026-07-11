// Web Push send helper — ported from app/services/push.py. Uses the
// "web-push" npm package (VAPID JWT signing + aes128gcm payload encryption
// per RFC 8291) via Deno's npm compatibility layer, the same mechanism
// jose/@supabase-js already rely on in this function (deno.json's import
// map). web-push is pure JS on top of Node's `crypto`/`https` modules —
// exactly the shape Deno's npm compat targets — but this is still the
// FLAGGED highest-risk port in the Round 6 rebuild plan's Phase 4 (no live
// network coverage in this repo's test suite, by design — see
// test/webpush.test.ts's header). Run a send-to-self integration test
// against a real push subscription before cutting the EMERGENCY-alert path
// over from the FastAPI backend's pywebpush equivalent.
import webpush from "web-push";
import { getConfig } from "./config.ts";
import { getSupabaseAdmin } from "./database.ts";

interface PushSubscriptionRow {
  id: string;
  endpoint: string;
  p256dh_key: string;
  auth_key: string;
}

async function sendOne(subscription: PushSubscriptionRow, payload: string): Promise<void> {
  try {
    await webpush.sendNotification(
      {
        endpoint: subscription.endpoint,
        keys: { p256dh: subscription.p256dh_key, auth: subscription.auth_key },
      },
      payload,
    );
  } catch (e) {
    const statusCode = (e as { statusCode?: number } | undefined)?.statusCode;
    if (statusCode === 410) {
      // Subscription expired/revoked on the browser side — clean it up.
      try {
        const { error } = await getSupabaseAdmin().from("push_subscriptions").delete().eq(
          "endpoint",
          subscription.endpoint,
        );
        if (error) throw error;
      } catch {
        console.warn(`Failed to remove stale push subscription ${subscription.id}`);
      }
    } else {
      console.warn(`Push send failed (status=${statusCode}):`, e);
    }
  }
}

/**
 * Fire-and-forget push to all subscribed doctors/admins at a facility (or
 * everyone subscribed, if facilityId is null). Called from routes/cases.ts
 * without being awaited on the request's critical path — never throws into
 * the caller. No-ops silently if VAPID isn't configured (Realtime, where
 * wired, is still the primary channel).
 */
export async function pushEmergencyAlert(facilityId: string | null, title: string, body: string): Promise<void> {
  const config = getConfig();
  if (!config.vapidPublicKey || !config.vapidPrivateKey) return;

  webpush.setVapidDetails(config.vapidSubject, config.vapidPublicKey, config.vapidPrivateKey);

  let subscriptions: PushSubscriptionRow[];
  try {
    let query = getSupabaseAdmin().from("push_subscriptions").select("id, endpoint, p256dh_key, auth_key");
    if (facilityId) query = query.eq("facility_id", facilityId);
    const { data, error } = await query;
    if (error) throw error;
    subscriptions = (data ?? []) as PushSubscriptionRow[];
  } catch (e) {
    console.warn("Failed to fetch push subscriptions:", e);
    return;
  }

  const payload = JSON.stringify({ title, body });
  for (const sub of subscriptions) {
    await sendOne(sub, payload);
  }
}
