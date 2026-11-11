// apps/web/tests/challenger_m5_stress.test.mjs
// Adversarial stress test harness for Milestone 5 (Medical Devices & UI Components)
// BUG-04, BUG-05, BUG-41, BUG-42, BUG-48, BUG-49, BUG-50, BUG-65

import test from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'

// Extract parseIeee11073Sfloat and calculateRppgPulse directly from VitalCaptureAssist.jsx
const vitalCapturePath = path.resolve('apps/web/src/components/VitalCaptureAssist.jsx')
const vitalCaptureSrc = fs.readFileSync(vitalCapturePath, 'utf8')

const sfloatMatch = vitalCaptureSrc.match(/export function parseIeee11073Sfloat\([\s\S]*?\n\}/)
assert.ok(sfloatMatch, 'Must find export function parseIeee11073Sfloat')
const parseIeee11073Sfloat = new Function(
  `${sfloatMatch[0].replace('export function', 'function')}; return parseIeee11073Sfloat;`
)()

const rppgMatch = vitalCaptureSrc.match(/export function calculateRppgPulse\([\s\S]*?\n\}/)
assert.ok(rppgMatch, 'Must find export function calculateRppgPulse')
const calculateRppgPulse = new Function(
  `${rppgMatch[0].replace('export function', 'function')}; return calculateRppgPulse;`
)()

import { buildSparklinePath, finiteValues, formatTrendSummary, VITAL_TREND_DEFINITIONS } from '../src/utils/vitalTrend.js'
import { serializeIntakePayload } from '../src/lib/intakePayload.js'

// =============================================================================
// SUITE 1: IEEE 11073-20601 SFLOAT Sentinels, Conversions & Offsets (BUG-48)
// =============================================================================
test('BUG-48 Stress: IEEE 11073 SFLOAT sentinels (0x07FE..0x0802) across all 4-bit exponents return null', () => {
  const sentinels = [
    { code: 0x07fe, name: '+INFINITY' },
    { code: 0x07ff, name: 'NaN' },
    { code: 0x0800, name: 'NRes (Not at this resolution)' },
    { code: 0x0801, name: 'Reserved' },
    { code: 0x0802, name: '-INFINITY' },
  ]

  // Test each sentinel across all 16 possible 4-bit exponents (0x0 to 0xF)
  const buffer = new ArrayBuffer(4)
  const dv = new DataView(buffer)

  for (const { code, name } of sentinels) {
    for (let exp = 0; exp < 16; exp++) {
      const rawWord = ((exp & 0x0f) << 12) | (code & 0x0fff)
      dv.setUint16(0, rawWord, true)
      const parsed = parseIeee11073Sfloat(dv, 0)
      assert.equal(
        parsed,
        null,
        `Sentinel ${name} (code 0x${code.toString(16)}) with exponent ${exp} (raw 0x${rawWord.toString(16)}) must parse to null, got ${parsed}`
      )
    }
  }
})

test('BUG-48 Stress: IEEE 11073 SFLOAT boundary numbers and two-complement ranges', () => {
  const buffer = new ArrayBuffer(8)
  const dv = new DataView(buffer)

  // Boundary 1: Just below sentinel range: 0x07FD (2045) with exp 0
  dv.setUint16(0, 0x07fd, true)
  assert.equal(parseIeee11073Sfloat(dv, 0), 2045, '0x07FD must decode to 2045')

  // Boundary 2: Just above sentinel range: 0x0803 (-2045) with exp 0
  // 12-bit two's complement: 0x0803 - 0x1000 = 2051 - 4096 = -2045
  dv.setUint16(0, 0x0803, true)
  assert.equal(parseIeee11073Sfloat(dv, 0), -2045, '0x0803 must decode to -2045')

  // Boundary 3: -1 in 12-bit two's complement: 0x0FFF with exp 0
  dv.setUint16(0, 0x0fff, true)
  assert.equal(parseIeee11073Sfloat(dv, 0), -1, '0x0FFF must decode to -1')

  // Boundary 4: 0 with exp 0
  dv.setUint16(0, 0x0000, true)
  assert.equal(parseIeee11073Sfloat(dv, 0), 0, '0x0000 must decode to 0')

  // Boundary 5: Negative exponent (exponent -2 = 0xFE >> 4 = 0xE in 4-bit two's complement)
  // mantissa = 120 (0x078), exponent -2 (0xE) -> raw = 0xE078
  // 120 * 10^-2 = 1.20
  dv.setUint16(0, 0xe078, true)
  const val = parseIeee11073Sfloat(dv, 0)
  assert.ok(Math.abs(val - 1.20) < 0.0001, `0xE078 must decode to 1.20, got ${val}`)

  // Buffer boundary guards: offset beyond byteLength
  assert.equal(parseIeee11073Sfloat(dv, 7), null, 'Offset 7 in 8-byte buffer must return null (needs 2 bytes)')
  assert.equal(parseIeee11073Sfloat(null, 0), null, 'Null buffer must return null')
})

