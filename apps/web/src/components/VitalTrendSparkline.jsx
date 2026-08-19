import { buildSparklinePath, finiteValues, formatTrendSummary } from '../utils/vitalTrend'

export default function VitalTrendSparkline({ label, unit, color, values }) {
  const points = finiteValues(values)
  if (points.length < 2) return null

  const path = buildSparklinePath(points)
  const summary = formatTrendSummary(label, points, unit)

  return (
    <div className="flex items-center gap-3 rounded-lg bg-surface2 px-3 py-2">
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-2">
          <span className="text-xs font-medium text-text">{label}</span>
          <span className="text-[11px] text-text3">{points[points.length - 1]} {unit}</span>
        </div>
        <svg
          viewBox="0 0 180 48"
          role="img"
          aria-label={summary}
          className="mt-1 h-10 w-full overflow-visible"
          preserveAspectRatio="none"
        >
          <path
            d={path}
            fill="none"
            stroke={color}
            strokeWidth="3"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
        <span className="sr-only">{summary}</span>
      </div>
    </div>
  )
}
