import { useState, useEffect, useRef, useCallback } from 'react'
import { Heart, Activity, Bluetooth, Video, Check, RotateCcw, AlertCircle, Zap } from 'lucide-react'

/**
 * VitalCaptureAssist — ADR §50 Hardware-Assisted & Contactless Vital Capture
 *
 * Implements:
 * 1. 15-second Tap-Tempo Cadence Calculator (Pulse & Respiratory Rate)
 * 2. Camera Torch Fingertip rPPG Pulse Estimator (Green/Red variance, CV_IBI <= 0.22 gate, 40..190 bpm)
 * 3. Web Bluetooth GATT Medical Device Bridge (0x1810 BP, 0x180D HR, 0x1822 SpO2)
 *
 * @param {Object} props
 * @param {Function} props.onApplyVitals - Callback to update parent form with vitals
 */
export default function VitalCaptureAssist({ onApplyVitals }) {
  const [activeTab, setActiveTab] = useState('tap') // 'tap' | 'rppg' | 'ble'
  const [appliedNotice, setAppliedNotice] = useState(null)

  const showApplied = (msg) => {
    setAppliedNotice(msg)
    setTimeout(() => setAppliedNotice(null), 3000)
  }

  return (
    <div className="mb-4 bg-surface2 border border-surface3 rounded-xl p-4 shadow-sm">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Activity size={18} className="text-forest" />
          <h3 className="text-xs font-mono font-bold text-text uppercase tracking-wider">
            Vital Capture Assist (ADR §50)
          </h3>
        </div>
        {appliedNotice && (
          <span className="text-xs font-medium text-forest bg-forest/10 border border-forest/20 px-2 py-0.5 rounded-full flex items-center gap-1 animate-fade-in">
            <Check size={12} /> {appliedNotice}
          </span>
        )}
      </div>

      {/* Mode navigation tabs */}
      <div className="flex border-b border-surface3 mb-4 gap-1">
        <button
          type="button"
          onClick={() => setActiveTab('tap')}
          className={`px-3 py-1.5 text-xs font-medium rounded-t-lg transition-colors cursor-pointer flex items-center gap-1.5 ${
            activeTab === 'tap'
              ? 'bg-surface text-forest border-t border-x border-surface3 -mb-px font-semibold'
              : 'text-text3 hover:text-text hover:bg-surface/50'
          }`}
        >
          <Activity size={14} />
          Tap Cadence
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('rppg')}
          className={`px-3 py-1.5 text-xs font-medium rounded-t-lg transition-colors cursor-pointer flex items-center gap-1.5 ${
            activeTab === 'rppg'
              ? 'bg-surface text-forest border-t border-x border-surface3 -mb-px font-semibold'
              : 'text-text3 hover:text-text hover:bg-surface/50'
          }`}
        >
          <Video size={14} />
          Camera Pulse (rPPG)
        </button>

        <button
          type="button"
          onClick={() => setActiveTab('ble')}
          className={`px-3 py-1.5 text-xs font-medium rounded-t-lg transition-colors cursor-pointer flex items-center gap-1.5 ${
            activeTab === 'ble'
              ? 'bg-surface text-forest border-t border-x border-surface3 -mb-px font-semibold'
              : 'text-text3 hover:text-text hover:bg-surface/50'
          }`}
        >
          <Bluetooth size={14} />
          Bluetooth Devices
        </button>
      </div>

      {/* Tab Panels */}
      {activeTab === 'tap' && (
        <TapCadencePanel
          onApply={(vitals, label) => {
            onApplyVitals(vitals)
            showApplied(label)
          }}
        />
      )}

      {activeTab === 'rppg' && (
        <RppgCameraPanel
          onApply={(bpm) => {
            onApplyVitals({ heart_rate: bpm })
            showApplied(`Pulse ${bpm} bpm applied`)
          }}
        />
      )}

      {activeTab === 'ble' && (
        <BluetoothGattPanel
          onApply={(vitals, label) => {
            onApplyVitals(vitals)
            showApplied(label)
          }}
        />
      )}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// 1. Tap-Tempo Cadence Panel
// ─────────────────────────────────────────────────────────────────────────────
function TapCadencePanel({ onApply }) {
  const [vitalTarget, setVitalTarget] = useState('heart_rate') // 'heart_rate' | 'respiratory_rate'
  const [taps, setTaps] = useState([])
  const [calculatedBpm, setCalculatedBpm] = useState(null)
  const [isBeating, setIsBeating] = useState(false)

  const handleTap = () => {
    const now = typeof performance !== 'undefined' ? performance.now() : Date.now()
    setIsBeating(true)
    setTimeout(() => setIsBeating(false), 120)

    // Keep taps from trailing 15 seconds
    const updated = [...taps, now].filter((t) => now - t <= 15000)
    setTaps(updated)

    if (updated.length >= 4) {
      const intervals = []
      for (let i = 1; i < updated.length; i++) {
        intervals.push(updated[i] - updated[i - 1])
      }
      const meanInterval = intervals.reduce((a, b) => a + b, 0) / intervals.length
      if (meanInterval > 0) {
        const bpm = Math.round(60000 / meanInterval)
        if (vitalTarget === 'heart_rate' && bpm >= 30 && bpm <= 220) {
          setCalculatedBpm(bpm)
        } else if (vitalTarget === 'respiratory_rate' && bpm >= 6 && bpm <= 60) {
          setCalculatedBpm(bpm)
        } else {
          setCalculatedBpm(null)
        }
      }
    }
  }

  const handleReset = () => {
    setTaps([])
    setCalculatedBpm(null)
  }

  const handleApply = () => {
    if (!calculatedBpm) return
    if (vitalTarget === 'heart_rate') {
      onApply({ heart_rate: calculatedBpm }, `HR ${calculatedBpm} bpm applied`)
    } else {
      onApply({ respiratory_rate: calculatedBpm }, `RR ${calculatedBpm}/min applied`)
    }
  }

  return (
    <div className="space-y-4">
      {/* Target selection */}
      <div className="flex items-center justify-between text-xs">
        <span className="text-text2 font-medium">Measurement Target:</span>
        <div className="flex gap-2">
          <label className="flex items-center gap-1.5 cursor-pointer">
            <input
              type="radio"
              name="tapTarget"
              checked={vitalTarget === 'heart_rate'}
              onChange={() => {
                setVitalTarget('heart_rate')
                handleReset()
              }}
              className="accent-forest"
            />
            <span className="text-text">Radial Pulse (30–220 bpm)</span>
          </label>
          <label className="flex items-center gap-1.5 cursor-pointer">
            <input
              type="radio"
              name="tapTarget"
              checked={vitalTarget === 'respiratory_rate'}
              onChange={() => {
                setVitalTarget('respiratory_rate')
                handleReset()
              }}
              className="accent-forest"
            />
            <span className="text-text">Respirations (6–60/min)</span>
          </label>
        </div>
      </div>

      {/* Tap Interaction Button */}
      <div className="flex flex-col items-center justify-center p-4 bg-surface rounded-xl border border-surface3">
        <button
          type="button"
          onClick={handleTap}
          className={`w-32 h-32 rounded-full border-4 flex flex-col items-center justify-center transition-all duration-100 cursor-pointer select-none active:scale-95 shadow-md ${
            isBeating
              ? 'border-forest bg-forest/20 scale-105 shadow-lg'
              : 'border-forest/40 bg-forest/5 hover:border-forest/80'
          }`}
        >
          <Heart
            size={36}
            className={`transition-transform duration-100 ${
              isBeating ? 'text-emergency fill-emergency scale-125' : 'text-forest'
            }`}
          />
          <span className="text-xs font-bold text-text mt-1 uppercase tracking-wider">
            TAP HERE
          </span>
          <span className="text-[10px] text-text3 font-mono">
            {taps.length} tap{taps.length === 1 ? '' : 's'}
          </span>
        </button>

        {/* Live calculated cadence display */}
        <div className="mt-3 text-center">
          {calculatedBpm ? (
            <div className="flex items-baseline justify-center gap-1">
              <span className="text-3xl font-bold font-mono text-forest">
                {calculatedBpm}
              </span>
              <span className="text-xs text-text3 font-mono">
                {vitalTarget === 'heart_rate' ? 'BPM' : 'breaths/min'}
              </span>
            </div>
          ) : (
            <p className="text-xs text-text3">
              {taps.length < 4
                ? `Tap in rhythm with patient ${
                    vitalTarget === 'heart_rate' ? 'pulse' : 'breathing'
                  } (need at least 4 taps)`
                : 'Pacing out of normal physiological range, keep tapping...'}
            </p>
          )}
        </div>

        {/* Action controls */}
        <div className="flex gap-2 mt-3">
          <button
            type="button"
            onClick={handleApply}
            disabled={!calculatedBpm}
            className="px-4 py-1.5 bg-forest text-white text-xs font-semibold rounded-lg hover:bg-forest/90 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer transition-colors"
          >
            Apply to Form
          </button>
          <button
            type="button"
            onClick={handleReset}
            disabled={taps.length === 0}
            className="px-3 py-1.5 bg-surface2 text-text3 hover:text-text text-xs rounded-lg border border-surface3 disabled:opacity-40 cursor-pointer flex items-center gap-1 transition-colors"
          >
            <RotateCcw size={12} /> Reset
          </button>
        </div>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// 2. Camera Torch Fingertip rPPG Pulse Estimator
// ─────────────────────────────────────────────────────────────────────────────
/**
 * Evaluates pulse signal with dynamic effective FPS derived from sample timestamps:
 * 1. Time-based duration gate (>= 9.5s)
 * 2. Dynamic effective FPS calculation from sample timestamps (BUG-49)
 * 3. 2.0s settling window discard (auto-exposure)
 * 4. 1-second sliding window detrending
 * 5. 300ms peak refractory period (<= 200 bpm)
 * 6. Regularity SNR gate: CV_IBI <= 0.22
 * 7. Physiological range gate: 40..190 bpm
 */
export function calculateRppgPulse(samples) {
  if (!samples || samples.length < 30) {
    return { ok: false, error: 'Too few camera samples recorded. Please retry.' }
  }

  const t0 = samples[0].time
  const tEnd = samples[samples.length - 1].time
  const totalDurationMs = tEnd - t0

  // Time-based duration gate (>= 9.5s)
  if (totalDurationMs < 9500) {
    return { ok: false, error: 'Insufficient sample duration. Please retry for a full 12 seconds.' }
  }

  // Dynamic effective FPS from sample timestamps (BUG-49)
  const effectiveFps = (samples.length - 1) / (totalDurationMs / 1000)
  if (!Number.isFinite(effectiveFps) || effectiveFps < 10 || effectiveFps > 240) {
    return { ok: false, error: 'Unstable camera frame rate detected. Please retry.' }
  }

  // Discard initial 2.0s (auto-exposure settling)
  const activeSamples = samples.filter((s) => s.time - t0 >= 2000)
  const activeDurationMs =
    activeSamples.length > 0
      ? activeSamples[activeSamples.length - 1].time - activeSamples[0].time
      : 0

  if (activeSamples.length < 20 || activeDurationMs < 6000) {
    return { ok: false, error: 'Too few steady samples captured.' }
  }

  const rawR = activeSamples.map((s) => s.r)

  // Detrending: 1-second rolling mean subtraction based on effectiveFps
  const windowSize = Math.max(5, Math.round(effectiveFps))
  const halfWin = Math.floor(windowSize / 2)
  const detrended = []

  for (let i = 0; i < rawR.length; i++) {
    const start = Math.max(0, i - halfWin)
    const end = Math.min(rawR.length, i + halfWin + 1)
    let sum = 0
    for (let j = start; j < end; j++) sum += rawR[j]
    const localMean = sum / (end - start)
    detrended.push(rawR[i] - localMean)
  }

  // Peak detection with refractory period >= 300ms (Math.round(0.3 * effectiveFps) frames)
  const refractoryFrames = Math.max(2, Math.round(0.3 * effectiveFps))
  const peaks = []
  let lastPeak = -refractoryFrames

  for (let i = 1; i < detrended.length - 1; i++) {
    if (
      detrended[i] > 0.15 &&
      detrended[i] > detrended[i - 1] &&
      detrended[i] > detrended[i + 1] &&
      i - lastPeak >= refractoryFrames
    ) {
      peaks.push(i)
      lastPeak = i
    }
  }

  if (peaks.length < 4) {
    return {
      ok: false,
      error: 'Could not detect distinct pulse peaks. Please ensure flash is on and lens is fully covered.',
    }
  }

  // Inter-beat intervals (IBI in ms) calculated directly from sample timestamps (BUG-49)
  const ibis = []
  for (let i = 1; i < peaks.length; i++) {
    const deltaMs = activeSamples[peaks[i]].time - activeSamples[peaks[i - 1]].time
    ibis.push(deltaMs)
  }

  const meanIbi = ibis.reduce((a, b) => a + b, 0) / ibis.length
  const variance = ibis.reduce((a, b) => a + Math.pow(b - meanIbi, 2), 0) / ibis.length
  const stdDev = Math.sqrt(variance)
  const cv = meanIbi > 0 ? stdDev / meanIbi : 1.0

  // Regularity Gate (ADR §50): CV_IBI <= 0.22
  if (cv > 0.22) {
    return {
      ok: false,
      error: `Pulse rhythm too erratic or motion-corrupted (CV = ${cv.toFixed(2)} > 0.22 gate). Please hold finger steady and retry.`,
      cv,
    }
  }

  const bpm = Math.round(60000 / meanIbi)

  // Physiological boundary gate (ADR §50): 40..190 bpm
  if (bpm < 40 || bpm > 190) {
    return {
      ok: false,
      error: `Calculated pulse (${bpm} bpm) out of physiological range (40–190 bpm). Please retry.`,
      bpm,
      cv,
    }
  }

  return { ok: true, bpm, cv, effectiveFps }
}

function RppgCameraPanel({ onApply }) {
  const [measuring, setMeasuring] = useState(false)
  const [progress, setProgress] = useState(0) // 0 .. 100%
  const [statusMessage, setStatusMessage] = useState('Cover the rear camera & flashlight with your index fingertip.')
  const [resultBpm, setResultBpm] = useState(null)
  const [resultCv, setResultCv] = useState(null)
  const [errorMsg, setErrorMsg] = useState(null)

  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const streamRef = useRef(null)
  const animFrameRef = useRef(null)
  const samplesRef = useRef([])
  const startTimeRef = useRef(null)

  const stopCameraStream = useCallback(() => {
    if (animFrameRef.current) {
      cancelAnimationFrame(animFrameRef.current)
      animFrameRef.current = null
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop())
      streamRef.current = null
    }
    setMeasuring(false)
  }, [])

  useEffect(() => {
    return () => {
      stopCameraStream()
    }
  }, [stopCameraStream])

  const startRppgCapture = async () => {
    setErrorMsg(null)
    setResultBpm(null)
    setResultCv(null)
    setProgress(0)
    samplesRef.current = []

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      setErrorMsg('Camera access is not supported on this browser.')
      return
    }

    try {
      const constraints = {
        video: {
          facingMode: { ideal: 'environment' },
          width: { ideal: 320 },
          height: { ideal: 240 },
        },
        audio: false,
      }

      const stream = await navigator.mediaDevices.getUserMedia(constraints)
      streamRef.current = stream

      if (videoRef.current) {
        videoRef.current.srcObject = stream
        await videoRef.current.play().catch(() => {})
      }

      // Try turning on flashlight torch
      const track = stream.getVideoTracks()[0]
      if (track && typeof track.getCapabilities === 'function') {
        const caps = track.getCapabilities()
        if (caps && caps.torch) {
          await track.applyConstraints({ advanced: [{ torch: true }] }).catch(() => {})
        }
      }

      setMeasuring(true)
      setStatusMessage('Acquiring fingertip pulse signal... Hold still.')
      startTimeRef.current = performance.now()

      const canvas = canvasRef.current || document.createElement('canvas')
      canvas.width = 32
      canvas.height = 32
      const ctx = canvas.getContext('2d', { willReadFrequently: true })

      const DURATION_MS = 12000 // 12-second acquisition window

      function sampleFrame() {
        if (!videoRef.current || videoRef.current.readyState < 2) {
          animFrameRef.current = requestAnimationFrame(sampleFrame)
          return
        }

        const now = performance.now()
        const elapsed = now - startTimeRef.current
        const pct = Math.min(100, Math.round((elapsed / DURATION_MS) * 100))
        setProgress(pct)

        // Draw downscaled 32x32 video frame
        ctx.drawImage(videoRef.current, 0, 0, 32, 32)
        const frameData = ctx.getImageData(0, 0, 32, 32).data

        let sumR = 0
        let sumG = 0
        const totalPixels = 1024
        for (let i = 0; i < frameData.length; i += 4) {
          sumR += frameData[i]
          sumG += frameData[i + 1]
        }
        const meanR = sumR / totalPixels
        const meanG = sumG / totalPixels

        samplesRef.current.push({
          time: now,
          r: meanR,
          g: meanG,
        })

        // Fingertip placement check
        if (meanR < 40 || meanR < meanG * 1.1) {
          setStatusMessage('Please cover the rear camera and flash firmly with your fingertip.')
        } else {
          setStatusMessage('Measuring pulse wave... Hold steady.')
        }

        if (elapsed < DURATION_MS) {
          animFrameRef.current = requestAnimationFrame(sampleFrame)
        } else {
          // Finished acquisition — analyze pulse
          stopCameraStream()
          processRppgSamples(samplesRef.current)
        }
      }

      animFrameRef.current = requestAnimationFrame(sampleFrame)
    } catch (err) {
      console.warn('[VitalNet] Camera rPPG error', err)
      setErrorMsg(
        err.name === 'NotAllowedError'
          ? 'Camera permission denied. Please allow camera access.'
          : 'Failed to access camera for rPPG pulse estimation.'
      )
      setMeasuring(false)
    }
  }

  function processRppgSamples(samples) {
    const res = calculateRppgPulse(samples)
    if (!res.ok) {
      setErrorMsg(res.error)
      if (res.cv != null) setResultCv(parseFloat(res.cv.toFixed(3)))
      return
    }
    setResultCv(parseFloat(res.cv.toFixed(3)))
    setResultBpm(res.bpm)
    setStatusMessage(`Estimated Pulse: ${res.bpm} bpm (Regular rhythm, CV = ${res.cv.toFixed(2)})`)
  }

  return (
    <div className="space-y-3">
      {/* Hidden video and canvas elements */}
      <video ref={videoRef} playsInline muted className="hidden" />
      <canvas ref={canvasRef} className="hidden" />

      <div className="bg-surface rounded-xl p-4 border border-surface3 flex flex-col items-center">
        {/* Visual pulse status ring */}
        <div className="relative w-28 h-28 flex items-center justify-center my-2">
          {/* Progress circular SVG */}
          <svg className="w-full h-full -rotate-90">
            <circle
              cx="56"
              cy="56"
              r="48"
              stroke="currentColor"
              strokeWidth="6"
              className="text-surface3"
              fill="transparent"
            />
            <circle
              cx="56"
              cy="56"
              r="48"
              stroke="currentColor"
              strokeWidth="6"
              strokeDasharray="301.6"
              strokeDashoffset={301.6 - (301.6 * progress) / 100}
              strokeLinecap="round"
              className="text-forest transition-all duration-200"
              fill="transparent"
            />
          </svg>

          <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
            {measuring ? (
              <>
                <Heart size={28} className="text-emergency animate-pulse" />
                <span className="text-xs font-mono font-bold text-text mt-1">{progress}%</span>
              </>
            ) : resultBpm ? (
              <>
                <span className="text-2xl font-bold font-mono text-forest leading-none">{resultBpm}</span>
                <span className="text-[10px] text-text3 font-mono mt-0.5">BPM</span>
              </>
            ) : (
              <Zap size={28} className="text-text3" />
            )}
          </div>
        </div>

        <p className="text-xs text-text2 text-center max-w-xs mt-1">
          {statusMessage}
        </p>

        {errorMsg && (
          <div className="mt-2 text-xs text-emergency bg-emergency/10 border border-emergency/20 rounded-lg p-2 flex items-start gap-1.5 max-w-sm">
            <AlertCircle size={14} className="shrink-0 mt-0.5" />
            <span>{errorMsg}</span>
          </div>
        )}

        {/* Action button */}
        <div className="flex gap-2 mt-4">
          {!measuring ? (
            <button
              type="button"
              onClick={startRppgCapture}
              className="px-4 py-2 bg-forest text-white text-xs font-semibold rounded-lg hover:bg-forest/90 cursor-pointer shadow-sm transition-all"
            >
              {resultBpm ? 'Measure Again' : 'Start Camera Pulse (12s)'}
            </button>
          ) : (
            <button
              type="button"
              onClick={stopCameraStream}
              className="px-4 py-2 bg-surface2 text-emergency border border-emergency/30 text-xs font-semibold rounded-lg hover:bg-emergency/10 cursor-pointer transition-all"
            >
              Cancel
            </button>
          )}

          {resultBpm && (
            <button
              type="button"
              onClick={() => onApply(resultBpm)}
              className="px-4 py-2 bg-forest text-white text-xs font-semibold rounded-lg hover:bg-forest/90 cursor-pointer shadow-btn transition-all flex items-center gap-1"
            >
              <Check size={14} /> Apply Pulse
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// 3. Web Bluetooth GATT Medical Device Bridge
// ─────────────────────────────────────────────────────────────────────────────
/**
 * Standalone IEEE 11073-20601 SFLOAT parser supporting sentinels (BUG-48):
 * - 0x07FE: +INFINITY -> null
 * - 0x07FF: NaN -> null
 * - 0x0800: NRes -> null
 * - 0x0801: Reserved -> null
 * - 0x0802: -INFINITY -> null
 */
export function parseIeee11073Sfloat(val, offset) {
  if (!val || offset + 2 > val.byteLength) return null
  const raw = val.getUint16(offset, true)
  const mantissaRaw = raw & 0x0fff

  // Check IEEE 11073-20601 special value sentinels:
  if (mantissaRaw >= 0x07fe && mantissaRaw <= 0x0802) {
    return null
  }

  let mantissa = mantissaRaw
  if (mantissa >= 0x0800) mantissa -= 0x1000

  let exponent = raw >> 12
  if (exponent >= 0x08) exponent -= 0x10

  const result = mantissa * Math.pow(10, exponent)
  return Number.isFinite(result) ? result : null
}

function BluetoothGattPanel({ onApply }) {
  const [device, setDevice] = useState(null)
  const [connecting, setConnecting] = useState(false)
  const [connected, setConnected] = useState(false)
  const [lastReading, setLastReading] = useState(null)
  const [bleError, setBleError] = useState(null)

  const lastConnectAttemptRef = useRef(0)
  const connectLockRef = useRef(false)
  const CONNECT_COOLDOWN_MS = 1500

  const deviceRef = useRef(null)
  const activeCharsRef = useRef([])
  const disconnectHandlerRef = useRef(null)

  const handleDisconnect = useCallback(() => {
    setConnected(false)
    setLastReading(null)
  }, [])
  disconnectHandlerRef.current = handleDisconnect

  const cleanupBleResources = useCallback(() => {
    if (deviceRef.current && disconnectHandlerRef.current) {
      try {
        deviceRef.current.removeEventListener('gattserverdisconnected', disconnectHandlerRef.current)
      } catch {}
    }
    activeCharsRef.current.forEach(({ char, listener }) => {
      try {
        char.removeEventListener('characteristicvaluechanged', listener)
        if (char.service?.device?.gatt?.connected) {
          char.stopNotifications().catch(() => {})
        }
      } catch {}
    })
    activeCharsRef.current = []
  }, [])

  const disconnectDevice = () => {
    cleanupBleResources()
    if (deviceRef.current?.gatt?.connected) {
      deviceRef.current.gatt.disconnect()
    }
    deviceRef.current = null
    setDevice(null)
    setConnected(false)
    setLastReading(null)
  }

  useEffect(() => {
    return () => {
      cleanupBleResources()
      if (deviceRef.current?.gatt?.connected) {
        deviceRef.current.gatt.disconnect()
      }
      deviceRef.current = null
    }
  }, [cleanupBleResources])

  const isBluetoothAvailable = typeof navigator !== 'undefined' && 'bluetooth' in navigator

  const connectDevice = async () => {
    const now = Date.now()
    if (connectLockRef.current || now - lastConnectAttemptRef.current < CONNECT_COOLDOWN_MS) {
      return
    }
    lastConnectAttemptRef.current = now
    connectLockRef.current = true

    setBleError(null)
    setConnecting(true)

    try {
      // Standard GATT Service UUIDs
      const HR_SERVICE = 0x180d // 'heart_rate'
      const BP_SERVICE = 0x1810 // 'blood_pressure'
      const PLX_SERVICE = 0x1822 // 'pulse_oximeter'

      const selectedDevice = await navigator.bluetooth.requestDevice({
        filters: [
          { services: [HR_SERVICE] },
          { services: [BP_SERVICE] },
          { services: [PLX_SERVICE] },
          { services: ['heart_rate'] },
          { services: ['blood_pressure'] },
          { services: ['pulse_oximeter'] },
        ],
        optionalServices: [HR_SERVICE, BP_SERVICE, PLX_SERVICE, 'heart_rate', 'blood_pressure', 'pulse_oximeter'],
      })

      deviceRef.current = selectedDevice
      setDevice(selectedDevice)
      selectedDevice.addEventListener('gattserverdisconnected', disconnectHandlerRef.current)

      const server = await selectedDevice.gatt.connect()
      setConnected(true)
      setConnecting(false)

      // Try discovering Heart Rate Service (0x180D)
      try {
        const hrService = await server.getPrimaryService(HR_SERVICE).catch(() => server.getPrimaryService('heart_rate'))
        if (hrService) {
          const hrChar = await hrService.getCharacteristic(0x2a37).catch(() => hrService.getCharacteristic('heart_rate_measurement'))
          await hrChar.startNotifications()
          const hrListener = (e) => {
            const val = e.target.value
            const flags = val.getUint8(0)
            const hr = (flags & 0x01) ? val.getUint16(1, true) : val.getUint8(1)
            setLastReading({ type: 'Heart Rate', value: `${hr} bpm`, vitals: { heart_rate: hr } })
            onApply({ heart_rate: hr }, `Bluetooth HR ${hr} bpm applied`)
          }
          hrChar.addEventListener('characteristicvaluechanged', hrListener)
          activeCharsRef.current.push({ char: hrChar, listener: hrListener })
        }
      } catch {
        // Not a pure HR device, try BP
      }

      // Try discovering Blood Pressure Service (0x1810) (BUG-48)
      try {
        const bpService = await server.getPrimaryService(BP_SERVICE).catch(() => server.getPrimaryService('blood_pressure'))
        if (bpService) {
          const bpChar = await bpService.getCharacteristic(0x2a35).catch(() => bpService.getCharacteristic('blood_pressure_measurement'))
          await bpChar.startNotifications()
          const bpListener = (e) => {
            const val = e.target.value
            const flags = val.getUint8(0)
            const isKpa = (flags & 0x01) === 1
            const sbpRaw = parseIeee11073Sfloat(val, 1)
            const dbpRaw = parseIeee11073Sfloat(val, 3)

            if (sbpRaw === null || dbpRaw === null) return

            const KPA_TO_MMHG = 7.50062
            const sbp = Math.round(isKpa ? sbpRaw * KPA_TO_MMHG : sbpRaw)
            const dbp = Math.round(isKpa ? dbpRaw * KPA_TO_MMHG : dbpRaw)

            if (sbp >= 30 && sbp <= 300 && dbp >= 10 && dbp <= 200) {
              setLastReading({
                type: 'Blood Pressure',
                value: `${sbp}/${dbp} mmHg`,
                vitals: { bp_systolic: sbp, bp_diastolic: dbp },
              })
              onApply({ bp_systolic: sbp, bp_diastolic: dbp }, `Bluetooth BP ${sbp}/${dbp} applied`)
            }
          }
          bpChar.addEventListener('characteristicvaluechanged', bpListener)
          activeCharsRef.current.push({ char: bpChar, listener: bpListener })
        }
      } catch {
        // Not BP
      }

      // Try discovering Pulse Oximeter Service (0x1822) (BUG-48)
      try {
        const plxService = await server.getPrimaryService(PLX_SERVICE).catch(() => server.getPrimaryService('pulse_oximeter'))
        if (plxService) {
          const plxChar = await plxService.getCharacteristic(0x2a5e)
            .catch(() => plxService.getCharacteristic(0x2a5f))
            .catch(() => plxService.getCharacteristic('plx_spot_check_measurement'))
            .catch(() => plxService.getCharacteristic('plx_continuous_measurement'))

          if (plxChar) {
            await plxChar.startNotifications()
            const plxListener = (e) => {
              const val = e.target.value
              const spo2Raw = parseIeee11073Sfloat(val, 1)
              const hrRaw = parseIeee11073Sfloat(val, 3)

              if (spo2Raw === null || hrRaw === null) return

              const spo2 = Math.round(spo2Raw)
              const hr = Math.round(hrRaw)

              if (spo2 >= 50 && spo2 <= 100 && hr >= 30 && hr <= 250) {
                setLastReading({
                  type: 'Pulse Oximeter',
                  value: `SpO2 ${spo2}%, HR ${hr} bpm`,
                  vitals: { spo2, heart_rate: hr },
                })
                onApply({ spo2, heart_rate: hr }, `Bluetooth SpO2 ${spo2}% applied`)
              }
            }
            plxChar.addEventListener('characteristicvaluechanged', plxListener)
            activeCharsRef.current.push({ char: plxChar, listener: plxListener })
          }
        }
      } catch {
        // Not PLX
      }
    } catch (err) {
      console.warn('[VitalNet] Bluetooth error', err)
      setConnecting(false)
      if (err.name !== 'NotFoundError') {
        setBleError(err.message || 'Bluetooth connection failed.')
      }
    } finally {
      connectLockRef.current = false
      setConnecting(false)
    }
  }

  return (
    <div className="space-y-3">
      <div className="bg-surface rounded-xl p-4 border border-surface3 flex flex-col items-center">
        {!isBluetoothAvailable ? (
          <div className="text-center p-3 text-text3 max-w-sm">
            <Bluetooth size={28} className="mx-auto text-text3/50 mb-2" />
            <p className="text-xs">
              Web Bluetooth is not supported on this browser. Use Chrome or Edge on Android or Desktop with Bluetooth enabled.
            </p>
          </div>
        ) : (
          <>
            <div className="flex items-center gap-2 mb-2">
              <Bluetooth
                size={24}
                className={connected ? 'text-forest animate-pulse' : 'text-text3'}
              />
              <span className="text-sm font-semibold text-text">
                {connected ? (device?.name || 'Medical Monitor Connected') : 'Pair Bluetooth Vital Monitor'}
              </span>
            </div>

            <p className="text-xs text-text3 text-center max-w-xs mb-3">
              Connect to BLE Blood Pressure Cuffs (0x1810), Pulse Oximeters (0x1822), or Heart Rate Monitors (0x180D).
            </p>

            {lastReading && (
              <div className="my-2 p-3 bg-forest/10 border border-forest/20 rounded-lg text-center animate-fade-in">
                <span className="text-[11px] font-medium text-forest uppercase tracking-wider block">
                  {lastReading.type} Received
                </span>
                <span className="text-lg font-bold font-mono text-text">
                  {lastReading.value}
                </span>
              </div>
            )}

            {bleError && (
              <p className="text-xs text-emergency text-center mb-2">{bleError}</p>
            )}

            <div className="flex gap-2">
              {!connected ? (
                <button
                  type="button"
                  onClick={connectDevice}
                  disabled={connecting}
                  className="px-4 py-2 bg-forest text-white text-xs font-semibold rounded-lg hover:bg-forest/90 disabled:opacity-40 cursor-pointer shadow-btn transition-all"
                >
                  {connecting ? 'Searching Devices…' : 'Pair & Connect BLE'}
                </button>
              ) : (
                <button
                  type="button"
                  onClick={disconnectDevice}
                  className="px-4 py-2 bg-surface2 text-text3 text-xs font-semibold rounded-lg hover:bg-surface3 cursor-pointer border border-surface3 transition-all"
                >
                  Disconnect
                </button>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