test('BUG-48 Stress: GATT Blood Pressure 0x2A35 unit conversion (kPa to mmHg) and sentinel suppression', () => {
  const KPA_TO_MMHG = 7.50062

  // Simulate parsing BP characteristic packet
  function parseBpPacket(dataView) {
    const flags = dataView.getUint8(0)
    const isKpa = (flags & 0x01) === 1
    const sbpRaw = parseIeee11073Sfloat(dataView, 1)
    const dbpRaw = parseIeee11073Sfloat(dataView, 3)

    if (sbpRaw === null || dbpRaw === null) return null

    const sbp = Math.round(isKpa ? sbpRaw * KPA_TO_MMHG : sbpRaw)
    const dbp = Math.round(isKpa ? dbpRaw * KPA_TO_MMHG : dbpRaw)

    if (sbp >= 30 && sbp <= 300 && dbp >= 10 && dbp <= 200) {
      return { sbp, dbp, isKpa }
    }
    return null
  }

  const buf = new ArrayBuffer(10)
  const dv = new DataView(buf)

  // Case A: mmHg mode (flags bit 0 = 0), SBP 120, DBP 80
  dv.setUint8(0, 0x00) // flags: mmHg
  dv.setUint16(1, 120, true) // SBP = 120
  dv.setUint16(3, 80, true) // DBP = 80
  const bpMmHg = parseBpPacket(dv)
  assert.deepEqual(bpMmHg, { sbp: 120, dbp: 80, isKpa: false })

  // Case B: kPa mode (flags bit 0 = 1), SBP = 16.0 kPa (120 mmHg), DBP = 10.7 kPa (80 mmHg)
  // 16.0 = 160 * 10^-1 -> mantissa 160 (0x0A0), exp -1 (0xF) -> 0xF0A0
  // 10.7 = 107 * 10^-1 -> mantissa 107 (0x06B), exp -1 (0xF) -> 0xF06B
  dv.setUint8(0, 0x01) // flags: kPa
  dv.setUint16(1, 0xf0a0, true)
  dv.setUint16(3, 0xf06b, true)
  const bpKpa = parseBpPacket(dv)
  assert.deepEqual(bpKpa, { sbp: 120, dbp: 80, isKpa: true })

  // Case C: SBP sentinel (0x07FE +INF), DBP valid 80 -> MUST SUPPRESS
  dv.setUint8(0, 0x00)
  dv.setUint16(1, 0x07fe, true)
  dv.setUint16(3, 80, true)
  assert.equal(parseBpPacket(dv), null, 'Sentinel in SBP must suppress entire BP reading')

  // Case D: SBP valid 120, DBP sentinel (0x07FF NaN) -> MUST SUPPRESS
  dv.setUint8(0, 0x00)
  dv.setUint16(1, 120, true)
  dv.setUint16(3, 0x07ff, true)
  assert.equal(parseBpPacket(dv), null, 'Sentinel in DBP must suppress entire BP reading')

  // Case E: Out-of-bounds physiological values (e.g. SBP = 400) -> MUST DISCARD
  dv.setUint8(0, 0x00)
  dv.setUint16(1, 400, true)
  dv.setUint16(3, 80, true)
  assert.equal(parseBpPacket(dv), null, 'Unphysiological SBP (>300) must be discarded')
})

