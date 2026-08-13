// sw-push.js — Web Push handler, injected into the generated service worker
// via workbox.importScripts (vite.config.js). Kept as a small standalone
// script rather than switching to injectManifest mode, which would require
// hand-maintaining the whole service worker.

self.addEventListener('push', (event) => {
  let data = { title: 'VitalNet', body: 'New notification' }
  try {
    if (event.data) data = event.data.json()
  } catch {
    // Non-JSON payload — fall back to the default text above.
  }

  // Defense-in-depth: never render a push payload verbatim. Coerce to string,
  // strip newlines, cap length, and always prefix the title with a fixed app
  // identifier — so if the push credentials are ever compromised server-side,
  // a notification still cannot masquerade as arbitrary unbranded content or
  // overflow the OS notification surface.
  const clean = (v, max) => String(v ?? '').replace(/[\r\n\t]+/g, ' ').slice(0, max)
  const safeTitle = 'VitalNet · ' + clean(data.title, 80)
  const safeBody = clean(data.body, 200)

  event.waitUntil(
    self.registration.showNotification(safeTitle, {
      body: safeBody,
      icon: '/pwa-192x192.png',
      badge: '/pwa-64x64.png',
      tag: 'vitalnet-emergency',
      requireInteraction: true,
    })
  )
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if ('focus' in client) return client.focus()
      }
      if (self.clients.openWindow) return self.clients.openWindow('/')
    })
  )
})
