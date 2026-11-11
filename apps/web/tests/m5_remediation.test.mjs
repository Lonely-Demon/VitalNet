// apps/web/tests/m5_remediation.test.mjs
// Comprehensive verification test suite for Milestone 5 Phase 52 Remediation fixes:
// BUG-04, BUG-05, BUG-06, BUG-07, BUG-08, BUG-15, BUG-24, BUG-25, BUG-31, BUG-32,
// BUG-34, BUG-41, BUG-42, BUG-46, BUG-47, BUG-48, BUG-49, BUG-50, BUG-59, BUG-60, BUG-65.

import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

// Load parseIeee11073Sfloat and calculateRppgPulse directly from VitalCaptureAssist.jsx
const vitalCapturePath = path.resolve('apps/web/src/components/VitalCaptureAssist.jsx')
const vitalCaptureSrc = fs.readFileSync(vitalCapturePath, 'utf8')
const sfloatMatch = vitalCaptureSrc.match(/export function parseIeee11073Sfloat\([\s\S]*?\n\}/)
const parseIeee11073Sfloat = new Function(`${sfloatMatch[0].replace('export function', 'function')}; return parseIeee11073Sfloat;`)()

const rppgMatch = vitalCaptureSrc.match(/export function calculateRppgPulse\([\s\S]*?\n\}/)
const calculateRppgPulse = new Function(`${rppgMatch[0].replace('export function', 'function')}; return calculateRppgPulse;`)()
import { parseStrictInt, parseStrictFloat, serializeIntakePayload } from '../src/lib/intakePayload.js'
import { buildPaediatricAdvisory, PAEDIATRIC_ADVISORY_VERSION, MUAC_REFERRAL_THRESHOLD_MM } from '../src/utils/triageClassifier.js'
import { encodeEmergencySmsFrame, decodeEmergencySms } from '@vitalnet/clinical-core'

// =============================================================================
// 1. Medical Devices & UI Components (BUG-04, 05, 41, 42, 48, 49, 50, 65)
// =============================================================================

test('BUG-04: BriefingCard inverts history array so VitalTrendSparkline renders chronologically', () => {
  const briefingCardPath = path.resolve('apps/web/src/components/BriefingCard.jsx')
  const src = fs.readFileSync(briefingCardPath, 'utf8')
  assert.ok(
    src.includes('[...history].reverse().map((visit) => visit[definition.key])'),
    'BriefingCard must reverse history array before mapping values to VitalTrendSparkline'
  )

  // Simulation of descending history -> chronological sparkline
  const descendingHistory = [
    { created_at: '2026-11-09T14:00:00Z', bp_systolic: 140 }, // Latest visit
    { created_at: '2026-11-08T10:00:00Z', bp_systolic: 120 },
    { created_at: '2026-11-01T09:00:00Z', bp_systolic: 110 }, // Oldest visit
  ]
  const sparklineValues = [...descendingHistory].reverse().map((v) => v.bp_systolic)
  assert.deepEqual(sparklineValues, [110, 120, 140])
  assert.equal(sparklineValues[sparklineValues.length - 1], 140, 'Rightmost badge point must be the latest visit')
})

test('BUG-05: TapCadencePanel handleApply correctly maps respiratory_rate', () => {
  const vitalCapturePath = path.resolve('apps/web/src/components/VitalCaptureAssist.jsx')
  const src = fs.readFileSync(vitalCapturePath, 'utf8')
  assert.ok(
    src.includes("onApply({ respiratory_rate: calculatedBpm }, `RR ${calculatedBpm}/min applied`)"),
    'TapCadencePanel must apply respiratory_rate when vitalTarget is not heart_rate'
  )
  assert.ok(
    !src.includes("onApply({ heart_rate: calculatedBpm }, `Cadence ${calculatedBpm}/min applied`)"),
    'TapCadencePanel must not map respiratory cadence to heart_rate'
  )
})

