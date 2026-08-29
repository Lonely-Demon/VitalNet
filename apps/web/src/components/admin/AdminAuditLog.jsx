import { useState, useEffect, useCallback } from 'react'
import { adminGetAuditLog } from '../../lib/api'

const EVENT_COLORS = {
  PHI_CREATE: 'text-routine',
  PHI_READ: 'text-text2',
  PHI_UPDATE: 'text-urgent',
  PHI_DELETE: 'text-emergency',
  PHI_EXPORT: 'text-urgent',
  AUTH_LOGIN: 'text-sage',
  AUTH_LOGOUT: 'text-text3',
  AUTH_FAILED: 'text-emergency',
  CONSENT_CAPTURED: 'text-routine',
}

export default function AdminAuditLog() {
  const [entries, setEntries] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [hasMore, setHasMore] = useState(false)
  const [nextCursor, setNextCursor] = useState(null)
  const [error, setError] = useState(null)

  const fetchLog = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await adminGetAuditLog()
      setEntries(data.entries)
      setHasMore(data.hasMore)
      setNextCursor(data.nextCursor)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { fetchLog() }, [fetchLog])

  const loadMore = async () => {
    if (!nextCursor || loadingMore) return
    setLoadingMore(true)
    try {
      const data = await adminGetAuditLog({ before: nextCursor })
      setEntries(prev => [...prev, ...data.entries])
      setHasMore(data.hasMore)
      setNextCursor(data.nextCursor)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoadingMore(false)
    }
  }

  if (loading) return <div className="text-center py-16 text-text3 text-sm">Loading audit log...</div>
  if (error) return <div className="bg-emergency/10 border border-emergency/30 rounded-lg px-4 py-3 text-emergency text-sm">{error}</div>

  return (
    <div>
      <h2 className="text-base font-semibold text-text mb-1 font-display font-bold">Audit Log</h2>
      <p className="text-xs text-text3 mb-4">Every PHI access and admin action, most recent first.</p>

      {entries.length === 0 ? (
        <div className="text-center bg-surface border border-dashed border-leaf/60 rounded-xl p-10 text-text3 text-sm">
          No audit entries yet.
        </div>
      ) : (
        <div className="bg-surface border border-leaf/40 rounded-lg shadow-card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-surface2 text-text3 text-xs uppercase tracking-wider font-mono">
              <tr>
                <th className="text-left px-3 py-2">Time</th>
                <th className="text-left px-3 py-2">Event</th>
                <th className="text-left px-3 py-2">Role</th>
                <th className="text-left px-3 py-2">Resource</th>
                <th className="text-left px-3 py-2">Facility</th>
                <th className="text-left px-3 py-2">IP</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((e) => (
                <tr key={e.id} className="border-t border-leaf/20">
                  <td className="px-3 py-2 font-mono text-xs text-text3 whitespace-nowrap">
                    {new Date(e.created_at).toLocaleString([], { dateStyle: 'short', timeStyle: 'short' })}
                  </td>
                  <td className={`px-3 py-2 font-mono text-xs font-bold ${EVENT_COLORS[e.event_type] || 'text-text2'}`}>
                    {e.event_type}
                  </td>
                  <td className="px-3 py-2 text-text2">{e.user_role || '—'}</td>
                  <td className="px-3 py-2 text-text2 font-mono text-xs">
                    {e.resource_type}{e.resource_id ? `:${e.resource_id}` : ''}
                  </td>
                  <td className="px-3 py-2 text-text3 font-mono text-xs">{e.facility_id || '—'}</td>
                  <td className="px-3 py-2 text-text3 font-mono text-xs">{e.ip_address || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {hasMore && (
        <div className="flex justify-center mt-4">
          <button
            onClick={loadMore}
            disabled={loadingMore}
            className="text-sm font-medium text-forest bg-leaf/40 px-6 py-2.5 rounded-pill hover:bg-leaf/70 transition-colors shadow-card cursor-pointer disabled:opacity-60"
          >
            {loadingMore ? 'Loading…' : 'Load More'}
          </button>
        </div>
      )}
    </div>
  )
}
