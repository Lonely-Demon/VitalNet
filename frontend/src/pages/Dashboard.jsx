import { useState, useEffect } from 'react'
import { getCases } from '../lib/api'
import BriefingCard from '../components/BriefingCard'
import { useAuth } from '../store/authStore'
import { useToast } from '../components/ToastProvider'
import { useRealtimeCases } from '../hooks/useRealtimeCases'

export default function Dashboard({ filter = 'all' }) {
  const [cases, setCases] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const { profile } = useAuth()
  const { showToast } = useToast()

  const facilityId = profile?.facility_id

  const fetchCases = async () => {
    try {
      const data = await getCases()
      if (Array.isArray(data)) {
        setCases(data)
        setError(null)
      } else {
        throw new Error("Invalid response from server. (Check API URL or CORS)")
      }
    } catch (e) {
      setError(e.message || "Failed to load cases. Check backend connection.")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchCases()
  }, [])

  // Replace polling with real-time subscriptions
  useRealtimeCases({
    facilityId,
    onInsert: (newCase) => {
      setCases((prev) => {
        // Avoid duplicates (offline sync may have already added it optimistically)
        if (prev.find((c) => c.id === newCase.id)) return prev
        return [newCase, ...prev]
      })
      // Show toast for EMERGENCY cases
      if (newCase.triage_level === 'EMERGENCY') {
        showToast('New EMERGENCY case received', 'error')
      }
    },
    onUpdate: (updatedCase) => {
      setCases((prev) =>
        prev.map((c) => (c.id === updatedCase.id ? updatedCase : c))
      )
    },
  })

  // Client-side filter: 'pending' shows unreviewed only, 'all' shows everything
  const visibleCases = filter === 'pending'
    ? cases.filter(c => !c.reviewed_at)
    : cases

  const emergency = visibleCases.filter(c => c.triage_level === 'EMERGENCY')
  const urgent    = visibleCases.filter(c => c.triage_level === 'URGENT')
  const routine   = visibleCases.filter(c => c.triage_level === 'ROUTINE')

  if (loading) {
    return (
      <div className="max-w-2xl mx-auto p-4 mt-8 text-center text-text3">
        Loading cases...
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
          {emergency.map(c => <BriefingCard key={c.id} caseData={c} onReviewed={() => {}} />)}
        </div>
      )}

      {urgent.length > 0 && (
        <div className="mb-8">
          <h2 className="text-xs font-mono font-bold text-urgent uppercase tracking-widest mb-3 flex items-center gap-2">
            Urgent <span className="bg-urgent/10 text-urgent px-2 py-0.5 rounded-pill">{urgent.length}</span>
          </h2>
          {urgent.map(c => <BriefingCard key={c.id} caseData={c} onReviewed={() => {}} />)}
        </div>
      )}

      {routine.length > 0 && (
        <div className="mb-8">
          <h2 className="text-xs font-mono font-bold text-routine uppercase tracking-widest mb-3 flex items-center gap-2">
            Routine <span className="bg-routine/10 text-routine px-2 py-0.5 rounded-pill">{routine.length}</span>
          </h2>
          {routine.map(c => <BriefingCard key={c.id} caseData={c} onReviewed={() => {}} />)}
        </div>
      )}
    </div>
  )
}
