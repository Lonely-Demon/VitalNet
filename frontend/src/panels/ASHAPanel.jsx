import { useState, useEffect } from 'react'
import NavBar from '../components/NavBar'
import IntakeForm from '../pages/IntakeForm'
import OfflineBanner from '../components/OfflineBanner'
import { getMySubmissions, processQueue } from '../lib/api'
import { useToast } from '../components/ToastProvider'

const TABS = [
  { id: 'new',     label: 'New Case' },
  { id: 'history', label: 'My Submissions' },
]

const TRIAGE_STYLES = {
  EMERGENCY: 'bg-red-100 text-red-700 border-red-200',
  URGENT:    'bg-amber-100 text-amber-700 border-amber-200',
  ROUTINE:   'bg-emerald-100 text-emerald-700 border-emerald-200',
}

export default function ASHAPanel() {
  const [activeTab,   setActiveTab]   = useState('new')
  const [submissions, setSubmissions] = useState([])
  const [loading,     setLoading]     = useState(false)
  const [error,       setError]       = useState(null)
  const { showToast } = useToast()

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
    <div className="min-h-screen bg-slate-50">
      <NavBar tabs={TABS} activeTab={activeTab} onTabChange={setActiveTab} />
      <OfflineBanner />

      <main className="max-w-2xl mx-auto px-4 py-6">
        {activeTab === 'new' && <IntakeForm />}

        {activeTab === 'history' && (
          <div>
            <h2 className="text-base font-semibold text-slate-800 mb-4">My Submissions</h2>

            {loading && (
              <div className="text-center py-12 text-slate-400 text-sm">Loading...</div>
            )}

            {error && (
              <div className="bg-red-50 border border-red-200 rounded-lg px-4 py-3 text-red-700 text-sm">
                {error}
              </div>
            )}

            {!loading && !error && submissions.length === 0 && (
              <div className="text-center py-12 text-slate-400 text-sm">
                No submissions yet.
              </div>
            )}

            {!loading && submissions.map(s => (
              <div
                key={s.id}
                className="bg-white rounded-lg border border-slate-200 shadow-sm px-4 py-3 mb-3"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium text-slate-800 truncate">
                      {s.chief_complaint}
                    </p>
                    <p className="text-xs text-slate-400 mt-0.5">
                      {s.patient_age ? `${s.patient_age}y` : '—'}
                      {s.patient_sex ? ` · ${s.patient_sex}` : ''}
                      {' · '}
                      {new Date(s.created_at).toLocaleDateString('en-IN', {
                        day: 'numeric', month: 'short', year: 'numeric',
                      })}
                    </p>
                  </div>
                  <div className="flex flex-col items-end gap-1 shrink-0">
                    <span className={`text-xs px-2 py-0.5 rounded border font-medium ${TRIAGE_STYLES[s.triage_level]}`}>
                      {s.triage_level}
                    </span>
                    {s.reviewed_at && (
                      <span className="text-xs text-emerald-600">✓ Reviewed</span>
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
