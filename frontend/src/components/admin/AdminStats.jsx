import { useState, useEffect } from 'react'
import { adminGetStats } from '../../lib/api'

function StatCard({ title, main, sub, children }) {
  return (
    <div className="bg-surface border border-leaf/40 rounded-lg shadow-card hover:shadow-card-hover transition-shadow duration-200 px-5 py-4">
      <p className="text-xs font-mono font-semibold text-text3 uppercase tracking-wider mb-1">{title}</p>
      <p className="text-3xl font-bold text-text mb-3">{main}</p>
      {sub && <p className="text-sm text-text2 mb-3">{sub}</p>}
      <div className="space-y-1.5">{children}</div>
    </div>
  )
}

function SubStat({ label, value, color }) {
  return (
    <div className="flex items-center justify-between">
      <span className={`text-xs font-medium font-mono ${color}`}>{label}</span>
      <span className={`text-sm font-bold font-mono ${color}`}>{value}</span>
    </div>
  )
}

export default function AdminStats() {
  const [stats,   setStats]   = useState(null)
  const [loading, setLoading] = useState(true)
  const [error,   setError]   = useState(null)

  useEffect(() => {
    adminGetStats()
      .then(setStats)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <div className="text-center py-16 text-text3 text-sm">Loading stats...</div>
  if (error)   return <div className="bg-emergency/10 border border-emergency/30 rounded-lg px-4 py-3 text-emergency text-sm">{error}</div>

  const { total_cases, triage_counts, total_users, active_users, role_counts } = stats

  return (
    <div>
      <h2 className="text-base font-semibold text-text mb-4 font-display italic">System</h2>
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">

        <StatCard
          title="Cases"
          main={total_cases}
          sub="Total submitted"
        >
          <SubStat label="Emergency" value={triage_counts.EMERGENCY} color="text-emergency" />
          <SubStat label="Urgent"    value={triage_counts.URGENT}    color="text-urgent" />
          <SubStat label="Routine"   value={triage_counts.ROUTINE}   color="text-routine" />
        </StatCard>

        <StatCard
          title="Users"
          main={total_users}
          sub={`${active_users} active`}
        >
          <SubStat label="ASHA Workers" value={role_counts.asha_worker ?? 0} color="text-routine" />
          <SubStat label="Doctors"      value={role_counts.doctor      ?? 0} color="text-sage" />
          <SubStat label="Admins"       value={role_counts.admin       ?? 0} color="text-text2" />
        </StatCard>

        <StatCard
          title="Analytics"
          main="—"
          sub="Coming in Phase 10"
        >
          <p className="text-xs text-text3">
            Advanced analytics dashboard, trend charts, and facility heatmaps will be available in a future phase.
          </p>
        </StatCard>

      </div>
    </div>
  )
}