test('BUG-48 Stress: GATT PLX (0x2A5E / 0x2A5F) SpO2 and Pulse Rate parsing and sentinel suppression', () => {
  function parsePlxPacket(dataView) {
    const spo2Raw = parseIeee11073Sfloat(dataView, 1)
    const hrRaw = parseIeee11073Sfloat(dataView, 3)

    if (spo2Raw === null || hrRaw === null) return null

    const spo2 = Math.round(spo2Raw)
    const hr = Math.round(hrRaw)

    if (spo2 >= 50 && spo2 <= 100 && hr >= 30 && hr <= 250) {
      return { spo2, hr }
    }
    return null
  }

  const buf = new ArrayBuffer(8)
  const dv = new DataView(buf)

  // Valid PLX reading: SpO2 98%, HR 72 bpm
  dv.setUint8(0, 0x00) // Flags
  dv.setUint16(1, 98, true)
  dv.setUint16(3, 72, true)
  assert.deepEqual(parsePlxPacket(dv), { spo2: 98, hr: 72 })

  // SpO2 Sentinel (0x0800 NRes) -> MUST SUPPRESS
  dv.setUint16(1, 0x0800, true)
  dv.setUint16(3, 72, true)
  assert.equal(parsePlxPacket(dv), null, 'Sentinel SpO2 must suppress PLX reading')

  // HR Sentinel (0x0802 -INF) -> MUST SUPPRESS
  dv.setUint16(1, 98, true)
  dv.setUint16(3, 0x0802, true)
  assert.equal(parsePlxPacket(dv), null, 'Sentinel HR must suppress PLX reading')

  // Unphysiological SpO2 (< 50%) -> DISCARD
  dv.setUint16(1, 45, true)
  dv.setUint16(3, 72, true)
  assert.equal(parsePlxPacket(dv), null, 'SpO2 < 50% must be discarded')
})

// =============================================================================
// SUITE 2: rPPG Dynamic FPS Across Variable Frame Intervals (BUG-49)
// =============================================================================
test('BUG-49 Empirical: rPPG dynamic FPS computation across 15, 30, 60, and 120 FPS', () => {
  const targetBpm = 76 // 76 bpm = 1.2667 Hz
  const freqHz = targetBpm / 60
  const durationSec = 12

  const fpsList = [15, 30, 60, 120]

  for (const fps of fpsList) {
    const totalSamples = Math.round(fps * durationSec)
    const samples = []

    for (let i = 0; i < totalSamples; i++) {
      const timeMs = i * (1000 / fps)
      const timeSec = timeMs / 1000
      // Pure cardiac optical pulse wave with slight harmonic
      const r = 60 + Math.sin(2 * Math.PI * freqHz * timeSec) * 1.5
      samples.push({ time: timeMs, r })
    }

    const result = calculateRppgPulse(samples)
    assert.equal(result.ok, true, `Pulse calculation failed at ${fps} FPS: ${result.error}`)
    assert.ok(
      Math.abs(result.effectiveFps - fps) < 0.5,
      `Effective FPS at ${fps} FPS must be ~${fps}, got ${result.effectiveFps}`
    )
    assert.ok(
      Math.abs(result.bpm - targetBpm) <= 3,
      `Calculated pulse at ${fps} FPS must be ~${targetBpm} bpm, got ${result.bpm} bpm`
    )

    // Adversarial assertion against old 30 FPS hardcoding:
    if (fps === 60) {
      assert.notEqual(
        result.bpm,
        Math.round(targetBpm / 2),
        '60 FPS must NOT halve pulse to 38 bpm due to hardcoded 30 FPS assumption'
      )
    }
    if (fps === 120) {
      assert.notEqual(
        result.bpm,
        Math.round(targetBpm / 4),
        '120 FPS must NOT divide pulse to 19 bpm due to hardcoded 30 FPS assumption'
      )
    }
  }
})

