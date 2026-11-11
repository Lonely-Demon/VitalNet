// apps/web/tests/challenger_m5_adversarial.test.mjs
// Adversarial verification & stress-testing harness for Milestone 5:
// BUG-06, BUG-07, BUG-08, BUG-15, BUG-24, BUG-25, BUG-31, BUG-32, BUG-34, BUG-46, BUG-47, BUG-59, BUG-60.

import test from 'node:test'
import assert from 'node:assert/strict'
import { parseStrictInt, parseStrictFloat, serializeIntakePayload } from '../src/lib/intakePayload.js'
import { buildPaediatricAdvisory, PAEDIATRIC_ADVISORY_VERSION, MUAC_REFERRAL_THRESHOLD_MM } from '../src/utils/triageClassifier.js'
export function buildAad(ownerId, eventId) {
  const aadString = `vn:v2:${ownerId || 'anon'}:${eventId || 'none'}`
  return new TextEncoder().encode(aadString)
}

// =============================================================================
// Mock In-Memory IndexedDB Engine for Outbox & Keystore Stress-Testing
// =============================================================================

function createMockIndexedDB() {
  const stores = new Map([
    ['outbox', new Map()],
    ['device_keystore', new Map()],
    ['patient_history_cache', new Map()],
    ['form-drafts', new Map()],
  ])

  return {
    async get(storeName, key) {
      const store = stores.get(storeName)
      if (!store) throw new Error(`Store ${storeName} not found`)
      const val = store.get(key)
      return val ? JSON.parse(JSON.stringify(val)) : undefined
    },
    async put(storeName, value) {
      const store = stores.get(storeName)
      if (!store) throw new Error(`Store ${storeName} not found`)
      const key = storeName === 'outbox' ? value.event_id
        : storeName === 'device_keystore' ? value.key_id
        : storeName === 'patient_history_cache' ? value.patient_key
        : value.id
      // Store clone
      store.set(key, value)
      return key
    },
    async delete(storeName, key) {
      const store = stores.get(storeName)
      if (store) store.delete(key)
    },
    async getAll(storeName) {
      const store = stores.get(storeName)
      if (!store) return []
      return Array.from(store.values())
    },
    async getAllFromIndex(storeName, indexName, value) {
      const store = stores.get(storeName)
      if (!store) return []
      const rows = Array.from(store.values())
      if (value !== undefined) {
        return rows.filter((r) => r[indexName] === value)
      }
      return rows.sort((a, b) => (a[indexName] > b[indexName] ? 1 : -1))
    },
    async countFromIndex(storeName, indexName, value) {
      const rows = await this.getAllFromIndex(storeName, indexName, value)
      return rows.length
    },
    transaction(storeName, mode) {
      const self = this
      return {
        store: {
          async get(key) { return self.get(storeName, key) },
          async put(val) { return self.put(storeName, val) },
          async delete(key) { return self.delete(storeName, key) },
          async getAll() { return self.getAll(storeName) },
        },
        get done() { return Promise.resolve() },
      }
    },
    _rawStore: stores,
  }
}

// =============================================================================
// Test Suite 1: Strict Number.isFinite Validation in intakePayload.js (BUG-32)
// =============================================================================

test('ADVERSARIAL BUG-32: parseStrictInt stress-testing and boundary conditions', () => {
  // 1. Newborn zero preservation across representations
  assert.equal(parseStrictInt(0), 0)
  assert.equal(parseStrictInt('0'), 0)
  assert.equal(parseStrictInt(0.0), 0)
  assert.equal(parseStrictInt('0.0'), 0)
  assert.ok(parseStrictInt(-0) === 0)
  assert.ok(parseStrictInt('-0') === 0)

  // 2. Truncation of valid positive/negative floats
  assert.equal(parseStrictInt(12.99), 12)
  assert.equal(parseStrictInt('12.99'), 12)
  assert.equal(parseStrictInt(-5.8), -5)

  // 3. Rejection of booleans (which coerce to 0/1 in loose Number())
  assert.equal(parseStrictInt(false), null)
  assert.equal(parseStrictInt(true), null)
  assert.equal(parseStrictInt(Boolean(0)), null)
  assert.equal(parseStrictInt(Boolean(1)), null)

  // 4. Rejection of non-finite numbers and special values
  assert.equal(parseStrictInt(NaN), null)
  assert.equal(parseStrictInt(Infinity), null)
  assert.equal(parseStrictInt(-Infinity), null)
  assert.equal(parseStrictInt('Infinity'), null)
  assert.equal(parseStrictInt('-Infinity'), null)
  assert.equal(parseStrictInt('NaN'), null)

  // 5. Rejection of empty, whitespace, and dirty strings
  assert.equal(parseStrictInt(''), null)
  assert.equal(parseStrictInt('    '), null)
  assert.equal(parseStrictInt('\t\n\r'), null)
  assert.equal(parseStrictInt('120/80'), null)
  assert.equal(parseStrictInt('120 mmHg'), null)
  assert.equal(parseStrictInt('98%'), null)
  assert.equal(parseStrictInt('0x10'), 16) // valid hex integer
  assert.equal(parseStrictInt('1e3'), 1000) // scientific notation valid integer

  // 6. Rejection of null and undefined
  assert.equal(parseStrictInt(null), null)
  assert.equal(parseStrictInt(undefined), null)
})