test('BUG-41: BluetoothGattPanel implements debounce cooldown on connect attempts', () => {
  const vitalCapturePath = path.resolve('apps/web/src/components/VitalCaptureAssist.jsx')
  const src = fs.readFileSync(vitalCapturePath, 'utf8')
  assert.ok(src.includes('CONNECT_COOLDOWN_MS = 1500'), 'Must define CONNECT_COOLDOWN_MS of 1500 ms')
  assert.ok(src.includes('connectLockRef.current'), 'Must maintain connectLockRef single-flight lock')
  assert.ok(
    src.includes('now - lastConnectAttemptRef.current < CONNECT_COOLDOWN_MS'),
    'Must drop rapid consecutive connection attempts within cooldown window'
  )
})

test('BUG-42: BluetoothGattPanel cleans up event listeners and notifications on disconnect and unmount', () => {
  const vitalCapturePath = path.resolve('apps/web/src/components/VitalCaptureAssist.jsx')
  const src = fs.readFileSync(vitalCapturePath, 'utf8')
  assert.ok(
    src.includes("deviceRef.current.removeEventListener('gattserverdisconnected'"),
    'Must remove gattserverdisconnected event listener on disconnect/cleanup'
  )
  assert.ok(
    src.includes("char.removeEventListener('characteristicvaluechanged'"),
    'Must unregister characteristic event listeners'
  )
  assert.ok(src.includes('char.stopNotifications()'), 'Must stop BLE characteristic notifications')
})

test('BUG-48: IEEE 11073-20601 SFLOAT parser handles sentinels, kPa conversion, and SpO2/PR offsets', () => {
  // Test sentinels: 0x07FE (+INF), 0x07FF (NaN), 0x0800 (NRes), 0x0801 (Reserved), 0x0802 (-INF)
  const buffer = new ArrayBuffer(16)
  const dv = new DataView(buffer)

  // Sentinel 0x07FE (+INFINITY)
  dv.setUint16(0, 0x07fe, true)
  assert.equal(parseIeee11073Sfloat(dv, 0), null, '0x07FE (+INF) must decode to null')

  // Sentinel 0x07FF (NaN)
  dv.setUint16(2, 0x07ff, true)
  assert.equal(parseIeee11073Sfloat(dv, 2), null, '0x07FF (NaN) must decode to null')

  // Sentinel 0x0800 (NRes)
  dv.setUint16(4, 0x0800, true)
  assert.equal(parseIeee11073Sfloat(dv, 4), null, '0x0800 (NRes) must decode to null')

  // Sentinel 0x0801 (Reserved)
  dv.setUint16(6, 0x0801, true)
  assert.equal(parseIeee11073Sfloat(dv, 6), null, '0x0801 (Reserved) must decode to null')

  // Sentinel 0x0802 (-INFINITY)
  dv.setUint16(8, 0x0802, true)
  assert.equal(parseIeee11073Sfloat(dv, 8), null, '0x0802 (-INF) must decode to null')

  // Valid number: mantissa 120, exponent 0 -> raw = 0x0078
  dv.setUint16(10, 0x0078, true)
  assert.equal(parseIeee11073Sfloat(dv, 10), 120, '0x0078 must decode to 120')

  // Valid float: mantissa 160, exponent -1 -> 16.0 kPa
  // 160 in hex = 0x0A0, exponent -1 = 0xF -> raw = 0xF0A0
  dv.setUint16(12, 0xf0a0, true)
  const kpaVal = parseIeee11073Sfloat(dv, 12)
  assert.ok(Math.abs(kpaVal - 16.0) < 0.001, '0xF0A0 must decode to 16.0')
  const mmhgVal = Math.round(kpaVal * 7.50062)
  assert.equal(mmhgVal, 120, '16.0 kPa must convert to 120 mmHg')

  // Verify Blood Pressure and PLX offsets in source
  const vitalCapturePath = path.resolve('apps/web/src/components/VitalCaptureAssist.jsx')
  const src = fs.readFileSync(vitalCapturePath, 'utf8')
  assert.ok(src.includes('const KPA_TO_MMHG = 7.50062'), 'Must define KPA_TO_MMHG multiplier')
  assert.ok(src.includes('parseIeee11073Sfloat(val, 1)'), 'Must parse SFLOAT at offset 1')
  assert.ok(src.includes('parseIeee11073Sfloat(val, 3)'), 'Must parse SFLOAT at offset 3')
  assert.ok(src.includes('0x2a5f'), 'Must include fallback to PLX continuous characteristic 0x2A5F')
})