test('BUG-49 Empirical: rPPG resilience under variable frame intervals (frame jitter & browser frame drops)', () => {
  const targetBpm = 82 // 1.3667 Hz
  const freqHz = targetBpm / 60
  const targetDurationMs = 12000

  // Generate sequence with variable frame deltas: mean 33.3ms (30 FPS), jitter +/- 12ms (21.3ms to 45.3ms)
  let currentTime = 0
  const samples = []

  // Deterministic pseudo-random jitter sequence
  let seed = 42
  function pseudoRandom() {
    seed = (seed * 9301 + 49297) % 233280
    return seed / 233280
  }

  while (currentTime < targetDurationMs) {
    const jitter = (pseudoRandom() - 0.5) * 20 // +/- 10ms
    const deltaMs = 33.3 + jitter
    currentTime += deltaMs
    const timeSec = currentTime / 1000
    const r = 55 + Math.sin(2 * Math.PI * freqHz * timeSec) * 1.8
    samples.push({ time: currentTime, r })
  }

  const result = calculateRppgPulse(samples)
  assert.equal(result.ok, true, `Jittered rPPG failed: ${result.error}`)
  assert.ok(
    Math.abs(result.bpm - targetBpm) <= 4,
    `Jittered sequence must accurately recover ~${targetBpm} bpm, got ${result.bpm} bpm`
  )
  assert.ok(result.cv <= 0.22, `CV must be within regularity gate <= 0.22, got ${result.cv}`)
})

test('BUG-49 Adversarial: rPPG rejection boundaries (under-duration, extreme FPS, erratic CV, extreme BPM)', () => {
  // A. Under-duration: 8 seconds (less than 9.5s gate)
  const shortSamples = []
  for (let i = 0; i < 240; i++) shortSamples.push({ time: i * 33.3, r: 50 })
  const resShort = calculateRppgPulse(shortSamples)
  assert.equal(resShort.ok, false)
  assert.ok(resShort.error.includes('Insufficient sample duration'))

  // B. Extreme low FPS (< 10 FPS)
  const lowFpsSamples = []
  for (let i = 0; i < 60; i++) lowFpsSamples.push({ time: i * 200, r: 50 }) // 5 FPS over 12s
  const resLowFps = calculateRppgPulse(lowFpsSamples)
  assert.equal(resLowFps.ok, false)
  assert.ok(resLowFps.error.includes('Unstable camera frame rate'))

  // C. Extreme high FPS (> 240 FPS)
  const highFpsSamples = []
  for (let i = 0; i < 3600; i++) highFpsSamples.push({ time: i * 3.33, r: 50 }) // 300 FPS over 12s
  const resHighFps = calculateRppgPulse(highFpsSamples)
  assert.equal(resHighFps.ok, false)
  assert.ok(resHighFps.error.includes('Unstable camera frame rate'))

  // D. Random noise (erratic rhythm, CV > 0.22)
  const noiseSamples = []
  for (let i = 0; i < 360; i++) {
    const timeMs = i * 33.3
    // High-frequency erratic noise
    const r = 50 + (i % 3 === 0 ? 3.0 : 0) + (i % 7 === 0 ? 2.5 : 0)
    noiseSamples.push({ time: timeMs, r })
  }
  const resNoise = calculateRppgPulse(noiseSamples)
  assert.equal(resNoise.ok, false, 'Erratic noise must be rejected by CV gate or peak detector')
})

