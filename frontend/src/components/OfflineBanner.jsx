import { useState, useEffect } from 'react'
import { getQueueCount } from '../lib/offlineQueue'

export default function OfflineBanner() {
  const [online,     setOnline]     = useState(navigator.onLine)
  const [queueCount, setQueueCount] = useState(0)

  useEffect(() => {
    async function updateCount() {
      const count = await getQueueCount()
      setQueueCount(count)
    }

    function handleOnline()  { setOnline(true);  updateCount() }
    function handleOffline() { setOnline(false); updateCount() }

    window.addEventListener('online',  handleOnline)
    window.addEventListener('offline', handleOffline)
    window.addEventListener('offline-queue-changed', updateCount)
    updateCount()

    return () => {
      window.removeEventListener('online',  handleOnline)
      window.removeEventListener('offline', handleOffline)
      window.removeEventListener('offline-queue-changed', updateCount)
    }
  }, [])

  if (online && queueCount === 0) return null

  if (!online) {
    return (
      <div className="bg-urgent/10 border-b border-urgent/30 px-4 py-2 text-center text-sm text-urgent">
        You are offline. Submissions will be saved and synced when connected.
        {queueCount > 0 && (
          <span className="ml-2 font-medium font-mono">{queueCount} pending</span>
        )}
      </div>
    )
  }

  // Online but has queued items (syncing in progress)
  if (online && queueCount > 0) {
    return (
      <div className="bg-forest/10 border-b border-forest/30 px-4 py-2 text-center text-sm text-forest">
        Syncing {queueCount} offline submission{queueCount > 1 ? 's' : ''}…
      </div>
    )
  }

  return null
}