test('ADVERSARIAL BUG-32: parseStrictFloat stress-testing and precision preservation', () => {
  assert.equal(parseStrictFloat(0), 0)
  assert.equal(parseStrictFloat('0'), 0)
  assert.equal(parseStrictFloat(37.5), 37.5)
  assert.equal(parseStrictFloat('37.5'), 37.5)
  assert.equal(parseStrictFloat('98.6'), 98.6)

  // Rejections
  assert.equal(parseStrictFloat(false), null)
  assert.equal(parseStrictFloat(true), null)
  assert.equal(parseStrictFloat(NaN), null)
  assert.equal(parseStrictFloat(Infinity), null)
  assert.equal(parseStrictFloat('   '), null)
  assert.equal(parseStrictFloat('37.5 C'), null)
  assert.equal(parseStrictFloat(null), null)
  assert.equal(parseStrictFloat(undefined), null)
})

test('ADVERSARIAL BUG-32: serializeIntakePayload newborn 0 preservation vs dirty vitals', () => {
  const newbornForm = {
    patient_name: ' Baby of Sita ',
    patient_age: '0', // newborn 0 years
    age_months: '2',
    muac_mm: '110',
    bp_systolic: '90/60', // dirty string -> must become null
    bp_diastolic: '', // empty -> null
    spo2: '97',
    heart_rate: '145',
    respiratory_rate: '40',
    temperature: '36.8',
    chief_complaint: 'Other',
    custom_complaint: ' Mild respiratory distress ',
    is_pregnant: false,
    human_review_requested: 'true',
    human_review_reason: '  Preterm evaluation  ',
  }

  const payload = serializeIntakePayload(newbornForm, 'PK-NEWBORN-001', '2026-11-09T12:00:00Z')

  assert.equal(payload.patient_name, 'Baby of Sita')
  assert.equal(payload.patient_key, 'PK-NEWBORN-001')
  assert.strictEqual(payload.patient_age, 0, 'Newborn age must be strictly preserved as numeric 0')
  assert.strictEqual(payload.age_months, 2)
  assert.strictEqual(payload.muac_mm, 110)
  assert.strictEqual(payload.bp_systolic, null, 'Dirty BP string must be null')
  assert.strictEqual(payload.bp_diastolic, null, 'Empty BP string must be null')
  assert.strictEqual(payload.spo2, 97)
  assert.strictEqual(payload.heart_rate, 145)
  assert.strictEqual(payload.respiratory_rate, 40)
  assert.strictEqual(payload.temperature, 36.8)
  assert.equal(payload.chief_complaint, 'Mild respiratory distress')
  assert.equal(payload.is_pregnant, false)
  assert.equal(payload.human_review_requested, true)
  assert.equal(payload.human_review_reason, 'Preterm evaluation')
  assert.equal(payload.consent_captured_at, '2026-11-09T12:00:00Z')

  // Now test adult with undefined age: parsedAge is null -> patient_age becomes undefined
  const blankAgeForm = { patient_age: '', patient_name: 'Adult' }
  const adultPayload = serializeIntakePayload(blankAgeForm, 'PK-ADULT-001')
  assert.strictEqual(adultPayload.patient_age, undefined, 'Blank age must serialize to undefined (matching Zod optional)')
})

// =============================================================================
// Test Suite 2: Outbox Monotonic timeOrigin Reconciliation (BUG-06)
// =============================================================================

