// frontend/src/components/OutbreakSignals.jsx
//
// EARS C1 aberration signals (docs/DECISIONS.md §26) — an informational aid
// for a human to review, not a validated public-health surveillance system.
// Shows aggregate (facility, symptom, day) counts only — no patient names,
// no individual case content, ever.
import { useState, useEffect, useCallback } from 'react'
import { getOutbreakSignals } from '../lib/api'

function formatSymptom(id) {
  return id.split('_').map((w) => w[0].toUpperCase() + w.slice(1)).join(' ')
}

export default function OutbreakSignals() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchSignals = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await getOutbreakSignals()
      setData(result)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchSignals()
  }, [fetchSignals])

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-sm font-mono font-semibold uppercase tracking-wide text-text3">
          Outbreak Signals
        </h2>
        <p className="mt-1 text-xs text-text3">
          Informational only — an aberration-detection aid (EARS C1 method) for a
          human to review, not a validated surveillance system or an automated alert.
          Shows aggregate symptom counts, never individual case content.
        </p>
      </div>

      {loading && <p className="text-sm text-text3 py-8 text-center">Checking for signals…</p>}

      {error && (
        <div className="rounded-lg border border-emergency/30 bg-emergency/5 p-4">
          <p className="text-sm text-emergency">Failed to load outbreak signals: {error}</p>
        </div>
      )}

      {!loading && !error && data && data.signals.length === 0 && (
        <p className="text-sm text-routine py-8 text-center">
          No elevated symptom clusters today ({data.date}).
        </p>
      )}

      {!loading && !error && data && data.signals.length > 0 && (
        <div className="space-y-2">
          {data.signals.map((s, i) => (
            <div
              key={`${s.facility_id}-${s.symptom}-${i}`}
              className="rounded-lg border border-urgent/40 bg-urgent/5 p-4 shadow-card"
            >
              <div className="flex items-center justify-between">
                <p className="font-medium text-text">{formatSymptom(s.symptom)}</p>
                <span className="text-xs font-mono px-2 py-0.5 rounded-pill bg-urgent/10 text-urgent-ink">
                  {s.today_count} today
                </span>
              </div>
              <p className="mt-1 text-xs text-text3 font-mono">
                7-day baseline: {s.baseline_mean} ± {s.baseline_stddev} (threshold {s.threshold})
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