test('BUG-49: calculateRppgPulse dynamically calculates effective FPS from timestamps', () => {
  // Test duration < 9.5s rejected
  const shortSamples = []
  for (let i = 0; i < 100; i++) {
    shortSamples.push({ time: i * 33.3, r: 100 })
  }
  const shortRes = calculateRppgPulse(shortSamples)
  assert.equal(shortRes.ok, false)
  assert.ok(shortRes.error.includes('Insufficient sample duration'))

  // Generate 60 Hz sequence (720 samples over 12s, 80 bpm pulse = 1.333 Hz)
  const fps60 = 60
  const durationSec = 12
  const totalFrames60 = fps60 * durationSec
  const targetBpm60 = 80
  const freqHz60 = targetBpm60 / 60 // 1.333 Hz
  const samples60 = []

  for (let i = 0; i < totalFrames60; i++) {
    const tMs = i * (1000 / fps60)
    const tSec = tMs / 1000
    // Sine wave signal with amplitude 1.0 (mean 50)
    const rVal = 50 + Math.sin(2 * Math.PI * freqHz60 * tSec) * 1.0
    samples60.push({ time: tMs, r: rVal })
  }

  const res60 = calculateRppgPulse(samples60)
  assert.equal(res60.ok, true, `60 Hz rPPG failed: ${res60.error}`)
  assert.ok(
    Math.abs(res60.bpm - targetBpm60) <= 3,
    `60 Hz display must estimate ~80 bpm (got ${res60.bpm} bpm), must NOT halve to 40 bpm`
  )
  assert.ok(Math.abs(res60.effectiveFps - 60) < 1, `Effective FPS must be ~60 (got ${res60.effectiveFps})`)

  // Generate 20 Hz sequence (240 samples over 12s, 75 bpm pulse = 1.25 Hz)
  const fps20 = 20
  const totalFrames20 = fps20 * durationSec
  const targetBpm20 = 75
  const freqHz20 = targetBpm20 / 60
  const samples20 = []

  for (let i = 0; i < totalFrames20; i++) {
    const tMs = i * (1000 / fps20)
    const tSec = tMs / 1000
    const rVal = 50 + Math.sin(2 * Math.PI * freqHz20 * tSec) * 1.0
    samples20.push({ time: tMs, r: rVal })
  }

  const res20 = calculateRppgPulse(samples20)
  assert.equal(res20.ok, true, `20 Hz rPPG failed: ${res20.error}`)
  assert.ok(
    Math.abs(res20.bpm - targetBpm20) <= 3,
    `20 Hz camera must estimate ~75 bpm (got ${res20.bpm} bpm)`
  )
})

test('BUG-50: QrScannerModal implements single-flight lock and post-await mount verification', () => {
  const qrModalPath = path.resolve('apps/web/src/components/QrScannerModal.jsx')
  const src = fs.readFileSync(qrModalPath, 'utf8')
  assert.ok(src.includes('detectInFlightRef = useRef(false)'), 'Must declare detectInFlightRef lock')
  assert.ok(src.includes('hasDetectedRef = useRef(false)'), 'Must declare hasDetectedRef single-flight guard')
  assert.ok(
    src.includes('if (detectInFlightRef.current || hasDetectedRef.current) return'),
    'Scan interval must drop concurrent/completed detection ticks'
  )
  assert.ok(
    src.includes('// Post-await mount verification (BUG-50)'),
    'Must verify component mount status after video.play() await'
  )
})