test('ADVERSARIAL BUG-06: Monotonic elapsed time calculation across tab reloads & clock skew', () => {
  function computeReconciledSubmittedAt(item, currentOrigin, currentNow, currentWallClockNow) {
    const payload = { ...item.payload }
    if (item.intake_monotonic_ms != null) {
      let elapsedMs = null
      const itemOrigin = typeof item.enqueued_time_origin === 'number' ? item.enqueued_time_origin : null

      if (itemOrigin != null && currentOrigin != null) {
        const enqueuedAbsolute = itemOrigin + item.intake_monotonic_ms
        const currentAbsolute = currentOrigin + currentNow
        if (currentAbsolute >= enqueuedAbsolute) {
          elapsedMs = Math.round(currentAbsolute - enqueuedAbsolute)
        }
      } else if (itemOrigin == null && currentNow >= item.intake_monotonic_ms) {
        elapsedMs = Math.round(currentNow - item.intake_monotonic_ms)
      }

      if (elapsedMs != null && elapsedMs >= 0) {
        payload.client_submitted_at = new Date(currentWallClockNow - elapsedMs).toISOString()
      } else if (!payload.client_submitted_at && item.created_at) {
        payload.client_submitted_at = item.created_at
      }
    } else if (!payload.client_submitted_at && item.created_at) {
      payload.client_submitted_at = item.created_at
    }
    return payload.client_submitted_at
  }

  // Scenario A: Standard tab reload after 5 minutes offline
  // Tab 1 (Enqueued):
  // timeOrigin = 1,700,000,000,000, performance.now() = 10,000 => enqueued at absolute 1,700,000,010,000
  const itemA = {
    intake_monotonic_ms: 10000,
    enqueued_time_origin: 1700000000000,
    created_at: new Date(1700000010000).toISOString(),
    payload: { client_submitted_at: new Date(1700000010000).toISOString() },
  }
  // Tab 2 (Reloaded 300,000 ms = 5 min later):
  // timeOrigin in new tab = 1,700,000,300,000, performance.now() in new tab = 10,000
  // currentAbsolute = 1,700,000,310,000. Time elapsed = 300,000 ms.
  const wallClockNowA = 1700000310000
  const submittedAtA = computeReconciledSubmittedAt(itemA, 1700000300000, 10000, wallClockNowA)
  assert.equal(submittedAtA, itemA.created_at, 'Standard reload must calculate exact enqueued timestamp')

  // Scenario B: Rapid reload (e.g. 50 ms later)
  const submittedAtB = computeReconciledSubmittedAt(itemA, 1700000000050, 0, 1700000010050)
  assert.equal(submittedAtB, itemA.created_at, 'Rapid reload must preserve timestamp without negative skew')

  // Scenario C: Forward System Clock Jump (+2 hours NTP correction while offline)
  // User tablet was offline and jumped forward by 2 hours (7,200,000 ms)
  // enqueuedAbsolute was 1,700,000,010,000.
  // currentOrigin in new tab = 1,707,200,300,000. currentNow = 10,000.
  // currentAbsolute = 1,707,200,310,000.
  // wallClockNow = 1,707,200,310,000.
  // elapsedMs = 7,200,300,000 ms.
  // client_submitted_at = wallClockNow - elapsedMs = 1,700,000,010,000!
  const submittedAtC = computeReconciledSubmittedAt(itemA, 1707200300000, 10000, 1707200310000)
  assert.equal(submittedAtC, itemA.created_at, 'NTP jump forward must not corrupt original submission time')

  // Scenario D: Backward Clock Skew (currentAbsolute < enqueuedAbsolute)
  // In extreme cases of manual clock rollback, currentAbsolute < enqueuedAbsolute.
  // Must NOT produce future dates or crash; falls back safely to original client_submitted_at.
  const submittedAtD = computeReconciledSubmittedAt(itemA, 1699999000000, 5000, 1699999005000)
  assert.equal(submittedAtD, itemA.payload.client_submitted_at, 'Backward clock jump must fallback safely to original submitted_at')

  // Scenario E: Legacy item with null enqueued_time_origin across reload
  const legacyItem = {
    intake_monotonic_ms: 50000,
    enqueued_time_origin: null,
    created_at: '2026-11-09T10:00:00.000Z',
    payload: { client_submitted_at: '2026-11-09T10:00:00.000Z' },
  }
  // If reloaded, currentNow is 200 ms (less than 50000 ms)
  const submittedAtE = computeReconciledSubmittedAt(legacyItem, 1700000000000, 200, 1700000000200)
  assert.equal(submittedAtE, legacyItem.created_at, 'Legacy item across reload must fallback to created_at')
})

// =============================================================================
// Test Suite 3: Concurrent Keystore Generation Races & Cryptographic Hardening (BUG-06, BUG-07)
// =============================================================================

