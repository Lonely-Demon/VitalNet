/**
 * push.js — Web Push subscription helper (FEATURES_ROADMAP §1.4).
 * Requests Notification permission, subscribes via the Push API, and
 * registers the subscription with the backend so EMERGENCY cases can
 * trigger a push even when the app isn't open.
 */
import { authHeaders } from '@/api/auth'

const BASE = import.meta.env.VITE_API_BASE_URL
const VAPID_PUBLIC_KEY = import.meta.env.VITE_VAPID_PUBLIC_KEY

function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const rawData = atob(base64)
  return Uint8Array.from([...rawData].map((c) => c.charCodeAt(0)))
}

/** True if this browser/context can support Web Push at all. */
export function isPushSupported() {
  return 'serviceWorker' in navigator && 'PushManager' in window && Boolean(VAPID_PUBLIC_KEY)
}

/**
 * Requests notification permission and subscribes to push, posting the
 * subscription to the backend. Returns false (never throws) if the user
 * declines or push isn't supported — this is an optional enhancement, not
 * a required flow (Realtime-while-open remains the primary channel).
 */
export async function subscribeToPush() {
  if (!isPushSupported()) return false

  try {
    const permission = await Notification.requestPermission()
    if (permission !== 'granted') return false

    const registration = await navigator.serviceWorker.ready
    let subscription = await registration.pushManager.getSubscription()
    if (!subscription) {
      subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY),
      })
    }

    const { endpoint, keys } = subscription.toJSON()
    const headers = await authHeaders()
    const res = await fetch(`${BASE}/api/push/subscribe`, {
      method: 'POST',
      headers,
      body: JSON.stringify({
        endpoint,
        p256dh_key: keys.p256dh,
        auth_key: keys.auth,
      }),
    })
    return res.ok
  } catch (e) {
    console.warn('Push subscription failed:', e)
    return false
  }
}
