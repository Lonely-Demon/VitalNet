// frontend/src/components/TeamMetrics.jsx
//
// Per-ASHA-worker aggregate metrics for supportive supervision
// (docs/DECISIONS.md §25). Deliberately shows only aggregates — counts and
// rates — never an individual case row, chief complaint, or patient field.
import { useState, useEffect, useCallback } from 'react'
import { getTeamMetrics } from '../lib/api'

const WINDOW_OPTIONS = [
  { label: '7 days', value: 7 },
  { label: '30 days', value: 30 },
  { label: '90 days', value: 90 },
]

function formatPct(rate) {
  return rate == null ? '—' : `${Math.round(rate * 100)}%`
}

export default function TeamMetrics() {
  const [days, setDays] = useState(30)
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetchMetrics = useCallback(async (window) => {
    setLoading(true)
    setError(null)
    try {
      const result = await getTeamMetrics({ days: window })
      setData(result)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchMetrics(days)
  }, [days, fetchMetrics])

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between flex-wrap gap-2">
        <h2 className="text-sm font-mono font-semibold uppercase tracking-wide text-text3">
          Team Metrics
        </h2>
        <div className="flex gap-1">
          {WINDOW_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              onClick={() => setDays(opt.value)}
              className={`rounded-pill px-3 py-1 text-xs font-mono transition-colors ${
                days === opt.value
                  ? 'bg-forest text-white'
                  : 'bg-surface border border-leaf/40 text-text2 hover:bg-leaf/10'
              }`}
            >
              {opt.label}
            </button>
          ))}
        </div>
      </div>

      {loading && <p className="text-sm text-text3 py-8 text-center">Loading team metrics…</p>}

      {error && (
        <div className="rounded-lg border border-emergency/30 bg-emergency/5 p-4">
          <p className="text-sm text-emergency">Failed to load team metrics: {error}</p>
        </div>
      )}

      {!loading && !error && data && data.workers.length === 0 && (
        <p className="text-sm text-text3 py-8 text-center">
          No submissions from your facility's ASHA workers in the last {days} days.
        </p>
      )}

      {!loading && !error && data && data.workers.length > 0 && (
        <div className="overflow-x-auto rounded-lg border border-leaf/40 bg-surface shadow-card">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-leaf/40 text-left text-xs font-mono uppercase tracking-wide text-text3">
                <th className="px-4 py-2">Worker</th>
                <th className="px-4 py-2 text-right">Submissions</th>
                <th className="px-4 py-2 text-right">Needs Review</th>
                <th className="px-4 py-2 text-right">Contraindication Flags</th>
                <th className="px-4 py-2 text-right">Deterioration Alerts</th>
                <th className="px-4 py-2 text-right">Emergency</th>
                <th className="px-4 py-2 text-right">Urgent</th>
                <th className="px-4 py-2 text-right">Routine</th>
              </tr>
            </thead>
            <tbody>
              {data.workers.map((w) => (
                <tr key={w.user_id} className="border-b border-leaf/20 last:border-0">
                  <td className="px-4 py-2 font-medium text-text">{w.full_name}</td>
                  <td className="px-4 py-2 text-right font-mono text-text">{w.submission_count}</td>
                  <td className="px-4 py-2 text-right font-mono text-text2">
                    {w.needs_review_count} ({formatPct(w.needs_review_rate)})
                  </td>
                  <td className="px-4 py-2 text-right font-mono text-text2">
                    {w.contraindication_flag_count} ({formatPct(w.contraindication_flag_rate)})
                  </td>
                  <td className="px-4 py-2 text-right font-mono text-text2">
                    {w.deterioration_alert_count} ({formatPct(w.deterioration_alert_rate)})
                  </td>
                  <td className="px-4 py-2 text-right font-mono text-emergency">
                    {w.tier_distribution.EMERGENCY}
                  </td>
                  <td className="px-4 py-2 text-right font-mono text-urgent">
                    {w.tier_distribution.URGENT}
                  </td>
                  <td className="px-4 py-2 text-right font-mono text-routine">
                    {w.tier_distribution.ROUTINE}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