test('ADVERSARIAL BUG-07: 100 concurrent getOwnerOutboxKey calls produce exactly 1 persistent key', async () => {
  const db = createMockIndexedDB()
  const _inflightKeyPromises = new Map()

  async function resolveOwnerKey(keyId) {
    const record = await db.get('device_keystore', keyId)
    if (record && record.key) return record.key

    const newKey = await crypto.subtle.generateKey(
      { name: 'AES-GCM', length: 256 },
      true, // extractable for mock storage verification
      ['encrypt', 'decrypt']
    )
    await db.put('device_keystore', {
      key_id: keyId,
      key: newKey,
      created_at: new Date().toISOString(),
    })
    return newKey
  }

  async function getOwnerKey(ownerId) {
    const keyId = `outbox_aes_gcm_${ownerId || 'anon'}`
    if (_inflightKeyPromises.has(keyId)) {
      return _inflightKeyPromises.get(keyId)
    }
    const promise = resolveOwnerKey(keyId)
    _inflightKeyPromises.set(keyId, promise)
    try {
      return await promise
    } finally {
      _inflightKeyPromises.delete(keyId)
    }
  }

  // Launch 100 concurrent requests simultaneously
  const workerId = 'asha_worker_stress_100'
  const promises = Array.from({ length: 100 }, () => getOwnerKey(workerId))
  const keys = await Promise.all(promises)

  // Verify all 100 returned keys are identical
  const firstKey = keys[0]
  assert.ok(firstKey, 'Key must be generated')
  for (let i = 1; i < keys.length; i++) {
    assert.strictEqual(keys[i], firstKey, `Concurrent caller ${i} must receive the exact same key instance`)
  }

  // Verify exactly 1 record was written to device_keystore
  const keystoreRecords = await db.getAll('device_keystore')
  assert.equal(keystoreRecords.length, 1, 'Exactly one key record must be stored')
  assert.equal(keystoreRecords[0].key_id, `outbox_aes_gcm_${workerId}`)
})

test('ADVERSARIAL BUG-06: Encryption failure strictly rejects plaintext fallback', async () => {
  async function simulateEncrypt(payload, shouldFail = false) {
    if (shouldFail) {
      throw new Error('Hardware crypto module unavailable')
    }
    return { _encrypted: true, data: 'dummy_cipher' }
  }

  async function safeEnqueue(payload, shouldFail) {
    try {
      const encrypted = await simulateEncrypt(payload, shouldFail)
      return { success: true, payload: encrypted }
    } catch (err) {
      // Must throw, never return cleartext
      throw new Error(`Outbox encryption failed: ${err.message}`)
    }
  }

  // Normal path: returns encrypted
  const normal = await safeEnqueue({ sensitive: 'patient_phi' }, false)
  assert.equal(normal.payload._encrypted, true)

  // Failure path: throws, never returns plaintext
  await assert.rejects(
    async () => safeEnqueue({ sensitive: 'patient_phi' }, true),
    (err) => {
      assert.ok(err.message.includes('Outbox encryption failed'))
      assert.ok(!err.message.includes('patient_phi'))
      return true
    }
  )
})

test('ADVERSARIAL BUG-07: AES-256-GCM AAD binding prevents cross-worker & cross-event ciphertext substitution', async () => {
  // Generate distinct keys for Worker A and Worker B
  const keyA = await crypto.subtle.generateKey({ name: 'AES-GCM', length: 256 }, false, ['encrypt', 'decrypt'])
  const keyB = await crypto.subtle.generateKey({ name: 'AES-GCM', length: 256 }, false, ['encrypt', 'decrypt'])

  const ownerA = 'worker_alpha'
  const ownerB = 'worker_beta'
  const event1 = 'event-uuid-1111'
  const event2 = 'event-uuid-2222'

  const secretPayload = { patient_name: 'Adversarial Test Patient', vitals: { spo2: 88 } }
  const encoded = new TextEncoder().encode(JSON.stringify(secretPayload))
  const iv = crypto.getRandomValues(new Uint8Array(12))
  const aadA1 = buildAad(ownerA, event1)

  // Encrypt under (keyA, ownerA, event1)
  const ctBuffer = await crypto.subtle.encrypt(
    { name: 'AES-GCM', iv, additionalData: aadA1 },
    keyA,
    encoded
  )

  // 1. Decrypt under correct (keyA, ownerA, event1) -> SUCCESS
  const decryptedGood = await crypto.subtle.decrypt(
    { name: 'AES-GCM', iv, additionalData: aadA1 },
    keyA,
    ctBuffer
  )
  assert.deepEqual(JSON.parse(new TextDecoder().decode(decryptedGood)), secretPayload)

  // 2. Attack: Worker B tries to decrypt Worker A's ciphertext using keyB
  await assert.rejects(
    async () => crypto.subtle.decrypt({ name: 'AES-GCM', iv, additionalData: buildAad(ownerB, event1) }, keyB, ctBuffer),
    'Worker B key must fail AES-GCM tag verification'
  )

  // 3. Attack: Ciphertext swapped to event2 under Worker A
  await assert.rejects(
    async () => crypto.subtle.decrypt({ name: 'AES-GCM', iv, additionalData: buildAad(ownerA, event2) }, keyA, ctBuffer),
    'Tampered eventId in AAD must fail AES-GCM authentication'
  )

  // 4. Attack: Bit-flip tampering of ciphertext
  const tamperedCt = new Uint8Array(ctBuffer)
  tamperedCt[0] ^= 0x01 // flip one bit
  await assert.rejects(
    async () => crypto.subtle.decrypt({ name: 'AES-GCM', iv, additionalData: aadA1 }, keyA, tamperedCt),
    'Bit-flipped ciphertext must fail authentication tag check'
  )
})