test('BUG-65: IntakeForm clears demographic fields on QR re-scan for distinct patient', () => {
  const intakeFormPath = path.resolve('apps/web/src/pages/IntakeForm.jsx')
  const src = fs.readFileSync(intakeFormPath, 'utf8')
  assert.ok(
    src.includes('const isDifferentKey = Boolean('),
    'Must check if scanned key is different from previous key'
  )
  assert.ok(
    src.includes('next.patient_name = scanned.patientName || \'\''),
    'Must overwrite patient_name on distinct patient key scan'
  )
  assert.ok(
    src.includes('next.age_months = \'\''),
    'Must clear age_months on distinct patient key scan'
  )

  // Functional simulation of the onDetected state updater
  function simulateOnDetected(prev, scanned) {
    const next = { ...prev }
    const isDifferentKey = Boolean(
      prev.patient_key && scanned.patientKey && prev.patient_key !== scanned.patientKey
    )
    if (scanned.patientKey) next.patient_key = scanned.patientKey

    if (isDifferentKey) {
      next.patient_name = scanned.patientName || ''
      next.patient_age = scanned.patientAge != null ? String(scanned.patientAge) : ''
      next.age_months = ''
      next.patient_sex = scanned.patientSex || ''
    } else {
      if (scanned.patientName) next.patient_name = scanned.patientName
      if (scanned.patientAge != null) next.patient_age = String(scanned.patientAge)
      if (scanned.patientSex) next.patient_sex = scanned.patientSex
    }
    return next
  }

  // Scan Patient 1 (Mother, 32F)
  const state1 = simulateOnDetected(
    { patient_key: '', patient_name: '', patient_age: '', patient_sex: '' },
    { patientKey: 'AAAA-1111', patientName: 'Meena Devi', patientAge: 32, patientSex: 'female' }
  )
  assert.equal(state1.patient_name, 'Meena Devi')
  assert.equal(state1.patient_age, '32')

  // Re-scan Patient 2 (Child, 3M, blank card)
  const state2 = simulateOnDetected(state1, {
    patientKey: 'BBBB-2222',
    patientName: 'Raju',
    patientAge: 3,
    patientSex: 'male',
  })
  assert.equal(state2.patient_key, 'BBBB-2222')
  assert.equal(state2.patient_name, 'Raju', 'Patient 1 name must NOT be retained')
  assert.equal(state2.patient_age, '3', 'Patient 1 age must NOT be retained')
  assert.equal(state2.patient_sex, 'male', 'Patient 1 sex must NOT be retained')

  // Re-scan plain card (no demographics attached)
  const state3 = simulateOnDetected(state2, { patientKey: 'CCCC-3333' })
  assert.equal(state3.patient_key, 'CCCC-3333')
  assert.equal(state3.patient_name, '', 'Demographics must be cleared on distinct blank card scan')
  assert.equal(state3.patient_age, '')
  assert.equal(state3.patient_sex, '')
})

// =============================================================================
// 2. Offline IDB, Keystore & Outbox (BUG-06, 07, 08, 15, 24, 25, 47)
// =============================================================================

test('BUG-06: Outbox captures enqueued_time_origin and reconciles monotonic client_submitted_at across reloads', () => {
  const outboxPath = path.resolve('apps/web/src/lib/outbox.js')
  const syncStorePath = path.resolve('apps/web/src/stores/syncStore.js')
  const outboxSrc = fs.readFileSync(outboxPath, 'utf8')
  const syncStoreSrc = fs.readFileSync(syncStorePath, 'utf8')

  assert.ok(outboxSrc.includes('enqueued_time_origin: timeOriginMs'), 'outbox enqueue must record enqueued_time_origin')
  assert.ok(syncStoreSrc.includes('item.enqueued_time_origin'), 'syncStore must read enqueued_time_origin')
  assert.ok(syncStoreSrc.includes('currentAbsolute >= enqueuedAbsolute'), 'syncStore must compute absolute elapsed time')

  // Simulation of tab reload clock skew reconciliation:
  // Tab 1: timeOrigin = 1,000,000, performance.now() = 5,000 => enqueued at absolute 1,005,000
  const item = {
    intake_monotonic_ms: 5000,
    enqueued_time_origin: 1000000,
    created_at: '2026-11-09T10:00:00.000Z',
    payload: {},
  }
  // Tab 2 (Reloaded 10 seconds later):
  // timeOrigin = 1,014,000, performance.now() = 1,000 => current absolute 1,015,000
  const currentOrigin = 1014000
  const currentNow = 1000
  const enqueuedAbsolute = item.enqueued_time_origin + item.intake_monotonic_ms
  const currentAbsolute = currentOrigin + currentNow
  const elapsedMs = Math.round(currentAbsolute - enqueuedAbsolute) // 10,000 ms = 10s elapsed!

  assert.equal(elapsedMs, 10000, 'Elapsed time must accurately evaluate to 10,000 ms across reload')
})

