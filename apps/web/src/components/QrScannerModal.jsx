import { useState, useEffect, useRef, useCallback } from 'react'
import { X, Camera, Zap, ZapOff, QrCode, AlertCircle } from 'lucide-react'
import { parseAbhaQr, parsePatientQrPayload, PATIENT_KEY_RE, normalizePatientKey } from '@vitalnet/clinical-core'

/**
 * QrScannerModal — ADR §49 Camera QR Scanner Modal
 * Scans ABDM ABHA QR codes and VitalNet patient key cards using browser-native
 * W3C BarcodeDetector API with graceful fallback.
 *
 * @param {Object} props
 * @param {boolean} props.isOpen - Whether the modal is visible
 * @param {Function} props.onClose - Callback to close modal
 * @param {Function} props.onDetected - Callback receiving parsed patient identity
 */
export default function QrScannerModal({ isOpen, onClose, onDetected }) {
  const [hasCamera, setHasCamera] = useState(true)
  const [cameraError, setCameraError] = useState(null)
  const [torchAvailable, setTorchAvailable] = useState(false)
  const [torchOn, setTorchOn] = useState(false)
  const [manualInput, setManualInput] = useState('')
  const [manualError, setManualError] = useState(null)
  const [isScanning, setIsScanning] = useState(false)

  const videoRef = useRef(null)
  const streamRef = useRef(null)
  const scanIntervalRef = useRef(null)

  const stopCamera = useCallback(() => {
    if (scanIntervalRef.current) {
      clearInterval(scanIntervalRef.current)
      scanIntervalRef.current = null
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop())
      streamRef.current = null
    }
    setTorchOn(false)
    setTorchAvailable(false)
    setIsScanning(false)
  }, [])

  const handleQrString = useCallback((rawText) => {
    if (!rawText || typeof rawText !== 'string') return false
    const trimmed = rawText.trim()
    if (!trimmed) return false

    // 1. Try parsing as official ABDM ABHA QR payload
    try {
      const abhaResult = parseAbhaQr ? parseAbhaQr(trimmed) : (parsePatientQrPayload ? parsePatientQrPayload(trimmed) : null)
      if (abhaResult && abhaResult.patientKey) {
        if (typeof navigator !== 'undefined' && navigator.vibrate) {
          navigator.vibrate(50)
        }
        stopCamera()
        onDetected({
          patientKey: abhaResult.patientKey,
          patientName: abhaResult.patientName || abhaResult.name || null,
          patientAge: abhaResult.patientAge || abhaResult.age || null,
          patientSex: abhaResult.patientSex || abhaResult.gender || null,
          source: 'abdm_abha',
          rawPayload: trimmed,
        })
        onClose()
        return true
      }
    } catch (err) {
      console.warn('[VitalNet] Error parsing as ABHA QR', err)
    }

    // 2. Try parsing as direct VitalNet XXXX-XXXX patient key
    const normalized = normalizePatientKey(trimmed)
    if (normalized && PATIENT_KEY_RE && PATIENT_KEY_RE.test(normalized)) {
      if (typeof navigator !== 'undefined' && navigator.vibrate) {
        navigator.vibrate(50)
      }
      stopCamera()
      onDetected({
        patientKey: normalized,
        source: 'vitalnet_card',
        rawPayload: trimmed,
      })
      onClose()
      return true
    }

    return false
  }, [onDetected, onClose, stopCamera])

  // Camera start / stop lifecycle
  useEffect(() => {
    if (!isOpen) {
      stopCamera()
      return
    }

    let isMounted = true

    async function startCamera() {
      setCameraError(null)
      setHasCamera(true)

      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        setHasCamera(false)
        setCameraError('Camera access is not supported by this browser.')
        return
      }

      try {
        const constraints = {
          video: {
            facingMode: { ideal: 'environment' },
            width: { ideal: 1280 },
            height: { ideal: 720 },
          },
          audio: false,
        }

        const stream = await navigator.mediaDevices.getUserMedia(constraints)
        if (!isMounted) {
          stream.getTracks().forEach((t) => t.stop())
          return
        }

        streamRef.current = stream
        if (videoRef.current) {
          videoRef.current.srcObject = stream
          await videoRef.current.play().catch(() => {})
        }

        // Check torch capability
        const track = stream.getVideoTracks()[0]
        if (track && typeof track.getCapabilities === 'function') {
          const caps = track.getCapabilities()
          if (caps && caps.torch) {
            setTorchAvailable(true)
          }
        }

        setIsScanning(true)

        // Setup BarcodeDetector scanner loop if available
        if ('BarcodeDetector' in window) {
          try {
            const barcodeDetector = new window.BarcodeDetector({ formats: ['qr_code'] })
            scanIntervalRef.current = setInterval(async () => {
              if (!videoRef.current || videoRef.current.readyState < 2) return
              try {
                const barcodes = await barcodeDetector.detect(videoRef.current)
                if (barcodes && barcodes.length > 0) {
                  const rawValue = barcodes[0].rawValue
                  if (rawValue) {
                    handleQrString(rawValue)
                  }
                }
              } catch {
                // Ignore transient frame detect errors
              }
            }, 250)
          } catch (err) {
            console.warn('[VitalNet] BarcodeDetector init failed, using manual fallback', err)
          }
        }
      } catch (err) {
        console.warn('[VitalNet] Camera access failed', err)
        setCameraError(
          err.name === 'NotAllowedError'
            ? 'Camera permission was denied. Please allow camera access or paste the QR code text below.'
            : 'Unable to access camera. Please enter or paste the code manually.'
        )
      }
    }

    startCamera()

    return () => {
      isMounted = false
      stopCamera()
    }
  }, [isOpen, handleQrString, stopCamera])

  const toggleTorch = async () => {
    if (!streamRef.current || !torchAvailable) return
    const track = streamRef.current.getVideoTracks()[0]
    if (!track) return

    try {
      const nextState = !torchOn
      await track.applyConstraints({
        advanced: [{ torch: nextState }],
      })
      setTorchOn(nextState)
    } catch (err) {
      console.warn('[VitalNet] Torch toggle failed', err)
    }
  }

  const handleManualSubmit = (e) => {
    e.preventDefault()
    setManualError(null)
    const success = handleQrString(manualInput)
    if (!success) {
      setManualError('Unrecognized QR data or invalid Patient Key. Please verify the code.')
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-sm animate-fade-in">
      <div className="relative w-full max-w-md bg-surface rounded-2xl shadow-2xl border border-leaf/40 overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-surface3 bg-surface2">
          <div className="flex items-center gap-2">
            <QrCode size={20} className="text-forest" />
            <h2 className="text-base font-bold font-display text-text">Scan Patient QR / ABHA</h2>
          </div>
          <button
            type="button"
            onClick={() => {
              stopCamera()
              onClose()
            }}
            aria-label="Close scanner"
            className="p-1 rounded-lg text-text3 hover:text-text hover:bg-surface3 transition-colors cursor-pointer"
          >
            <X size={20} />
          </button>
        </div>

        {/* Viewfinder area */}
        <div className="relative flex-1 bg-black min-h-[280px] max-h-[360px] flex items-center justify-center overflow-hidden">
          {cameraError ? (
            <div className="p-6 text-center text-text3 max-w-xs space-y-3">
              <AlertCircle size={36} className="mx-auto text-urgent" />
              <p className="text-xs text-text2 leading-relaxed">{cameraError}</p>
            </div>
          ) : (
            <>
              <video
                ref={videoRef}
                playsInline
                muted
                className="w-full h-full object-cover"
              />

              {/* Viewfinder targeting overlay */}
              <div className="absolute inset-0 pointer-events-none flex items-center justify-center">
                <div className="relative w-52 h-52 border-2 border-white/60 rounded-xl shadow-[0_0_0_9999px_rgba(0,0,0,0.5)]">
                  {/* Corner brackets */}
                  <div className="absolute -top-1 -left-1 w-6 h-6 border-t-4 border-l-4 border-forest rounded-tl-lg" />
                  <div className="absolute -top-1 -right-1 w-6 h-6 border-t-4 border-r-4 border-forest rounded-tr-lg" />
                  <div className="absolute -bottom-1 -left-1 w-6 h-6 border-b-4 border-l-4 border-forest rounded-bl-lg" />
                  <div className="absolute -bottom-1 -right-1 w-6 h-6 border-b-4 border-r-4 border-forest rounded-br-lg" />

                  {/* Pulsing scan laser */}
                  {isScanning && (
                    <div className="absolute inset-x-2 h-0.5 bg-forest shadow-[0_0_8px_#2d6a4f] top-1/2 -translate-y-1/2 animate-pulse" />
                  )}
                </div>
              </div>

              {/* Viewfinder controls */}
              <div className="absolute bottom-3 inset-x-0 flex justify-center gap-3 pointer-events-auto">
                {torchAvailable && (
                  <button
                    type="button"
                    onClick={toggleTorch}
                    className={`p-2.5 rounded-full backdrop-blur-md transition-all cursor-pointer ${
                      torchOn
                        ? 'bg-forest text-white shadow-btn'
                        : 'bg-black/50 text-white/80 hover:bg-black/70'
                    }`}
                    title={torchOn ? 'Turn Flash Off' : 'Turn Flash On'}
                  >
                    {torchOn ? <Zap size={18} /> : <ZapOff size={18} />}
                  </button>
                )}
              </div>
            </>
          )}
        </div>

        {/* Footer / Manual fallback */}
        <div className="p-4 bg-surface2 border-t border-surface3 space-y-3">
          <p className="text-xs text-text3 text-center">
            Align camera with ABDM ABHA QR card or VitalNet patient slip.
          </p>

          <form onSubmit={handleManualSubmit} className="space-y-2">
            <div className="flex gap-2">
              <input
                type="text"
                value={manualInput}
                onChange={(e) => {
                  setManualInput(e.target.value)
                  setManualError(null)
                }}
                placeholder="Or paste QR payload / Patient Key"
                className="flex-1 bg-surface border border-surface3 rounded-lg px-3 py-2 text-xs text-text focus:outline-none focus:ring-1 focus:ring-forest font-mono"
              />
              <button
                type="submit"
                disabled={!manualInput.trim()}
                className="px-4 py-2 bg-forest text-white text-xs font-semibold rounded-lg hover:bg-forest/90 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
              >
                Apply
              </button>
            </div>
            {manualError && (
              <p className="text-[11px] text-emergency font-medium">{manualError}</p>
            )}
          </form>
        </div>
      </div>
    </div>
  )
}
