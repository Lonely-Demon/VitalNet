const DEFAULT_WIDTH = 180
const DEFAULT_HEIGHT = 48
const PADDING = 4

export function finiteValues(values = []) {
  return values
    .filter((value) => value !== null && value !== undefined && value !== '')
    .map(Number)
    .filter(Number.isFinite)
}

export function buildSparklinePath(values, width = DEFAULT_WIDTH, height = DEFAULT_HEIGHT) {
  const points = finiteValues(values)
  if (points.length === 0) return ''
  if (points.length === 1) {
    const y = height / 2
    return `M ${width / 2} ${y}`
  }

  const min = Math.min(...points)
  const max = Math.max(...points)
  const range = max - min || 1
  const xStep = (width - PADDING * 2) / (points.length - 1)
  const drawableHeight = height - PADDING * 2

  return points.map((value, index) => {
    const x = PADDING + index * xStep
    const y = height - PADDING - ((value - min) / range) * drawableHeight
    return `${index === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`
  }).join(' ')
}

export function formatTrendSummary(label, values, unit) {
  const points = finiteValues(values)
  if (points.length === 0) return `${label}: no recorded values`
  return `${label} over ${points.length} visits: ${points.join(', ')} ${unit}`
}

export const VITAL_TREND_DEFINITIONS = [
  { key: 'heart_rate', label: 'Heart rate', unit: 'bpm', color: '#256f5b' },
  { key: 'bp_systolic', label: 'Systolic blood pressure', unit: 'mmHg', color: '#7c3aed' },
  { key: 'bp_diastolic', label: 'Diastolic blood pressure', unit: 'mmHg', color: '#a855f7' },
  { key: 'spo2', label: 'Oxygen saturation', unit: '%', color: '#0369a1' },
  { key: 'temperature', label: 'Temperature', unit: '°C', color: '#c2410c' },
]