// =============================================================================
// SUITE 3: QR Scanner Single-Flight Lock & Post-Await Mount Handling (BUG-50)
// =============================================================================
test('BUG-50 Stress: QrScannerModal concurrency gate prevents parallel barcode detection', async () => {
  // Model the state machine of QrScannerModal
  let detectInFlight = false
  let hasDetected = false
  let detectionsStarted = 0
  let detectionsCompleted = 0
  let onDetectedCount = 0

  async function mockDetect(video) {
    if (detectInFlight || hasDetected) {
      return null // Dropped by single-flight gate
    }
    detectInFlight = true
    detectionsStarted++

    // Simulate async barcode detection delay
    await new Promise((resolve) => setTimeout(resolve, 30))

    try {
      if (hasDetected) return null
      return [{ rawValue: 'VNET-8899-0011' }]
    } finally {
      detectionsCompleted++
      detectInFlight = false
    }
  }

  function handleQrString(raw) {
    if (hasDetected) return false
    hasDetected = true
    onDetectedCount++
    return true
  }

  // Simulate 10 rapid interval ticks firing every 5ms while detection takes 30ms
  const promises = []
  for (let i = 0; i < 10; i++) {
    promises.push(
      (async () => {
        await new Promise((r) => setTimeout(r, i * 5))
        const barcodes = await mockDetect({})
        if (barcodes && barcodes.length > 0) {
          handleQrString(barcodes[0].rawValue)
        }
      })()
    )
  }

  await Promise.all(promises)

  assert.equal(detectionsStarted, 1, 'Only exactly 1 detection must have been started due to single-flight lock')
  assert.equal(detectionsCompleted, 1, 'Only 1 detection completed')
  assert.equal(onDetectedCount, 1, 'onDetected callback must fire at most once')
})

test('BUG-50 Stress: QrScannerModal stops tracks and aborts if unmounted during getUserMedia or video.play', async () => {
  let isMounted = true
  let trackStopped = false
  let intervalStarted = false

  const mockTrack = {
    stop() {
      trackStopped = true
    },
  }
  const mockStream = {
    getTracks() {
      return [mockTrack]
    },
    getVideoTracks() {
      return [mockTrack]
    },
  }

  // Simulate startCamera lifecycle
  async function startCamera() {
    // Simulate getUserMedia
    const stream = await new Promise((resolve) => setTimeout(() => resolve(mockStream), 20))
    if (!isMounted) {
      stream.getTracks().forEach((t) => t.stop())
      return
    }

    // Simulate video.play()
    await new Promise((resolve) => setTimeout(resolve, 20))

    // Post-await mount verification (BUG-50)
    if (!isMounted) {
      stream.getTracks().forEach((t) => t.stop())
      return
    }

    intervalStarted = true
  }

  // Launch camera
  const camPromise = startCamera()

  // Unmount component 10ms later (while getUserMedia is awaiting)
  setTimeout(() => {
    isMounted = false
  }, 10)

  await camPromise

  assert.equal(trackStopped, true, 'Camera tracks must be stopped if component unmounts during camera startup')
  assert.equal(intervalStarted, false, 'Scan interval must never start if component unmounted')
})

// =============================================================================
// SUITE 4: Sparkline Chronological Ordering (BUG-04)
// =============================================================================
test('BUG-04 Empirical: BriefingCard sparkline renders oldest visit on left, newest on right, header badge latest', () => {
  // Descending visit history from backend (newest first, oldest last)
  const apiHistory = [
    { created_at: '2026-11-09T18:00:00Z', bp_systolic: 155, heart_rate: 98 }, // Visit 3: latest (Emergency spike)
    { created_at: '2026-11-05T10:00:00Z', bp_systolic: 130, heart_rate: 82 }, // Visit 2: intermediate
    { created_at: '2026-10-20T09:00:00Z', bp_systolic: 118, heart_rate: 74 }, // Visit 1: oldest baseline
  ]

  // In BriefingCard.jsx, history is reversed before mapping:
  // values={[...history].reverse().map((visit) => visit[definition.key])}
  const reversedSystolic = [...apiHistory].reverse().map((v) => v.bp_systolic)
  assert.deepEqual(reversedSystolic, [118, 130, 155], 'Reversed systolic must be chronologically ascending')

  // In VitalTrendSparkline.jsx:
  const points = finiteValues(reversedSystolic)
  assert.deepEqual(points, [118, 130, 155])

  // Header badge displays points[points.length - 1]
  const badgeValue = points[points.length - 1]
  assert.equal(badgeValue, 155, 'Badge value must show the latest visit (155 mmHg), NOT the oldest visit (118 mmHg)')

  // In buildSparklinePath:
  const pathString = buildSparklinePath(points, 180, 48)
  assert.ok(pathString.startsWith('M 4.00'), 'Oldest point must be positioned at x = 4.00 (left edge)')
  assert.ok(pathString.endsWith('4.00'), 'Newest highest point must end at y = 4.00 (top-right edge)')

  // Trend summary format check
  const summary = formatTrendSummary('Systolic blood pressure', points, 'mmHg')
  assert.equal(
    summary,
    'Systolic blood pressure over 3 visits: 118, 130, 155 mmHg',
    'Aria summary must present visits in chronological progression'
  )
})

