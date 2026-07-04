// frontend/src/components/AnalyticsDashboard.jsx
import { useState, useEffect } from 'react'
import { useAuth } from '../store/authStore'
import { useRealtimeCases } from '../hooks/useRealtimeCases'
import { getAnalyticsSummary, getResponseTimes, exportCases } from '../lib/api'

function todayIso() {
  return new Date().toISOString().slice(0, 10)
}

function daysAgoIso(days) {
  const d = new Date()
  d.setDate(d.getDate() - days)
  return d.toISOString().slice(0, 10)
}

const TRIAGE_COLORS = {
  EMERGENCY: 'bg-emergency',
  URGENT: 'bg-urgent',
  ROUTINE: 'bg-routine',
}

const TRIAGE_TEXT_COLORS = {
  EMERGENCY: 'text-emergency',
  URGENT: 'text-urgent',
  ROUTINE: 'text-routine',
}

function formatMinutes(mins) {
  if (mins == null) return '—'
  if (mins < 60) return `${Math.round(mins)}m`
  return `${(mins / 60).toFixed(1)}h`
}

export default function AnalyticsDashboard() {
  const { profile } = useAuth()
  const [stats, setStats] = useState(null)
  const [responseTimes, setResponseTimes] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [liveCount, setLiveCount] = useState(0)
  const [exportFrom, setExportFrom] = useState(daysAgoIso(30))
  const [exportTo, setExportTo] = useState(todayIso())
  const [exporting, setExporting] = useState(false)
  const [exportError, setExportError] = useState(null)

  const facilityId = profile?.facility_id

  async function handleExport() {
    setExporting(true)
    setExportError(null)
    try {
      await exportCases({ dateFrom: exportFrom, dateTo: exportTo })
    } catch (err) {
      setExportError(err.message)
    } finally {
      setExporting(false)
    }
  }

  async function fetchStats() {
    try {
      const data = await getAnalyticsSummary()
      setStats(data)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchStats()
    getResponseTimes().then(setResponseTimes).catch(() => {})
  }, [])

  // Live case counter — increments on every new INSERT
  useRealtimeCases({
    facilityId,
    onInsert: () => {
      setLiveCount((n) => n + 1)
      // Re-fetch full stats every 5 new cases to keep chart accurate
      if ((liveCount + 1) % 5 === 0) fetchStats()
    },
  })

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <p className="text-sm text-text3">Loading analytics…</p>
      </div>
    )
  }

  if (error) {
    return (
      <div className="rounded-lg border border-emergency/30 bg-emergency/5 p-4">
        <p className="text-sm text-emergency">Failed to load analytics: {error}</p>
      </div>
    )
  }

  const { triage_distribution, daily_volume, total_cases, reviewed_count,
          unreviewed_count, top_asha_workers } = stats

  const totalTriage = Object.values(triage_distribution).reduce((a, b) => a + b, 0)
  const sortedDays = Object.entries(daily_volume).sort(([a], [b]) => a.localeCompare(b))
  const maxDaily = Math.max(...sortedDays.map(([, v]) => v), 1)

  return (
    <div className="space-y-6">

      {/* Live indicator */}
      {liveCount > 0 && (
        <div className="flex items-center gap-2 text-xs text-routine font-mono">
          <span className="inline-block h-2 w-2 rounded-full bg-routine animate-pulse" />
          {liveCount} new case{liveCount > 1 ? 's' : ''} since page load
        </div>
      )}

      {/* Summary cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        {[
          { label: 'Total Cases', value: total_cases },
          { label: 'Reviewed', value: reviewed_count },
          { label: 'Pending Review', value: unreviewed_count },
          { label: 'Emergency', value: triage_distribution.EMERGENCY },
        ].map(({ label, value }) => (
          <div key={label} className="rounded-lg border border-leaf/40 bg-surface p-4 shadow-card hover:shadow-card-hover transition-shadow duration-200">
            <p className="text-xs font-mono font-medium uppercase tracking-wide text-text3">{label}</p>
            <p className="mt-1 text-2xl font-bold text-text">{value}</p>
          </div>
        ))}
      </div>

      {/* Triage distribution bar */}
      <div className="rounded-lg border border-leaf/40 bg-surface p-4 shadow-card">
        <p className="mb-3 text-xs font-mono font-semibold uppercase tracking-wide text-text3">
          Triage Distribution
        </p>
        <div className="flex h-5 w-full overflow-hidden rounded-pill">
          {['EMERGENCY', 'URGENT', 'ROUTINE'].map((level) => {
            const pct = totalTriage > 0
              ? (triage_distribution[level] / totalTriage) * 100
              : 0
            return (
              <div
                key={level}
                className={`${TRIAGE_COLORS[level]} transition-all duration-500`}
                style={{ width: `${pct}%` }}
                title={`${level}: ${triage_distribution[level]} (${pct.toFixed(1)}%)`}
              />
            )
          })}
        </div>
        <div className="mt-2 flex gap-4">
          {['EMERGENCY', 'URGENT', 'ROUTINE'].map((level) => (
            <div key={level} className="flex items-center gap-1.5">
              <span className={`inline-block h-2.5 w-2.5 rounded-sm ${TRIAGE_COLORS[level]}`} />
              <span className="text-xs text-text2 font-mono">
                {level} — {triage_distribution[level]}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Response-time SLA (FEATURES_ROADMAP §1.5) */}
      {responseTimes && (
        <div className="rounded-lg border border-leaf/40 bg-surface p-4 shadow-card">
          <p className="mb-3 text-xs font-mono font-semibold uppercase tracking-wide text-text3">
            Response Times — Last 30 Days
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {['EMERGENCY', 'URGENT', 'ROUTINE'].map((level) => {
              const t = responseTimes.tiers[level]
              return (
                <div key={level} className="rounded-lg border border-leaf/20 p-3">
                  <p className={`text-xs font-mono font-bold uppercase tracking-wider ${TRIAGE_TEXT_COLORS[level]}`}>
                    {level}
                  </p>
                  <div className="mt-2 flex justify-between text-sm">
                    <span className="text-text3">Median</span>
                    <span className="font-mono text-text font-medium">{formatMinutes(t.median_minutes)}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-text3">p90</span>
                    <span className="font-mono text-text font-medium">{formatMinutes(t.p90_minutes)}</span>
                  </div>
                  {t.overdue_count > 0 && (
                    <p className="mt-2 text-xs font-bold text-emergency">
                      {t.overdue_count} overdue (past {formatMinutes(t.overdue_threshold_minutes)})
                    </p>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Daily volume chart (last 7 days) */}
      <div className="rounded-lg border border-leaf/40 bg-surface p-4 shadow-card">
        <p className="mb-4 text-xs font-mono font-semibold uppercase tracking-wide text-text3">
          Daily Volume — Last 7 Days
        </p>
        {sortedDays.length === 0 ? (
          <p className="text-sm text-text3">No data yet.</p>
        ) : (
          <div className="flex items-end gap-2 h-24">
            {sortedDays.map(([day, count]) => (
              <div key={day} className="flex flex-1 flex-col items-center gap-1">
                <span className="text-xs font-medium text-text2 font-mono">{count}</span>
                <div
                  className="w-full rounded-t bg-sage transition-all duration-500"
                  style={{ height: `${(count / maxDaily) * 80}px`, minHeight: '4px' }}
                  title={`${day}: ${count} cases`}
                />
                <span className="text-[10px] text-text3 font-mono">
                  {day.slice(5)} {/* MM-DD */}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Top ASHA workers */}
      {top_asha_workers.length > 0 && (
        <div className="rounded-lg border border-leaf/40 bg-surface p-4 shadow-card">
          <p className="mb-3 text-xs font-mono font-semibold uppercase tracking-wide text-text3">
            Top Submitters — Last 30 Days
          </p>
          <div className="space-y-2">
            {top_asha_workers.map(({ name, count }, i) => (
              <div key={name} className="flex items-center gap-3">
                <span className="w-4 text-xs font-bold text-text3 font-mono">{i + 1}</span>
                <span className="flex-1 text-sm text-text2 truncate">{name}</span>
                <span className="text-xs font-semibold text-text3 font-mono">{count}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* CSV export (FEATURES_ROADMAP §1b.3) */}
      <div className="rounded-lg border border-leaf/40 bg-surface p-4 shadow-card">
        <p className="mb-3 text-xs font-mono font-semibold uppercase tracking-wide text-text3">
          Export Case Data
        </p>
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-xs text-text3">From</span>
            <input
              type="date"
              value={exportFrom}
              max={exportTo}
              onChange={(e) => setExportFrom(e.target.value)}
              className="rounded-lg border border-leaf/40 bg-bg px-2 py-1.5 text-sm text-text"
            />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-xs text-text3">To</span>
            <input
              type="date"
              value={exportTo}
              min={exportFrom}
              max={todayIso()}
              onChange={(e) => setExportTo(e.target.value)}
              className="rounded-lg border border-leaf/40 bg-bg px-2 py-1.5 text-sm text-text"
            />
          </label>
          <button
            onClick={handleExport}
            disabled={exporting}
            className="rounded-lg bg-forest px-4 py-1.5 text-sm font-semibold text-white hover:bg-forest/90 transition-colors disabled:opacity-60"
          >
            {exporting ? 'Exporting…' : 'Download CSV'}
          </button>
        </div>
        {exportError && (
          <p className="mt-2 text-xs text-emergency">Export failed: {exportError}</p>
        )}
      </div>

    </div>
  )
}
