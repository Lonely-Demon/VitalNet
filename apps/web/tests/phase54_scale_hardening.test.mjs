// apps/web/tests/phase54_scale_hardening.test.mjs
// Verification test suite for Milestone 2 Phase 54 Performance, Indexing & Scale Hardening:
// - F-01: Web Locks cross-tab mutual exclusion in syncStore.js
// - F-02: HTTP 429 Retry-After backoff & non-deadlettering
// - F-14: Lazy decryption via getPendingEventMetas in outbox.js
// - F-15: Single primaryFilter with client-side secondary guard in useRealtimeCases.js

import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

test('F-01: syncStore.js wraps processQueue in Web Locks API with fallback', () => {
  const syncStorePath = path.resolve('apps/web/src/stores/syncStore.js')
  const src = fs.readFileSync(syncStorePath, 'utf8')

  assert.ok(
    src.includes("navigator.locks.request("),
    'syncStore.js must use navigator.locks.request'
  )
  assert.ok(
    src.includes("'vitalnet_outbox_drain'"),
    'syncStore.js must name the lock vitalnet_outbox_drain'
  )
  assert.ok(
    src.includes("{ ifAvailable: true }"),
    'syncStore.js must request lock with { ifAvailable: true }'
  )
  assert.ok(
    src.includes("_drainOutboxCore"),
    'syncStore.js must delegate to _drainOutboxCore'
  )
  assert.ok(
    src.includes("_activeDrainPromise = null"),
    'syncStore.js must reset _activeDrainPromise'
  )
})

test('F-01 regression: processQueue resets _activeDrainPromise on lock contention allowing subsequent drains', async () => {
  const syncStorePath = path.resolve('apps/web/src/stores/syncStore.js')
  const src = fs.readFileSync(syncStorePath, 'utf8')

  // Extract processQueue implementation from syncStore.js
  const match = src.match(/export async function processQueue\(\) \{[\s\S]*?\n\}/)
  assert.ok(match, 'processQueue function must be found in syncStore.js')
  const fnBody = match[0].replace('export async function processQueue()', 'async function processQueue()')

  const factory = new Function(
    'navigator',
    '_drainOutboxCore',
    `let _activeDrainPromise = null;
${fnBody}
return {
  processQueue,
  getActiveDrainPromise: () => _activeDrainPromise
};`
  )

  let lockContended = true
  let drainCalls = 0
  const mockDrainOutboxCore = async () => {
    drainCalls++
    return { synced: 1, failed: 0, dead: 0 }
  }

  let locksRequestCalls = 0
  const mockNavigator = {
    locks: {
      request: async (name, options, callback) => {
        locksRequestCalls++
        assert.equal(name, 'vitalnet_outbox_drain')
        assert.equal(options?.ifAvailable, true)
        if (lockContended) {
          return callback(null)
        }
        return callback({ name })
      }
    }
  }

  const { processQueue, getActiveDrainPromise } = factory(mockNavigator, mockDrainOutboxCore)

  // Invocation 1: Contended lock (simulating another tab holding vitalnet_outbox_drain)
  const result1 = await processQueue()
  assert.deepEqual(result1, { synced: 0, failed: 0, dead: 0, locked: true }, 'Must return locked: true when contended')
  assert.equal(drainCalls, 0, 'Must NOT invoke _drainOutboxCore when lock is not acquired')
  assert.equal(locksRequestCalls, 1, 'Must request lock on first invocation')
  assert.equal(getActiveDrainPromise(), null, '_activeDrainPromise must be reset to null via .finally')

  // Release contention
  lockContended = false

  // Invocation 2: Subsequent call when lock is now free
  const result2 = await processQueue()
  assert.deepEqual(result2, { synced: 1, failed: 0, dead: 0 }, 'Must successfully acquire lock and drain on subsequent invocation')
  assert.equal(drainCalls, 1, 'Must invoke _drainOutboxCore when lock is acquired')
  assert.equal(locksRequestCalls, 2, 'Must request lock again instead of returning cached locked: true promise')
  assert.equal(getActiveDrainPromise(), null, '_activeDrainPromise must be reset to null after draining')
})

