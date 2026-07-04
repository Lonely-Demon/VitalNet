// frontend/src/hooks/useVoiceInput.js
// Browser-native voice-to-text (FEATURES_ROADMAP §2.2, ship-first path).
// Wraps the Web Speech API (webkitSpeechRecognition on Chrome/Android
// WebView — what most ASHA-issued tablets run). Chrome's SpeechRecognition
// calls a Google speech API over the network and silently fails offline, so
// availability is gated on navigator.onLine in addition to feature support.
import { useCallback, useRef, useState } from 'react'

function getSpeechRecognitionCtor() {
  if (typeof window === 'undefined') return null
  return window.SpeechRecognition || window.webkitSpeechRecognition || null
}

export function useVoiceInput({ lang = 'en-US', onResult } = {}) {
  const [listening, setListening] = useState(false)
  const [error, setError] = useState(null)
  const recognitionRef = useRef(null)

  const supported = Boolean(getSpeechRecognitionCtor())
  const online = typeof navigator === 'undefined' || navigator.onLine
  const available = supported && online

  const start = useCallback(() => {
    setError(null)
    if (!supported) {
      setError('unsupported')
      return
    }
    if (!online) {
      setError('offline')
      return
    }

    const SpeechRecognitionCtor = getSpeechRecognitionCtor()
    const recognition = new SpeechRecognitionCtor()
    recognition.lang = lang
    recognition.interimResults = false
    recognition.maxAlternatives = 1

    recognition.onresult = (event) => {
      const transcript = Array.from(event.results)
        .map((r) => r[0].transcript)
        .join(' ')
        .trim()
      if (transcript) onResult?.(transcript)
    }
    recognition.onerror = (event) => {
      setError(event.error === 'not-allowed' ? 'permissionDenied' : 'failed')
    }
    recognition.onend = () => setListening(false)

    recognitionRef.current = recognition
    setListening(true)
    recognition.start()
  }, [supported, online, lang, onResult])

  const stop = useCallback(() => {
    recognitionRef.current?.stop()
    setListening(false)
  }, [])

  return { start, stop, listening, error, supported, available }
}
