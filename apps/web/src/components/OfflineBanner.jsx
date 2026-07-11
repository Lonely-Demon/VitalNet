import { useState, useEffect } from 'react'
import { getPendingCount, getDeadLetters, retryDeadLetter, discardDeadLetter } from '../lib/outbox'

export default function OfflineBanner() {
  const [online,       setOnline]       = useState(navigator.onLine)
  const [queueCount,   setQueueCount]   = useState(0)
  const [deadLetters,  setDeadLetters]  = useState([])
  const [showDead,     setShowDead]     = useState(false)

  useEffect(() => {
    async function updateCounts() {
      const [count, dead] = await Promise.all([getPendingCount(), getDeadLetters()])
      setQueueCount(count)
      setDeadLetters(dead)
    }

    function handleOnline()  { setOnline(true);  updateCounts() }
    function handleOffline() { setOnline(false); updateCounts() }

    window.addEventListener('online',  handleOnline)
    window.addEventListener('offline', handleOffline)
    window.addEventListener('offline-queue-changed', updateCounts)
    updateCounts()

    return () => {
      window.removeEventListener('online',  handleOnline)
      window.removeEventListener('offline', handleOffline)
      window.removeEventListener('offline-queue-changed', updateCounts)
    }
  }, [])

  const handleRetry = async (eventId) => {
    await retryDeadLetter(eventId)
  }

  const handleDiscard = async (eventId) => {
    await discardDeadLetter(eventId)
  }

  if (online && queueCount === 0 && deadLetters.length === 0) return null

  return (
    <div>
      {!online && (
        <div role="status" aria-live="polite" className="bg-urgent/10 border-b border-urgent/30 px-4 py-2 text-center text-sm text-urgent">
          You are offline. Submissions will be saved and synced when connected.
          {queueCount > 0 && (
            <span className="ml-2 font-medium font-mono">{queueCount} pending</span>
          )}
        </div>
      )}

      {/* Online but has queued items (syncing in progress) */}
      {online && queueCount > 0 && (
        <div role="status" aria-live="polite" className="bg-forest/10 border-b border-forest/30 px-4 py-2 text-center text-sm text-forest">
          Syncing {queueCount} offline submission{queueCount > 1 ? 's' : ''}…
        </div>
      )}

      {/* Dead-lettered submissions — surfaced, never silently dropped
          (Round 6 rebuild plan, Phase 5's unified-outbox requirement). */}
      {deadLetters.length > 0 && (
        <div role="alert" aria-live="polite" className="bg-emergency/10 border-b border-emergency/30 px-4 py-2 text-sm text-emergency">
          <div className="flex items-center justify-center gap-2 flex-wrap">
            <span>
              {deadLetters.length} offline submission{deadLetters.length > 1 ? 's' : ''} could not be saved.
            </span>
            <button
              type="button"
              onClick={() => setShowDead((s) => !s)}
              className="underline font-medium cursor-pointer"
            >
              {showDead ? 'Hide details' : 'Show details'}
            </button>
          </div>
          {showDead && (
            <ul className="mt-2 max-w-lg mx-auto text-left space-y-2">
              {deadLetters.map((item) => (
                <li key={item.event_id} className="bg-surface border border-emergency/20 rounded-md p-2">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-text2 truncate">
                      {item.payload?.patient_name || 'Unnamed patient'} — {item.payload?.chief_complaint || ''}
                    </span>
                    <div className="flex gap-2 shrink-0">
                      <button
                        type="button"
                        onClick={() => handleRetry(item.event_id)}
                        className="px-2 py-1 rounded bg-forest/10 text-forest text-xs font-medium cursor-pointer hover:bg-forest/20"
                      >
                        Retry
                      </button>
                      <button
                        type="button"
                        onClick={() => handleDiscard(item.event_id)}
                        className="px-2 py-1 rounded bg-surface2 text-text3 text-xs font-medium cursor-pointer hover:bg-surface3"
                      >
                        Discard
                      </button>
                    </div>
                  </div>
                  {item.last_error && (
                    <p className="text-xs text-text3 mt-1 truncate">{item.last_error}</p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}