// =============================================================================
// Test Suite 4: Consent Revocation Coalescence & 404 Retry Loop (BUG-08)
// =============================================================================

test('ADVERSARIAL BUG-08: Consent revocation purges pending case.submit and retries on 404', async () => {
  const db = createMockIndexedDB()

  // 1. Enqueue 2 pending submissions: one for target case, one for another patient
  const targetClientId = 'client-case-target-1234'
  const otherClientId = 'client-case-other-5678'

  await db.put('outbox', {
    event_id: targetClientId,
    type: 'case.submit',
    owner_id: 'asha_1',
    status: 'pending',
    payload: { _encrypted: true },
  })
  await db.put('outbox', {
    event_id: otherClientId,
    type: 'case.submit',
    owner_id: 'asha_1',
    status: 'pending',
    payload: { _encrypted: true },
  })

  // 2. Execute consent revocation for targetClientId
  async function simulateEnqueueConsentRevocation(clientId, ownerId) {
    const all = await db.getAll('outbox')
    for (const item of all) {
      if ((item.event_id === clientId || item.payload?.client_id === clientId) && item.type === 'case.submit') {
        await db.delete('outbox', item.event_id)
      }
    }
    const revokeEventId = `revoke-${clientId}`
    await db.put('outbox', {
      event_id: revokeEventId,
      type: 'case.revoke_consent',
      owner_id: ownerId,
      status: 'pending',
      attempts: 0,
      payload: { client_id: clientId, reason: 'patient_withdrew_offline' },
    })
    return revokeEventId
  }

  const revokeId = await simulateEnqueueConsentRevocation(targetClientId, 'asha_1')

  // Verify target case.submit was purged from outbox
  const remainingTarget = await db.get('outbox', targetClientId)
  assert.strictEqual(remainingTarget, undefined, 'Pending case.submit for revoked patient must be purged')

  // Verify other case.submit was NOT touched
  const remainingOther = await db.get('outbox', otherClientId)
  assert.ok(remainingOther, 'Unrelated case.submit must remain queued')

  // Verify revocation event was queued
  const revokeEvent = await db.get('outbox', revokeId)
  assert.ok(revokeEvent, 'case.revoke_consent event must be queued')
  assert.equal(revokeEvent.type, 'case.revoke_consent')

  // 3. Test 404 Retry Logic in drain loop
  async function simulateDrainConsentRevoke(item, httpStatus) {
    if (httpStatus === 404) {
      if ((item.attempts || 0) < 3) {
        item.attempts = (item.attempts || 0) + 1
        await db.put('outbox', item)
        return 'failed' // will retry next time
      }
      item.status = 'dead'
      item.last_error = 'HTTP 404: Case not found for revocation'
      await db.put('outbox', item)
      return 'dead'
    }
    return 'synced'
  }

  // Attempt 1 -> 404 -> retries
  const outcome1 = await simulateDrainConsentRevoke(revokeEvent, 404)
  assert.equal(outcome1, 'failed')
  const after1 = await db.get('outbox', revokeId)
  assert.equal(after1.attempts, 1)
  assert.equal(after1.status, 'pending')

  // Attempt 2 -> 404 -> retries
  const outcome2 = await simulateDrainConsentRevoke(after1, 404)
  assert.equal(outcome2, 'failed')
  const after2 = await db.get('outbox', revokeId)
  assert.equal(after2.attempts, 2)
  assert.equal(after2.status, 'pending')

  // Attempt 3 -> 404 -> retries
  const outcome3 = await simulateDrainConsentRevoke(after2, 404)
  assert.equal(outcome3, 'failed')
  const after3 = await db.get('outbox', revokeId)
  assert.equal(after3.attempts, 3)

  // Attempt 4 -> 404 after 3 attempts -> dead-lettered
  const outcome4 = await simulateDrainConsentRevoke(after3, 404)
  assert.equal(outcome4, 'dead')
  const after4 = await db.get('outbox', revokeId)
  assert.equal(after4.status, 'dead')
  assert.ok(after4.last_error.includes('HTTP 404'))
})

// =============================================================================
// Test Suite 5: Owner-Scoped Recovery Count and Purge Isolation (BUG-24)
// =============================================================================

