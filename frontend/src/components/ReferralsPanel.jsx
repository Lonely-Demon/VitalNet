// frontend/src/components/ReferralsPanel.jsx
// Inter-facility referral workflow (FEATURES_ROADMAP §2.3) — outgoing and
// incoming referrals for the calling doctor's facility (or all, for admin).
import { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../store/authStore'
import { useRealtimeReferrals } from '../hooks/useRealtimeReferrals'
import { listReferrals, updateReferralStatus } from '../lib/api'

const STATUS_COLORS = {
  pending: 'bg-urgent/10 text-urgent',
  acknowledged: 'bg-sage/20 text-forest',
  patient_arrived: 'bg-sage/20 text-forest',
  completed: 'bg-routine/10 text-routine',
  cancelled: 'bg-surface3 text-text3',
}

const NEXT_ACTIONS = {
  pending: [{ status: 'acknowledged', label: 'Acknowledge' }],
  acknowledged: [{ status: 'patient_arrived', label: 'Patient Arrived' }],
  patient_arrived: [{ status: 'completed', label: 'Complete' }],
}

const URGENCY_TEXT_COLORS = {
  EMERGENCY: 'text-emergency',
  URGENT: 'text-urgent',
  ROUTINE: 'text-routine',
}

export default function ReferralsPanel() {
  const { profile } = useAuth()
  const facilityId = profile?.facility_id
  const [direction, setDirection] = useState('all')
  const [referrals, setReferrals] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [actioningId, setActioningId] = useState(null)

  const fetchReferrals = useCallback(async () => {
    try {
      const data = await listReferrals({ direction })
      setReferrals(data.referrals || [])
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [direction])

  useEffect(() => {
    setLoading(true)
    fetchReferrals()
  }, [fetchReferrals])

  useRealtimeReferrals({
    facilityId: profile?.role === 'admin' ? null : facilityId,
    onInsert: () => fetchReferrals(),
    onUpdate: () => fetchReferrals(),
  })

  async function handleAdvance(referralId, status) {
    setActioningId(referralId)
    try {
      await updateReferralStatus(referralId, status)
      await fetchReferrals()
    } catch (e) {
      alert(e.message)
    } finally {
      setActioningId(null)
    }
  }

  async function handleCancel(referralId) {
    if (!confirm('Cancel this referral?')) return
    handleAdvance(referralId, 'cancelled')
  }

  if (loading) return <div className="text-center py-16 text-text3 text-sm">Loading referrals…</div>
  if (error) return <div className="bg-emergency/10 border border-emergency/30 rounded-lg px-4 py-3 text-emergency text-sm">{error}</div>

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-base font-semibold text-text font-display italic">
          Referrals <span className="text-text3 font-normal font-body">({referrals.length})</span>
        </h2>
        <div className="flex gap-1">
          {['all', 'incoming', 'outgoing'].map((d) => (
            <button
              key={d}
              onClick={() => setDirection(d)}
              className={`text-xs px-3 py-1.5 rounded-pill font-medium capitalize transition-all ${
                direction === d ? 'bg-forest text-white' : 'bg-surface2 text-text2 hover:bg-surface3'
              }`}
            >
              {d}
            </button>
          ))}
        </div>
      </div>

      {referrals.length === 0 ? (
        <div className="text-center py-16 text-text3 text-sm">No referrals.</div>
      ) : (
        <div className="space-y-3">
          {referrals.map((r) => {
            const isReceivingFacility = profile?.role === 'admin' || r.receiving_facility_id === facilityId
            const nextActions = isReceivingFacility ? (NEXT_ACTIONS[r.status] || []) : []
            const canCancel = isReceivingFacility && ['pending', 'acknowledged', 'patient_arrived'].includes(r.status)
            const c = r.case_records || {}

            return (
              <div key={r.id} className="bg-surface border border-leaf/40 rounded-lg p-4 shadow-card">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className={`text-xs px-2 py-0.5 rounded-pill font-medium font-mono capitalize ${STATUS_COLORS[r.status]}`}>
                        {r.status.replace('_', ' ')}
                      </span>
                      <span className={`text-xs font-mono font-bold ${URGENCY_TEXT_COLORS[r.urgency]}`}>
                        {r.urgency}
                      </span>
                    </div>
                    <p className="text-sm font-medium text-text">
                      {c.patient_age}{c.patient_sex === 'male' ? 'M' : c.patient_sex === 'female' ? 'F' : ''}
                      {c.chief_complaint && <> · {c.chief_complaint}</>}
                    </p>
                    <p className="text-xs text-text2 mt-1">
                      {r.referring_facility?.name || 'Unknown facility'} → {r.receiving_facility?.name || 'Unknown facility'}
                    </p>
                    <p className="text-sm text-text2 mt-1">{r.reason}</p>
                    <p className="text-xs text-text3 mt-1 font-mono">
                      {new Date(r.created_at).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' })}
                    </p>
                  </div>
                  {(nextActions.length > 0 || canCancel) && (
                    <div className="flex flex-col gap-1.5 shrink-0">
                      {nextActions.map((a) => (
                        <button
                          key={a.status}
                          onClick={() => handleAdvance(r.id, a.status)}
                          disabled={actioningId === r.id}
                          className="text-xs px-3 py-1.5 bg-forest text-white rounded-pill hover:shadow-btn disabled:opacity-50 transition-all whitespace-nowrap"
                        >
                          {actioningId === r.id ? '…' : a.label}
                        </button>
                      ))}
                      {canCancel && (
                        <button
                          onClick={() => handleCancel(r.id)}
                          disabled={actioningId === r.id}
                          className="text-xs px-3 py-1.5 text-emergency hover:text-emergency/80 font-medium disabled:opacity-50"
                        >
                          Cancel
                        </button>
                      )}
                    </div>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