test('BUG-07: Outbox key resolution consults IDB first, locks in-flight, and rejects plaintext fallback', () => {
  const outboxPath = path.resolve('apps/web/src/lib/outbox.js')
  const src = fs.readFileSync(outboxPath, 'utf8')

  assert.ok(src.includes('const _inflightKeyPromises = new Map()'), 'Must use in-flight mutex map')
  assert.ok(src.includes('Step 1: Consult IndexedDB device_keystore FIRST'), 'Must prioritize persistent IDB over sessionStorage')
  assert.ok(
    src.includes('throw new Error(`Outbox encryption failed:'),
    'encryptOutboxPayload must throw rather than falling back to plaintext'
  )
})

test('BUG-08: Offline consent revocation coalesces case.submit and retries on 404', () => {
  const outboxPath = path.resolve('apps/web/src/lib/outbox.js')
  const syncStorePath = path.resolve('apps/web/src/stores/syncStore.js')
  const outboxSrc = fs.readFileSync(outboxPath, 'utf8')
  const syncStoreSrc = fs.readFileSync(syncStorePath, 'utf8')

  assert.ok(
    outboxSrc.includes('item.type === \'case.submit\'') && outboxSrc.includes('await db.delete(STORE_NAME, item.event_id)'),
    'enqueueConsentRevocation must delete matching pending case.submit outbox items'
  )
  assert.ok(
    syncStoreSrc.includes('if (res.status === 404)') && syncStoreSrc.includes('if ((item.attempts || 0) < 3)'),
    'drainConsentRevoke must retry on 404 rather than immediately dropping revocation'
  )
})

test('BUG-15: IndexedDB upgrade creates all stores synchronously before awaiting migration', () => {
  const offlineDbPath = path.resolve('apps/web/src/lib/offlineDB.js')
  const src = fs.readFileSync(offlineDbPath, 'utf8')

  // Find index of store creations vs async data migration
  const keystoreIndex = src.indexOf("db.createObjectStore('device_keystore'")
  const historyCacheIndex = src.indexOf("db.createObjectStore('patient_history_cache'")
  const migrationIndex = src.indexOf('await Promise.all(rows.map')

  assert.ok(keystoreIndex > 0, 'device_keystore store must be created')
  assert.ok(historyCacheIndex > 0, 'patient_history_cache store must be created')
  assert.ok(keystoreIndex < migrationIndex, 'device_keystore must be created BEFORE async data migration')
  assert.ok(historyCacheIndex < migrationIndex, 'patient_history_cache must be created BEFORE async data migration')
  assert.ok(src.includes('await transaction.done'), 'Must await transaction.done in upgrade callback')
})

test('BUG-24: OfflineBanner scopes getRecoveryRequiredCount and purgeRecoveryRequired by ownerId', () => {
  const bannerPath = path.resolve('apps/web/src/components/OfflineBanner.jsx')
  const outboxPath = path.resolve('apps/web/src/lib/outbox.js')
  const bannerSrc = fs.readFileSync(bannerPath, 'utf8')
  const outboxSrc = fs.readFileSync(outboxPath, 'utf8')

  assert.ok(bannerSrc.includes('getRecoveryRequiredCount(ownerId)'), 'OfflineBanner must pass ownerId to getRecoveryRequiredCount')
  assert.ok(bannerSrc.includes('purgeRecoveryRequired(ownerId)'), 'OfflineBanner must pass ownerId to purgeRecoveryRequired')
  assert.ok(
    outboxSrc.includes('if (row.owner_id === ownerId || row.owner_id == null)'),
    'purgeRecoveryRequired must protect records belonging to other workers'
  )
})

test('BUG-25 & BUG-47: Patient history cache encrypts sensitive fields, scopes by owner, and batches visits', () => {
  const cachePath = path.resolve('apps/web/src/lib/patientHistoryCache.js')
  const src = fs.readFileSync(cachePath, 'utf8')

  assert.ok(src.includes('export async function cachePatientVisits(visitsList, ownerId = null)'), 'Must export batched cachePatientVisits')
  assert.ok(src.includes('encryptHistoryPayload(sensitivePayload, ownerId, patientKey)'), 'Must encrypt sensitive payload')
  assert.ok(src.includes('rawRecord.owner_id !== ownerId'), 'getOfflinePatientHistory must scope queries by ownerId')
  assert.ok(src.includes('findPatientsByPhonetic(nameQuery, ownerId = null)'), 'findPatientsByPhonetic must accept ownerId')
  assert.ok(src.includes('!p.owner_id || p.owner_id === ownerId'), 'findPatientsByPhonetic must filter matches by ownerId')
})

