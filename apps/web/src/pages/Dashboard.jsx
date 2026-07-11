import { useState, useEffect, useCallback, useMemo } from 'react'
import { getCases } from '../lib/api'
import BriefingCard from '../components/BriefingCard'
import { useAuth } from '../store/authStore'
import { useToast } from '../components/ToastProvider'
import { useRealtimeCases } from '../hooks/useRealtimeCases'
import SkeletonCard from '../components/SkeletonCard'

export default function Dashboard({ filter = 'all' }) {
  const [cases, setCases]         = useState([])
  const [loading, setLoading]     = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [hasMore, setHasMore]     = useState(false)
  const [nextCursor, setNextCursor] = useState(null)
  const [nextTriagePriority, setNextTriagePriority] = useState(null)
  const [nextId, setNextId] = useState(null)
  const [error, setError]         = useState(null)
  const { profile } = useAuth()
  const { showToast } = useToast()

  const facilityId = profile?.facility_id

  // Initial load — resets pagination state
  const fetchCases = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await getCases()
      if (!data || !Array.isArray(data.cases)) {
        throw new Error('Invalid response from server. (Check API URL or CORS)')
      }
      setCases(data.cases)
      setHasMore(data.hasMore)
      setNextCursor(data.nextCursor)
      setNextTriagePriority(data.nextTriagePriority ?? null)
      setNextId(data.nextId ?? null)
    } catch (e) {
      setError(e.message || 'Failed to load cases. Check backend connection.')
    } finally {
      setLoading(false)
    }
  }, [])

  // Load next page — appends to existing list without replacing real-time inserts
  const loadMore = async () => {
    if (!nextCursor || loadingMore) return
    setLoadingMore(true)
    try {
      const data = await getCases({
        before_time: nextCursor,
        before_priority: nextTriagePriority,
        before_id: nextId,
      })
      if (!data || !Array.isArray(data.cases)) return
      // Deduplicate in case realtime already inserted a row / prior page overlap
      setCases(prev => {
        const existingIds = new Set(prev.map(c => c.id))
        const fresh = data.cases.filter(c => !existingIds.has(c.id))
        return [...prev, ...fresh]
      })
      setHasMore(data.hasMore)
      setNextCursor(data.nextCursor)
      setNextTriagePriority(data.nextTriagePriority ?? null)
      setNextId(data.nextId ?? null)
    } catch (e) {
      showToast('Failed to load more cases', 'error')
    } finally {
      setLoadingMore(false)
    }
  }

  useEffect(() => { fetchCases() }, [fetchCases])

  const handleReviewed = useCallback((caseId) => {
    setCases((prev) => prev.map((c) => (
      c.id === caseId
        ? { ...c, reviewed_at: c.reviewed_at || new Date().toISOString() }
        : c
    )))
  }, [])

  // Real-time: prepend new inserts; update reviewed cases in place
  useRealtimeCases({
    facilityId,
    onInsert: (newCase) => {
      // Soft-deleted rows shouldn't appear on the live dashboard
      if (newCase.deleted_at) return
      setCases((prev) => {
        if (prev.find((c) => c.id === newCase.id)) return prev
        return [newCase, ...prev]
      })
      if (newCase.triage_level === 'EMERGENCY') {
        showToast('New EMERGENCY case received', 'error')
      }
    },
    onUpdate: (updatedCase) => {
      setCases((prev) => {
        // A case just soft-deleted should drop off the dashboard immediately
        if (updatedCase.deleted_at) {
          return prev.filter((c) => c.id !== updatedCase.id)
        }
        return prev.map((c) => (c.id === updatedCase.id ? updatedCase : c))
      })
    },
  })

  // Client-side filter — memoized so section derivation doesn't re-run every render
  const visibleCases = useMemo(() => (
    filter === 'pending'
      ? cases.filter(c => !c.reviewed_at && !c.deleted_at)
      : cases.filter(c => !c.deleted_at)
  ), [cases, filter])

  const emergency = useMemo(() => visibleCases.filter(c => c.triage_level === 'EMERGENCY'), [visibleCases])
  const urgent    = useMemo(() => visibleCases.filter(c => c.triage_level === 'URGENT'), [visibleCases])
  const routine   = useMemo(() => visibleCases.filter(c => c.triage_level === 'ROUTINE'), [visibleCases])

  if (loading) {
    return (
      <div className="max-w-2xl mx-auto p-4 mt-6">
        <SkeletonCard />
        <SkeletonCard />
        <SkeletonCard />
      </div>
    )
  }

  return (
    <div className="max-w-2xl mx-auto p-4 mt-6">
      <div className="flex items-center justify-end mb-4">
        <button onClick={fetchCases} className="text-sm font-medium text-forest bg-leaf/40 px-4 py-2 rounded-pill hover:bg-leaf/70 transition-colors shadow-card cursor-pointer">
          Refresh Queue
        </button>
      </div>

      {error && (
        <div className="bg-emergency/10 border border-emergency/30 text-emergency px-4 py-3 rounded-lg shadow-card mb-6 text-sm">
          {error}
        </div>
      )}

      {visibleCases.length === 0 && !error && (
        <div className="text-center bg-surface border border-dashed border-leaf/60 rounded-xl p-12 shadow-card mt-8 animate-fade-up">
          <div className="text-4xl mb-3">📭</div>
          <p className="text-xl font-medium text-text tracking-tight font-display italic">
            {filter === 'pending' ? 'No Pending Cases' : 'Queue is Empty'}
          </p>
          <p className="text-sm text-text2 mt-2">
            {filter === 'pending'
              ? 'All submitted cases have been reviewed.'
              : 'New cases submitted by ASHAs will appear here'}
          </p>
        </div>
      )}

      {emergency.length > 0 && (
        <div className="mb-8">
          <h2 className="text-xs font-mono font-bold text-emergency uppercase tracking-widest mb-3 flex items-center gap-2">
            Emergency <span className="bg-emergency/10 text-emergency px-2 py-0.5 rounded-pill">{emergency.length}</span>
          </h2>
          {emergency.map(c => <BriefingCard key={c.id} caseData={c} onReviewed={handleReviewed} />)}
        </div>
      )}

      {urgent.length > 0 && (
        <div className="mb-8">
          <h2 className="text-xs font-mono font-bold text-urgent uppercase tracking-widest mb-3 flex items-center gap-2">
            Urgent <span className="bg-urgent/10 text-urgent px-2 py-0.5 rounded-pill">{urgent.length}</span>
          </h2>
          {urgent.map(c => <BriefingCard key={c.id} caseData={c} onReviewed={handleReviewed} />)}
        </div>
      )}

      {routine.length > 0 && (
        <div className="mb-8">
          <h2 className="text-xs font-mono font-bold text-routine uppercase tracking-widest mb-3 flex items-center gap-2">
            Routine <span className="bg-routine/10 text-routine px-2 py-0.5 rounded-pill">{routine.length}</span>
          </h2>
          {routine.map(c => <BriefingCard key={c.id} caseData={c} onReviewed={handleReviewed} />)}
        </div>
      )}

      {/* Cursor-based Load More — does not affect real-time inserts at top */}
      {hasMore && (
        <div className="flex justify-center mt-4 mb-8">
          <button
            onClick={loadMore}
            disabled={loadingMore}
            className="text-sm font-medium text-forest bg-leaf/40 px-6 py-2.5 rounded-pill hover:bg-leaf/70 transition-colors shadow-card cursor-pointer disabled:opacity-60 disabled:cursor-wait"
          >
            {loadingMore ? 'Loading…' : 'Load More Cases'}
          </button>
        </div>
      )}
    </div>
  )
}
