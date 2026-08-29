// frontend/src/components/PushPrompt.jsx
// Web Push opt-in prompt (FEATURES_ROADMAP §1.4). Dismissible and never
// forced — doctors who decline still get EMERGENCY cases via Realtime while
// the app is open, this only extends that to when the app/tab is closed.
import { useEffect, useState } from 'react'
import { isPushSupported, subscribeToPush } from '@/lib/push'

const DISMISSED_KEY = 'vn_push_prompt_dismissed'

export function PushPrompt() {
  const [visible, setVisible] = useState(false)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!isPushSupported()) return
    if (localStorage.getItem(DISMISSED_KEY)) return
    if (typeof Notification !== 'undefined' && Notification.permission !== 'default') return
    setVisible(true)
  }, [])

  if (!visible) return null

  const dismiss = () => {
    localStorage.setItem(DISMISSED_KEY, '1')
    setVisible(false)
  }

  const enable = async () => {
    setBusy(true)
    await subscribeToPush()
    setBusy(false)
    dismiss()
  }

  return (
    <div className="fixed bottom-4 left-4 bg-forest text-white p-4 rounded-xl shadow-2xl z-50 max-w-xs animate-fade-up">
      <p className="font-semibold text-sm mb-1">Get EMERGENCY alerts</p>
      <p className="text-white/80 text-xs mb-3">
        Enable push notifications to be alerted about new EMERGENCY cases even when this app is closed.
      </p>
      <div className="flex gap-2">
        <button
          onClick={enable}
          disabled={busy}
          className="flex-1 bg-white text-forest px-3 py-1.5 rounded-lg text-sm font-semibold hover:bg-white/90 transition-colors disabled:opacity-60"
        >
          {busy ? 'Enabling…' : 'Enable'}
        </button>
        <button
          onClick={dismiss}
          className="text-white/70 hover:text-white text-sm px-2 transition-colors"
        >
          Not now
        </button>
      </div>
    </div>
  )
}