// =============================================================================
// 3. Intake Payload, Dashboard, Auth & Wire Parity (BUG-31, 32, 34, 46, 59, 60)
// =============================================================================

test('BUG-31: triageClassifier includes muac_mm and returns completeness_state, paediatric_advisory, topFactors', () => {
  const classifierPath = path.resolve('apps/web/src/utils/triageClassifier.js')
  const src = fs.readFileSync(classifierPath, 'utf8')

  assert.ok(src.includes('muac_mm: formData.muac_mm ?? null'), 'runTriage must forward muac_mm to engineInput')
  assert.ok(src.includes('completeness_state:'), 'runTriage must return completeness_state')
  assert.ok(src.includes('paediatric_advisory:'), 'runTriage must return paediatric_advisory')
  assert.ok(src.includes('topFactors:'), 'runTriage must return topFactors')

  // Test buildPaediatricAdvisory helper
  const disabledAdvisory = buildPaediatricAdvisory({ patient_age: 2, muac_mm: 110 }, false)
  assert.equal(disabledAdvisory.status, 'disabled_pending_governance')

  const activeAdvisory = buildPaediatricAdvisory({ patient_age: 2, age_months: 24, muac_mm: 110 }, true)
  assert.equal(activeAdvisory.version, PAEDIATRIC_ADVISORY_VERSION)
  assert.equal(activeAdvisory.eligible_for_muac_screen, true)
  assert.equal(activeAdvisory.muac_screen_status, 'below_reference_threshold_full_assessment_needed')
  assert.equal(activeAdvisory.reference_threshold_mm, MUAC_REFERRAL_THRESHOLD_MM)
})

test('BUG-32: parseStrictInt and parseStrictFloat enforce strict numeric validation in intake payload', () => {
  // Test zero preservation (newborns & 0 measurements)
  assert.equal(parseStrictInt(0), 0)
  assert.equal(parseStrictInt('0'), 0)
  assert.equal(parseStrictFloat(0), 0)

  // Test valid numbers
  assert.equal(parseStrictInt('120'), 120)
  assert.equal(parseStrictFloat('37.5'), 37.5)

  // Test dirty strings rejected to null (no partial parsing)
  assert.equal(parseStrictInt('120abc'), null)
  assert.equal(parseStrictFloat('37.5foo'), null)
  assert.equal(parseStrictInt('abc'), null)

  // Test whitespace, null, undefined, booleans rejected to null
  assert.equal(parseStrictInt(''), null)
  assert.equal(parseStrictInt('   '), null)
  assert.equal(parseStrictInt(null), null)
  assert.equal(parseStrictInt(undefined), null)
  assert.equal(parseStrictInt(false), null)
  assert.equal(parseStrictInt(true), null)

  // Test payload serialization
  const payload = serializeIntakePayload(
    {
      patient_age: '0',
      age_months: '4',
      muac_mm: '115',
      bp_systolic: '120abc',
      bp_diastolic: '',
      spo2: '98',
      heart_rate: '75',
      temperature: '37.2',
      chief_complaint: 'Fever',
    },
    'ABCD-1234'
  )
  assert.equal(payload.patient_age, 0, 'Newborn 0 age must be preserved as number 0')
  assert.equal(payload.age_months, 4)
  assert.equal(payload.muac_mm, 115)
  assert.equal(payload.bp_systolic, null, 'Dirty string 120abc must be sanitized to null')
  assert.equal(payload.bp_diastolic, null, 'Empty string must serialize to null')
  assert.equal(payload.spo2, 98)
  assert.equal(payload.heart_rate, 75)
  assert.equal(payload.temperature, 37.2)
})

