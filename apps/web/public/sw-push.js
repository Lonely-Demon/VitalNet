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

  event.waitUntil(
    self.registration.showNotification(data.title, {
      body: data.body,
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