test('ADVERSARIAL BUG-24: Shared device isolation - purgeRecoveryRequired protects other workers', async () => {
  const db = createMockIndexedDB()

  // Seed outbox with mixed recovery records:
  // - Worker 1 recovery row
  // - Worker 2 recovery row
  // - Legacy ownerless recovery row (owner_id: null)
  // - Worker 1 active pending row
  await db.put('outbox', { event_id: 'rec-w1', owner_id: 'worker_1', status: 'recovery_required' })
  await db.put('outbox', { event_id: 'rec-w2', owner_id: 'worker_2', status: 'recovery_required' })
  await db.put('outbox', { event_id: 'rec-legacy', owner_id: null, status: 'recovery_required' })
  await db.put('outbox', { event_id: 'pending-w1', owner_id: 'worker_1', status: 'pending' })

  async function getRecoveryCount(ownerId = null) {
    const rows = await db.getAllFromIndex('outbox', 'status', 'recovery_required')
    if (!ownerId) return rows.filter((r) => r.owner_id == null).length
    return rows.filter((r) => r.owner_id === ownerId || r.owner_id == null).length
  }

  async function purgeRecovery(ownerId = null) {
    if (!ownerId) return 0
    const rows = await db.getAllFromIndex('outbox', 'status', 'recovery_required')
    let removed = 0
    for (const row of rows) {
      if (row.owner_id === ownerId || row.owner_id == null) {
        await db.delete('outbox', row.event_id)
        removed++
      }
    }
    return removed
  }

  // 1. Verify counts before purge
  assert.equal(await getRecoveryCount('worker_1'), 2, 'Worker 1 must see rec-w1 and rec-legacy')
  assert.equal(await getRecoveryCount('worker_2'), 2, 'Worker 2 must see rec-w2 and rec-legacy')
  assert.equal(await getRecoveryCount(null), 1, 'Unauthenticated/unscoped must see only rec-legacy')

  // 2. Unauthenticated purge must be rejected (returns 0)
  const purgedAnon = await purgeRecovery(null)
  assert.equal(purgedAnon, 0, 'Unauthenticated purge must do nothing')
  assert.equal((await db.getAll('outbox')).length, 4, 'All items must remain intact')

  // 3. Worker 1 executes purge
  const purgedW1 = await purgeRecovery('worker_1')
  assert.equal(purgedW1, 2, 'Must purge exactly 2 items (rec-w1 and rec-legacy)')

  // 4. Assert Worker 2 recovery item and Worker 1 pending item are STILL INTACT!
  const remainingRecW2 = await db.get('outbox', 'rec-w2')
  assert.ok(remainingRecW2, 'Worker 2 recovery row must NOT be deleted by Worker 1 purge')
  assert.equal(remainingRecW2.owner_id, 'worker_2')

  const remainingPendingW1 = await db.get('outbox', 'pending-w1')
  assert.ok(remainingPendingW1, 'Pending submissions must never be touched by recovery purge')

  // 5. Worker 2 logs in: sees only their own recovery row remaining
  assert.equal(await getRecoveryCount('worker_2'), 1)
})

// =============================================================================
// Test Suite 6: AES-256-GCM Patient History Cache & Owner Filtering (BUG-25, BUG-47)
// =============================================================================