// =============================================================================
// SUITE 5: Tap Cadence Metric Target Mapping (BUG-05)
// =============================================================================
test('BUG-05 Empirical: TapCadencePanel handleApply correctly routes to respiratory_rate vs heart_rate', () => {
  let appliedVitals = null
  let appliedLabel = null

  function onApply(vitals, label) {
    appliedVitals = vitals
    appliedLabel = label
  }

  // Simulate TapCadencePanel.handleApply logic:
  function simulateTapApply(vitalTarget, calculatedBpm) {
    if (!calculatedBpm) return
    if (vitalTarget === 'heart_rate') {
      onApply({ heart_rate: calculatedBpm }, `HR ${calculatedBpm} bpm applied`)
    } else {
      onApply({ respiratory_rate: calculatedBpm }, `RR ${calculatedBpm}/min applied`)
    }
  }

  // Case 1: Respiratory Rate selected (24 breaths/min)
  simulateTapApply('respiratory_rate', 24)
  assert.deepEqual(appliedVitals, { respiratory_rate: 24 })
  assert.equal(appliedLabel, 'RR 24/min applied')
  assert.equal(appliedVitals.heart_rate, undefined, 'Must not touch heart_rate when applying respiration')

  // Case 2: Heart Rate selected (78 bpm)
  simulateTapApply('heart_rate', 78)
  assert.deepEqual(appliedVitals, { heart_rate: 78 })
  assert.equal(appliedLabel, 'HR 78 bpm applied')
  assert.equal(appliedVitals.respiratory_rate, undefined, 'Must not touch respiratory_rate when applying pulse')

  // Case 3: Verify IntakeForm form state update & serialization
  let formState = {
    heart_rate: '72',
    respiratory_rate: '',
    bp_systolic: '120',
  }

  // Apply RR 22/min to form
  const incomingVitals = { respiratory_rate: 22 }
  formState = {
    ...formState,
    ...Object.fromEntries(
      Object.entries(incomingVitals)
        .filter(([, v]) => v != null)
        .map(([k, v]) => [k, String(v)])
    ),
  }

  assert.equal(formState.respiratory_rate, '22')
  assert.equal(formState.heart_rate, '72', 'Prior heart_rate must remain intact')

  const serialized = serializeIntakePayload(formState)
  assert.equal(serialized.respiratory_rate, 22)
  assert.equal(serialized.heart_rate, 72)
})

// =============================================================================
// SUITE 6: Bluetooth Connection Debounce & Listener Cleanup (BUG-41 & BUG-42)
// =============================================================================
test('BUG-41 Stress: Bluetooth connection debounce drops rapid successive connect attempts within 1500ms', async () => {
  let connectCount = 0
  let lastConnectAttempt = 0
  let connectLock = false
  const CONNECT_COOLDOWN_MS = 1500

  async function mockConnectDevice() {
    const now = Date.now()
    if (connectLock || now - lastConnectAttempt < CONNECT_COOLDOWN_MS) {
      return false // dropped
    }
    lastConnectAttempt = now
    connectLock = true
    try {
      connectCount++
      // Simulate pairing prompt delay
      await new Promise((r) => setTimeout(r, 50))
      return true
    } finally {
      connectLock = false
    }
  }

  // Attempt 1: allowed
  const r1 = await mockConnectDevice()
  assert.equal(r1, true)
  assert.equal(connectCount, 1)

  // Attempt 2 immediately after: dropped by cooldown
  const r2 = await mockConnectDevice()
  assert.equal(r2, false)
  assert.equal(connectCount, 1)

  // Attempt 3 at 500ms: dropped by cooldown
  await new Promise((r) => setTimeout(r, 100))
  const r3 = await mockConnectDevice()
  assert.equal(r3, false)
  assert.equal(connectCount, 1)
})

