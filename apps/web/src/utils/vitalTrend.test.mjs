import test from 'node:test'
import assert from 'node:assert/strict'
import { buildSparklinePath, finiteValues, formatTrendSummary } from './vitalTrend.js'

test('finiteValues removes missing readings without changing numeric order', () => {
  assert.deepEqual(finiteValues([null, 78, undefined, '82', NaN]), [78, 82])
})

test('buildSparklinePath is deterministic and handles a flat series', () => {
  const first = buildSparklinePath([80, 80, 80])
  const second = buildSparklinePath([80, 80, 80])
  assert.equal(first, second)
  assert.match(first, /^M /)
  assert.match(first, /L /)
})

test('formatTrendSummary provides an accessible text alternative', () => {
  assert.equal(
    formatTrendSummary('Heart rate', [78, null, 92], 'bpm'),
    'Heart rate over 2 visits: 78, 92 bpm',
  )
  assert.equal(formatTrendSummary('SpO2', [], '%'), 'SpO2: no recorded values')
})