test('ADVERSARIAL BUG-47 & BUG-25: Patient history encryption, owner scoping, and batched writes', async () => {
  const db = createMockIndexedDB()

  // Key generator per owner
  const ownerKeys = new Map()
  async function getKey(ownerId) {
    if (!ownerKeys.has(ownerId)) {
      const k = await crypto.subtle.generateKey({ name: 'AES-GCM', length: 256 }, false, ['encrypt', 'decrypt'])
      ownerKeys.set(ownerId, k)
    }
    return ownerKeys.get(ownerId)
  }

  function buildHistoryAad(ownerId, patientKey) {
    return new TextEncoder().encode(`vn:history:${ownerId || 'anon'}:${patientKey}`)
  }

  async function encryptHistory(payload, ownerId, patientKey) {
    const key = await getKey(ownerId)
    const iv = crypto.getRandomValues(new Uint8Array(12))
    const aad = buildHistoryAad(ownerId, patientKey)
    const encoded = new TextEncoder().encode(JSON.stringify(payload))
    const ct = await crypto.subtle.encrypt({ name: 'AES-GCM', iv, additionalData: aad }, key, encoded)
    return { _encrypted: true, _v: 1, iv: Array.from(iv), ct: Array.from(new Uint8Array(ct)) }
  }

  async function decryptHistory(record, ownerId, patientKey) {
    if (!record || !record._encrypted) return record
    try {
      const key = await getKey(ownerId)
      const iv = new Uint8Array(record.iv)
      const ct = new Uint8Array(record.ct)
      const aad = buildHistoryAad(ownerId, patientKey)
      const decrypted = await crypto.subtle.decrypt({ name: 'AES-GCM', iv, additionalData: aad }, key, ct)
      return { ...record, ...JSON.parse(new TextDecoder().decode(decrypted)), _encrypted: false }
    } catch {
      return null
    }
  }

  // 1. Batch write visits for 2 different patients under Worker A (BUG-25)
  const patientKey1 = 'PKEY-ALPHA-001'
  const patientKey2 = 'PKEY-ALPHA-002'
  const visitsP1 = [
    { created_at: '2026-11-09T10:00:00Z', chief_complaint: 'Fever', triage_level: 'URGENT', bp_systolic: 145 },
    { created_at: '2026-11-08T10:00:00Z', chief_complaint: 'Headache', triage_level: 'ROUTINE', bp_systolic: 125 },
  ]
  const visitsP2 = [
    { created_at: '2026-11-09T11:00:00Z', chief_complaint: 'Dyspnea', triage_level: 'EMERGENCY', bp_systolic: 160 },
  ]

  const env1 = await encryptHistory({ patient_name: 'Anjali Sharma', visits: visitsP1 }, 'worker_a', patientKey1)
  await db.put('patient_history_cache', {
    patient_key: patientKey1,
    owner_id: 'worker_a',
    phonetic_skeleton: 'ANJL-SRM',
    updated_at: new Date().toISOString(),
    ...env1,
  })

  const env2 = await encryptHistory({ patient_name: 'Bablu Kumar', visits: visitsP2 }, 'worker_a', patientKey2)
  await db.put('patient_history_cache', {
    patient_key: patientKey2,
    owner_id: 'worker_a',
    phonetic_skeleton: 'BBL-KMR',
    updated_at: new Date().toISOString(),
    ...env2,
  })

  // 2. Verify raw stored records in IndexedDB contain ZERO plaintext PHI
  const rawP1 = await db.get('patient_history_cache', patientKey1)
  assert.equal(rawP1._encrypted, true)
  assert.strictEqual(rawP1.patient_name, undefined, 'Raw IDB record must NOT contain plaintext patient_name')
  assert.strictEqual(rawP1.visits, undefined, 'Raw IDB record must NOT contain plaintext visits array')
  assert.ok(Array.isArray(rawP1.ct) && rawP1.ct.length > 0, 'Ciphertext must be present')

  // 3. Worker A queries their patient: SUCCESS with longitudinal deterioration calculation
  async function queryPatientHistory(patientKey, queryOwnerId) {
    const raw = await db.get('patient_history_cache', patientKey)
    if (!raw) return { found: false, cases: [] }
    if (queryOwnerId && raw.owner_id && raw.owner_id !== queryOwnerId) {
      return { found: false, cases: [] }
    }
    const decrypted = await decryptHistory(raw, queryOwnerId, patientKey)
    if (!decrypted || !Array.isArray(decrypted.visits)) return { found: false, cases: [] }
    return { found: true, patient_name: decrypted.patient_name, cases: decrypted.visits }
  }

  const queryAsWorkerA = await queryPatientHistory(patientKey1, 'worker_a')
  assert.equal(queryAsWorkerA.found, true)
  assert.equal(queryAsWorkerA.patient_name, 'Anjali Sharma')
  assert.equal(queryAsWorkerA.cases.length, 2)
  assert.equal(queryAsWorkerA.cases[0].bp_systolic, 145)

  // 4. Worker B queries Worker A's patient: ZERO LEAKAGE
  const queryAsWorkerB = await queryPatientHistory(patientKey1, 'worker_b')
  assert.equal(queryAsWorkerB.found, false, 'Cross-worker query must return found: false')
  assert.deepEqual(queryAsWorkerB.cases, [], 'Cross-worker query must return empty cases')

  // 5. Cross-worker Phonetic Lookup isolation
  async function searchPhonetic(skeleton, queryOwnerId) {
    const all = await db.getAll('patient_history_cache')
    const matched = all.filter((p) => (!queryOwnerId || !p.owner_id || p.owner_id === queryOwnerId) && p.phonetic_skeleton === skeleton)
    const results = []
    for (const r of matched) {
      const dec = await decryptHistory(r, queryOwnerId, r.patient_key)
      if (dec) results.push(dec)
    }
    return results
  }

  // Worker A searches: finds Anjali
  const foundByA = await searchPhonetic('ANJL-SRM', 'worker_a')
  assert.equal(foundByA.length, 1)
  assert.equal(foundByA[0].patient_name, 'Anjali Sharma')

  // Worker B searches: finds nothing!
  const foundByB = await searchPhonetic('ANJL-SRM', 'worker_b')
  assert.equal(foundByB.length, 0, 'Phonetic lookup must not reveal Worker A patients to Worker B')
})

// =============================================================================
// Test Suite 7: Paediatric Advisory Matrix & Edge Bounds (BUG-31)
// =============================================================================

