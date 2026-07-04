// frontend/src/hooks/useVoiceInput.js
// Voice-to-text for intake free-text fields (FEATURES_ROADMAP §2.2).
//
// Two transcription paths, in preference order:
//   1. Server-side Groq Whisper (app/services/voice.py) — records audio via
//      MediaRecorder and POSTs it to /api/voice/transcribe. This is the
//      accuracy layer: VitalNet's original design intent was that Indic
//      medical speech needs a real Whisper-class model, not the browser's
//      built-in recognizer (docs/DECISIONS.md §15).
//   2. Browser SpeechRecognition (webkitSpeechRecognition) — used only as a
//      fallback if MediaRecorder/mic access isn't available, or if the
//      server call itself fails (e.g. GROQ_API_KEY not configured, Groq
//      outage). Note this path ALSO calls out to a network speech service
//      (Chrome routes it through Google) — it is not a true offline path,
//      just a different online path with weaker accuracy on Indic/medical
//      speech, which is exactly why it's the fallback and not the primary.
// Both paths require connectivity, so availability is gated on
// navigator.onLine either way — there is no offline voice input.
import { useCallback, useRef, useState } from 'react'
import { transcribeAudio } from '../api/voice'

function getSpeechRecognitionCtor() {
  if (typeof window === 'undefined') return null
  return window.SpeechRecognition || window.webkitSpeechRecognition || null
}

function getMediaRecorderCtor() {
  return typeof window !== 'undefined' ? window.MediaRecorder : undefined
}

// intake i18n language codes (frontend/src/i18n.js) → Whisper ISO-639-1 codes.
const LANG_TO_ISO = { 'en-US': 'en', 'hi-IN': 'hi', 'ta-IN': 'ta' }

export function useVoiceInput({ lang = 'en-US', onResult } = {}) {
  const [listening, setListening] = useState(false)
  const [error, setError] = useState(null)
  const recognitionRef = useRef(null)
  const mediaRecorderRef = useRef(null)
  const chunksRef = useRef([])

  const speechSupported = Boolean(getSpeechRecognitionCtor())
  const recorderSupported = Boolean(getMediaRecorderCtor() && navigator.mediaDevices?.getUserMedia)
  const supported = speechSupported || recorderSupported
  const online = typeof navigator === 'undefined' || navigator.onLine
  const available = supported && online

  const startBrowserRecognition = useCallback(() => {
    if (!speechSupported) {
      setError('failed')
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
  }, [speechSupported, lang, onResult])

  const startServerRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const MediaRecorderCtor = getMediaRecorderCtor()
      const recorder = new MediaRecorderCtor(stream)
      chunksRef.current = []

      recorder.ondataavailable = (event) => {
        if (event.data.size > 0) chunksRef.current.push(event.data)
      }
      recorder.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop())
        const blob = new Blob(chunksRef.current, { type: recorder.mimeType || 'audio/webm' })
        try {
          const transcript = await transcribeAudio(blob, LANG_TO_ISO[lang])
          setListening(false)
          if (transcript) onResult?.(transcript)
        } catch (err) {
          console.warn('[VitalNet] Server transcription failed, falling back to browser STT:', err)
          if (speechSupported) {
            startBrowserRecognition()
          } else {
            setListening(false)
            setError('failed')
          }
        }
      }

      mediaRecorderRef.current = recorder
      recorder.start()
      setListening(true)
    } catch (err) {
      setError(err.name === 'NotAllowedError' ? 'permissionDenied' : 'failed')
    }
  }, [lang, onResult, speechSupported, startBrowserRecognition])

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
    if (recorderSupported) {
      startServerRecording()
    } else {
      startBrowserRecognition()
    }
  }, [supported, online, recorderSupported, startServerRecording, startBrowserRecognition])

  const stop = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop()
    }
    recognitionRef.current?.stop()
    setListening(false)
  }, [])

  return { start, stop, listening, error, supported, available }
}