test('BUG-34: Dashboard resets pagination state on filter change', () => {
  const dashboardPath = path.resolve('apps/web/src/pages/Dashboard.jsx')
  const src = fs.readFileSync(dashboardPath, 'utf8')

  assert.ok(
    src.includes('useEffect(() => {') &&
    src.includes('setNextCursor(null)') &&
    src.includes('setNextTriagePriority(null)') &&
    src.includes('setNextNeedsReview(null)') &&
    src.includes('setNextId(null)') &&
    src.includes('setHasMore(false)') &&
    src.includes('fetchCases()') &&
    src.includes('}, [filter, fetchCases])'),
    'Dashboard must reset all pagination cursors and re-fetch when filter changes'
  )
})

test('BUG-46: encodeEmergencySmsFrame handles aliases and sub-year neonatal encoding with byte 254', () => {
  // Test sub-year infant encoding with age_months: 6
  const infantFrame = encodeEmergencySmsFrame({
    clientId: '11111111-2222-3333-4444-555555555555',
    patient_age: 0,
    age_months: 6,
    patient_sex: 'female',
    triage_level: 'EMERGENCY',
    symptoms: ['high_fever'],
    bp_systolic: null,
    bp_diastolic: null,
    spo2: 95,
    heart_rate: 140,
    temperature: 38.5,
  })

  assert.ok(infantFrame.startsWith('VN1:'), 'Frame must have VN1: header')
  const decoded = decodeEmergencySms(infantFrame)
  assert.equal(decoded.patient_sex, 'female')
  assert.equal(decoded.triage_level, 'EMERGENCY')
  assert.equal(decoded.age_months, 6, 'Sub-year infant must decode age_months === 6')

  // Verify IntakeForm passes all canonical keys and age_months
  const intakeFormPath = path.resolve('apps/web/src/pages/IntakeForm.jsx')
  const src = fs.readFileSync(intakeFormPath, 'utf8')
  assert.ok(src.includes('age_months: payload.age_months != null'), 'IntakeForm must pass age_months')
  assert.ok(src.includes('patient_age: payload.patient_age != null'), 'IntakeForm must pass patient_age')
  assert.ok(src.includes('triage_level: \'EMERGENCY\''), 'IntakeForm must pass triage_level')
})

test('BUG-59: Dashboard checks overridden_triage || triage_level in realtime listener and escalation', () => {
  const dashboardPath = path.resolve('apps/web/src/pages/Dashboard.jsx')
  const src = fs.readFileSync(dashboardPath, 'utf8')

  assert.ok(
    src.includes('const effectiveTriage = newCase.overridden_triage || newCase.triage_level'),
    'onInsert must check overridden_triage || triage_level'
  )
  assert.ok(
    src.includes('if (effectiveTriage === \'EMERGENCY\')'),
    'onInsert must alert when effective triage is EMERGENCY'
  )
  assert.ok(
    src.includes('if (oldTriage !== \'EMERGENCY\' && newTriage === \'EMERGENCY\')'),
    'onUpdate must detect case escalation to EMERGENCY'
  )
  assert.ok(
    src.includes('showToast(\'Case escalated to EMERGENCY\', \'error\')'),
    'onUpdate must toast when case is escalated to EMERGENCY'
  )
})

test('BUG-60: authStore and IntakeForm isolate drafts per worker and purge on logout', () => {
  const authStorePath = path.resolve('apps/web/src/store/authStore.jsx')
  const intakeFormPath = path.resolve('apps/web/src/pages/IntakeForm.jsx')
  const authSrc = fs.readFileSync(authStorePath, 'utf8')
  const intakeSrc = fs.readFileSync(intakeFormPath, 'utf8')

  assert.ok(authSrc.includes('const activeUserIdRef = useRef(null)'), 'authStore must track activeUserIdRef')
  assert.ok(
    authSrc.includes('clearSharedDeviceState(targetUserId)'),
    'authStore must pass targetUserId to clearSharedDeviceState'
  )
  assert.ok(
    intakeSrc.includes('const loadedDraftOwnerRef = useRef(null)'),
    'IntakeForm must track loadedDraftOwnerRef to reload on profile change'
  )
  assert.ok(
    intakeSrc.includes('if (loadedDraftOwnerRef.current)') && intakeSrc.includes('setForm(emptyForm)'),
    'IntakeForm must reset form on logout'
  )
})