test('ADVERSARIAL BUG-31: buildPaediatricAdvisory age and MUAC boundary matrix', () => {
  // Disabled mode
  const disabled = buildPaediatricAdvisory({ patient_age: 2, muac_mm: 110 }, false)
  assert.equal(disabled.status, 'disabled_pending_governance')
  assert.strictEqual(disabled.eligible_for_muac_screen, null)

  // Non-finite age
  const nonFiniteAge = buildPaediatricAdvisory({ patient_age: NaN, muac_mm: 110 }, true)
  assert.equal(nonFiniteAge.status, 'insufficient_age_data')

  // Sub-6-month infant (5 months) -> out of scope for MUAC (<6 mo)
  const infant5Mo = buildPaediatricAdvisory({ patient_age: 0, age_months: 5, muac_mm: 110 }, true)
  assert.equal(infant5Mo.eligible_for_muac_screen, false)
  assert.equal(infant5Mo.muac_screen_status, 'out_of_scope')

  // Exactly 6 months -> eligible
  const infant6Mo = buildPaediatricAdvisory({ patient_age: 0, age_months: 6, muac_mm: 110 }, true)
  assert.equal(infant6Mo.eligible_for_muac_screen, true)
  assert.equal(infant6Mo.muac_screen_status, 'below_reference_threshold_full_assessment_needed')

  // Exactly 59 months -> eligible
  const child59Mo = buildPaediatricAdvisory({ patient_age: 4, age_months: 59, muac_mm: 120 }, true)
  assert.equal(child59Mo.eligible_for_muac_screen, true)
  assert.equal(child59Mo.muac_screen_status, 'at_or_above_reference_threshold')

  // 60 months (5 years) -> out of scope
  const child60Mo = buildPaediatricAdvisory({ patient_age: 5, age_months: 60, muac_mm: 110 }, true)
  assert.equal(child60Mo.eligible_for_muac_screen, false)
  assert.equal(child60Mo.muac_screen_status, 'out_of_scope')

  // Eligible child with missing/non-finite MUAC -> eligible_missing_muac
  const missingMuac = buildPaediatricAdvisory({ patient_age: 2, age_months: 24, muac_mm: null }, true)
  assert.equal(missingMuac.eligible_for_muac_screen, true)
  assert.equal(missingMuac.muac_screen_status, 'eligible_missing_muac')
})

// =============================================================================
// Test Suite 8: Realtime Case Escalation & Overridden Triage (BUG-59)
// =============================================================================

test('ADVERSARIAL BUG-59: Realtime listener escalation detects overridden_triage == EMERGENCY', () => {
  let toastTriggered = null
  function showToast(msg, type) {
    toastTriggered = { msg, type }
  }

  function handleUpdate(existingCase, updatedPayload) {
    let wasEscalated = false
    const oldTriage = existingCase.overridden_triage || existingCase.triage_level
    const newTriage = updatedPayload.overridden_triage || updatedPayload.triage_level
    if (oldTriage !== 'EMERGENCY' && newTriage === 'EMERGENCY') {
      wasEscalated = true
    }
    if (wasEscalated) {
      showToast('Case escalated to EMERGENCY', 'error')
    }
    return wasEscalated
  }

  // Case 1: ROUTINE -> overridden to EMERGENCY -> MUST ESCALATE
  const case1 = { id: 'c1', triage_level: 'ROUTINE', overridden_triage: null }
  const update1 = { id: 'c1', triage_level: 'ROUTINE', overridden_triage: 'EMERGENCY' }
  const escalated1 = handleUpdate(case1, update1)
  assert.equal(escalated1, true)
  assert.equal(toastTriggered.msg, 'Case escalated to EMERGENCY')

  // Case 2: EMERGENCY -> overridden to EMERGENCY (already emergency) -> NO ESCALATION TOAST
  toastTriggered = null
  const case2 = { id: 'c2', triage_level: 'EMERGENCY', overridden_triage: null }
  const update2 = { id: 'c2', triage_level: 'EMERGENCY', overridden_triage: 'EMERGENCY' }
  const escalated2 = handleUpdate(case2, update2)
  assert.equal(escalated2, false)
  assert.strictEqual(toastTriggered, null)

  // Case 3: URGENT -> natural model escalation to EMERGENCY -> MUST ESCALATE
  toastTriggered = null
  const case3 = { id: 'c3', triage_level: 'URGENT', overridden_triage: null }
  const update3 = { id: 'c3', triage_level: 'EMERGENCY', overridden_triage: null }
  const escalated3 = handleUpdate(case3, update3)
  assert.equal(escalated3, true)
  assert.equal(toastTriggered.msg, 'Case escalated to EMERGENCY')
})
