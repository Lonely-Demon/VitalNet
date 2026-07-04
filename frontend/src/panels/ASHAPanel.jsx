import { useState, useEffect } from 'react'
import NavBar from '../components/NavBar'
import IntakeForm from '../pages/IntakeForm'
import OfflineBanner from '../components/OfflineBanner'
import { getMySubmissions, processQueue } from '../lib/api'
import { useToast } from '../components/ToastProvider'
import { useAuth } from '../store/authStore'
import { useRealtimeCases } from '../hooks/useRealtimeCases'

const TABS = [
  { id: 'new',     label: 'New Case' },
  { id: 'history', label: 'My Submissions' },
]

const TRIAGE_STYLES = {
  EMERGENCY: 'bg-emergency/10 text-emergency border-emergency/30',
  URGENT:    'bg-urgent/10 text-urgent border-urgent/30',
  ROUTINE:   'bg-routine/10 text-routine border-routine/30',
}

export default function ASHAPanel() {
  const [activeTab,   setActiveTab]   = useState('new')
  const [submissions, setSubmissions] = useState([])
  const [loading,     setLoading]     = useState(false)
  const [error,       setError]       = useState(null)
  const { showToast } = useToast()
  const { session } = useAuth()

  const userId = session?.user?.id

  // Process any queued offline submissions on mount and on every 'online' event
  useEffect(() => {
    processQueue().then(result => {
      if (result.synced > 0) {
        showToast(`${result.synced} offline submission${result.synced > 1 ? 's' : ''} synced`, 'success')
      }
      if (result.requiresLogin) {
        showToast('Please sign in again to sync offline submissions', 'warning')
      }
    })

    function handleOnline() {
      processQueue().then(result => {
        if (result.synced > 0) {
          showToast(`${result.synced} submission${result.synced > 1 ? 's' : ''} synced`, 'success')
        }
        if (result.requiresLogin) {
          showToast('Re-login required to sync offline submissions', 'warning')
        }
      })
    }

    window.addEventListener('online', handleOnline)
    return () => window.removeEventListener('online', handleOnline)
  }, [showToast])

  useEffect(() => {
    if (activeTab === 'history') fetchSubmissions()
  }, [activeTab])

  // Real-time sync for submission history when queued cases are processed
  useRealtimeCases({
    userId,
    onUpdate: (updatedCase) => {
      // Update the submission history when a queued offline case is processed
      setSubmissions((prev) =>
        prev.map((c) => (c.id === updatedCase.id ? {
          ...c,
          triage_level: updatedCase.triage_level,
          reviewed_at: updatedCase.reviewed_at,
        } : c))
      )
    },
  })

  async function fetchSubmissions() {
    setLoading(true)
    setError(null)
    try {
      const data = await getMySubmissions()
      setSubmissions(data)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-bg">
      <NavBar tabs={TABS} activeTab={activeTab} onTabChange={setActiveTab} />
      <OfflineBanner />

      <main className="max-w-2xl mx-auto px-4 py-6">
        {activeTab === 'new' && <IntakeForm />}

        {activeTab === 'history' && (
          <div>
            <h2 className="text-base font-semibold text-text mb-4 font-display italic">My Submissions</h2>

            {loading && (
              <div className="text-center py-12 text-text3 text-sm">Loading...</div>
            )}

            {error && (
              <div className="bg-emergency/10 border border-emergency/30 rounded-lg px-4 py-3 text-emergency text-sm">
                {error}
              </div>
            )}

            {!loading && !error && submissions.length === 0 && (
              <div className="text-center py-12 text-text3 text-sm">
                No submissions yet.
              </div>
            )}

            {!loading && submissions.map(s => (
              <div
                key={s.id}
                className="bg-surface rounded-lg border border-leaf/40 shadow-card px-4 py-3 mb-3 hover:shadow-card-hover transition-shadow duration-200 animate-fade-up"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-text truncate">
                      {s.patient_name || s.chief_complaint}
                    </p>
                    <p className="text-xs text-text2 truncate">
                      {s.patient_name ? s.chief_complaint : ''}
                    </p>
                    <p className="text-xs text-text3 mt-0.5 font-mono">
                      {s.patient_age ? `${s.patient_age}y` : '—'}
                      {s.patient_sex ? ` · ${s.patient_sex}` : ''}
                      {' · '}
                      {new Date(s.created_at).toLocaleDateString('en-IN', {
                        day: 'numeric', month: 'short', year: 'numeric',
                      })}
                    </p>
                  </div>
                  <div className="flex flex-col items-end gap-1 shrink-0">
                    <span className={`text-xs font-mono px-2 py-0.5 rounded-pill border font-medium ${TRIAGE_STYLES[s.triage_level]}`}>
                      {s.triage_level}
                    </span>
                    {s.reviewed_at && (
                      <span className="text-xs text-routine font-mono">✓ Reviewed</span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