test('F-02: syncStore.js isolates HTTP 429 from 4xx and applies bounded Retry-After backoff without dead-lettering', () => {
  const syncStorePath = path.resolve('apps/web/src/stores/syncStore.js')
  const src = fs.readFileSync(syncStorePath, 'utf8')

  // HTTP 429 check in drainCaseSubmit
  assert.ok(
    src.includes("res.status === 429"),
    'syncStore.js must explicitly check for res.status === 429'
  )
  assert.ok(
    src.includes("res.headers.get('Retry-After')"),
    'syncStore.js must inspect Retry-After header'
  )
  assert.ok(
    src.includes("Math.min(Math.max(Number.isFinite(retryAfterSec) ? retryAfterSec : 5, 1), 60) * 1000"),
    'syncStore.js must enforce bounded backoff [1, 60] seconds'
  )
  assert.ok(
    src.includes("return 'rate_limited'"),
    'syncStore.js must return rate_limited outcome on 429'
  )
  assert.ok(
    src.includes("outcome === 'rate_limited'"),
    'syncStore.js must abort queue loop on rate_limited without dead-lettering'
  )
})

test('F-14: outbox.js exports getPendingEventMetas and getEventPayload for lazy decryption', () => {
  const outboxPath = path.resolve('apps/web/src/lib/outbox.js')
  const src = fs.readFileSync(outboxPath, 'utf8')

  assert.ok(
    src.includes("export async function getPendingEventMetas(ownerId)"),
    'outbox.js must export getPendingEventMetas'
  )
  assert.ok(
    src.includes("export async function getEventPayload(eventId, ownerId)"),
    'outbox.js must export getEventPayload'
  )

  // Verify getPendingEventMetas returns only metadata fields without decrypting payload
  const metaFnMatch = src.match(/export async function getPendingEventMetas\([\s\S]*?\n\}/)
  assert.ok(metaFnMatch, 'getPendingEventMetas must be defined')
  const fnBody = metaFnMatch[0]
  assert.ok(!fnBody.includes("decryptOutboxPayload"), 'getPendingEventMetas must NOT invoke decryptOutboxPayload')
  assert.ok(fnBody.includes("intake_monotonic_ms"), 'getPendingEventMetas must include intake_monotonic_ms')
  assert.ok(fnBody.includes("enqueued_time_origin"), 'getPendingEventMetas must include enqueued_time_origin')
})

test('F-15: useRealtimeCases.js defines single primaryFilter and client-side secondary guard', () => {
  const hookPath = path.resolve('apps/web/src/hooks/useRealtimeCases.js')
  const src = fs.readFileSync(hookPath, 'utf8')

  assert.ok(
    src.includes("const primaryFilter = facilityId"),
    'useRealtimeCases.js must construct primaryFilter'
  )
  assert.ok(
    src.includes("'facility_id=eq.' + facilityId") && src.includes("'submitted_by=eq.' + userId"),
    'useRealtimeCases.js must prioritize facility_id with fallback to submitted_by'
  )
  assert.ok(
    src.includes("if (facilityId && userId && payload.new?.submitted_by !== userId)"),
    'useRealtimeCases.js must filter secondary userId client-side when both are provided'
  )
})

test('Reconnect jitter: syncStore.js and ASHAPanel.jsx apply 0-2000ms randomized jitter on online event', () => {
  const syncStorePath = path.resolve('apps/web/src/stores/syncStore.js')
  const syncStoreSrc = fs.readFileSync(syncStorePath, 'utf8')
  assert.ok(
    syncStoreSrc.includes("Math.floor(Math.random() * 2000)"),
    'syncStore.js must apply 0-2000ms jitter on online event'
  )

  const ashaPanelPath = path.resolve('apps/web/src/panels/ASHAPanel.jsx')
  const ashaPanelSrc = fs.readFileSync(ashaPanelPath, 'utf8')
  assert.ok(
    ashaPanelSrc.includes("Math.floor(Math.random() * 2000)"),
    'ASHAPanel.jsx must apply 0-2000ms jitter on online event'
  )
})