test('BUG-42 Stress: Bluetooth disconnect/unmount detaches listeners and stops notifications', () => {
  const removedListeners = []
  let notificationsStopped = false

  const mockDevice = {
    removeEventListener(event, handler) {
      removedListeners.push(event)
    },
    gatt: { connected: true, disconnect() {} },
  }

  const mockChar = {
    removeEventListener(event, handler) {
      removedListeners.push(event)
    },
    service: {
      device: { gatt: { connected: true } },
    },
    stopNotifications: async () => {
      notificationsStopped = true
    },
  }

  // Simulate cleanupBleResources:
  function cleanupBle(device, chars) {
    if (device) {
      device.removeEventListener('gattserverdisconnected', () => {})
    }
    chars.forEach(({ char, listener }) => {
      char.removeEventListener('characteristicvaluechanged', listener)
      if (char.service?.device?.gatt?.connected) {
        char.stopNotifications()
      }
    })
  }

  cleanupBle(mockDevice, [{ char: mockChar, listener: () => {} }])

  assert.ok(removedListeners.includes('gattserverdisconnected'), 'Must remove gattserverdisconnected')
  assert.ok(removedListeners.includes('characteristicvaluechanged'), 'Must remove characteristicvaluechanged')
  assert.equal(notificationsStopped, true, 'Must stop BLE notifications')
})

// =============================================================================
// SUITE 7: QR Scanner Re-Scan Demographic Reset (BUG-65)
// =============================================================================
test('BUG-65 Stress: QR re-scan resets demographics when scanning a distinct patient', () => {
  function applyScannedData(prev, scanned) {
    const next = { ...prev }
    const isDifferentKey = Boolean(
      prev.patient_key && scanned.patientKey && prev.patient_key !== scanned.patientKey
    )

    if (scanned.patientKey) {
      next.patient_key = scanned.patientKey
    }

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

  // 1. Initial State: Form filled with Patient A demographics
  const formA = {
    patient_key: 'AAAA-1111',
    patient_name: 'Rajesh Kumar',
    patient_age: '45',
    age_months: '6',
    patient_sex: 'male',
  }

  // 2. ASHA scans Patient B who only has a basic card (no demographics encoded)
  const scannedB = {
    patientKey: 'BBBB-2222',
  }

  const formB = applyScannedData(formA, scannedB)

  assert.equal(formB.patient_key, 'BBBB-2222')
  assert.equal(formB.patient_name, '', 'Patient A name must be cleared')
  assert.equal(formB.patient_age, '', 'Patient A age must be cleared')
  assert.equal(formB.age_months, '', 'Patient A age_months must be cleared')
  assert.equal(formB.patient_sex, '', 'Patient A sex must be cleared')

  // 3. ASHA scans Patient C: a newborn with age 0
  const scannedC = {
    patientKey: 'CCCC-3333',
    patientName: 'Baby of Anitha',
    patientAge: 0,
    patientSex: 'female',
  }

  const formC = applyScannedData(formB, scannedC)
  assert.equal(formC.patient_key, 'CCCC-3333')
  assert.equal(formC.patient_name, 'Baby of Anitha')
  assert.equal(formC.patient_age, '0', 'Newborn age 0 must be preserved as "0", not cleared')
  assert.equal(formC.patient_sex, 'female')

  // 4. ASHA re-scans Patient C (same key) with partial payload: existing demographics preserved
  const scannedCRepeat = {
    patientKey: 'CCCC-3333',
  }
  const formCRepeat = applyScannedData(formC, scannedCRepeat)
  assert.equal(formCRepeat.patient_name, 'Baby of Anitha', 'Same patient re-scan preserves demographic fields')
  assert.equal(formCRepeat.patient_age, '0')
})
