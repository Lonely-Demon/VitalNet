"""
Web Push send helper (FEATURES_ROADMAP §1.4). Separate from
app/api/routes/push_routes.py (which owns the subscribe/unsubscribe
endpoints) so cases.py can call push_emergency_alert() without a circular
import between the two route modules.
"""
import json
import logging

from pywebpush import webpush, WebPushException

from app.core.config import settings
from app.core.database import supabase_admin

logger = logging.getLogger("vitalnet")


def _send_one(subscription: dict, payload: str) -> None:
    try:
        webpush(
            subscription_info={
                "endpoint": subscription["endpoint"],
                "keys": {"p256dh": subscription["p256dh_key"], "auth": subscription["auth_key"]},
            },
            data=payload,
            vapid_private_key=settings.vapid_private_key,
            vapid_claims={"sub": settings.vapid_subject},
        )
    except WebPushException as e:
        status_code = getattr(e.response, "status_code", None)
        if status_code == 410:
            # Subscription expired/revoked on the browser side — clean it up.
            try:
                supabase_admin.table("push_subscriptions").delete().eq("endpoint", subscription["endpoint"]).execute()
            except Exception:
                logger.warning("Failed to remove stale push subscription %s", subscription.get("id"))
        else:
            logger.warning("Push send failed (status=%s): %s", status_code, e)


def push_emergency_alert(facility_id: str | None, title: str, body: str) -> None:
    """
    Fire-and-forget push to all subscribed doctors/admins at a facility (or
    everyone subscribed, if facility_id is None). Called as a FastAPI
    BackgroundTask from submit_case — never raises into the caller.
    """
    if not settings.vapid_public_key or not settings.vapid_private_key:
        return  # Push not configured — silently no-op, Realtime is still the primary channel.

    try:
        query = supabase_admin.table("push_subscriptions").select("id, endpoint, p256dh_key, auth_key")
        if facility_id:
            query = query.eq("facility_id", facility_id)
        subscriptions = query.execute().data or []
    except Exception as e:
        logger.warning("Failed to fetch push subscriptions: %s", e)
        return

    payload = json.dumps({"title": title, "body": body})
    for sub in subscriptions:
        _send_one(sub, payload)
