// frontend/src/components/UpdatePrompt.jsx
// Service worker cache invalidation UI — §4.8.
// When a new PWA version is detected (new service worker is waiting),
// shows a fixed bottom-right toast prompting the user to reload.
// This ensures rural workers get the matching frontend bundle after a deployment
// instead of running a stale cached version that may send malformed API requests.
//
// Requires registerType: 'prompt' in vite.config.js (changed from 'autoUpdate').

import { useRegisterSW } from 'virtual:pwa-register/react'

export function UpdatePrompt() {
  const {
    needRefresh: [needRefresh, setNeedRefresh],
    updateServiceWorker,
  } = useRegisterSW({
    onRegistered(r) {
      console.log('[VitalNet] Service worker registered:', r)
    },
    onRegisterError(error) {
      console.error('[VitalNet] Service worker registration error:', error)
    },
  })

  if (!needRefresh) return null

  return (
    <div className="fixed bottom-4 right-4 bg-red-700 text-white p-4 rounded-xl shadow-2xl z-50 max-w-xs animate-fade-up">
      <p className="font-semibold text-sm mb-1">App update available</p>
      <p className="text-white/80 text-xs mb-3">
        A new version of VitalNet is ready. Reload to ensure you are on the correct version.
      </p>
      <div className="flex gap-2">
        <button
          onClick={() => updateServiceWorker(true)}
          className="flex-1 bg-white text-red-700 px-3 py-1.5 rounded-lg text-sm font-semibold hover:bg-red-50 transition-colors"
        >
          Reload now
        </button>
        <button
          onClick={() => setNeedRefresh(false)}
          className="text-white/70 hover:text-white text-sm px-2 transition-colors"
        >
          Later
        </button>
      </div>
    </div>
  )
}
