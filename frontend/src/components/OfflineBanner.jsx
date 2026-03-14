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
      <div className="bg-amber-50 border-b border-amber-200 px-4 py-2 text-center text-sm text-amber-800">
        You are offline. Submissions will be saved and synced when connected.
        {queueCount > 0 && (
          <span className="ml-2 font-medium">{queueCount} pending</span>
        )}
      </div>
    )
  }

  // Online but has queued items (syncing in progress)
  if (online && queueCount > 0) {
    return (
      <div className="bg-blue-50 border-b border-blue-200 px-4 py-2 text-center text-sm text-blue-800">
        Syncing {queueCount} offline submission{queueCount > 1 ? 's' : ''}…
      </div>
    )
  }

  return null
}
