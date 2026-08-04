// frontend/src/hooks/useVoiceInput.js
// Voice-to-text for intake free-text fields (FEATURES_ROADMAP §2.2).
//
// Dual-path architecture:
//   1. Real-time browser SpeechRecognition (webkitSpeechRecognition) runs
//      immediately on record to transcribe speech live into input fields as the user speaks.
//   2. Server-side Groq Whisper (app/services/voice.py) records in parallel via
//      MediaRecorder and refines the transcript when stop() is called.
//
// If server Whisper is unconfigured or fails (e.g. invalid API key), the live
// browser transcript is preserved so no spoken data is lost.
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
  const hasBrowserTranscriptRef = useRef(false)

  const speechSupported = Boolean(getSpeechRecognitionCtor())
  const recorderSupported = Boolean(getMediaRecorderCtor() && navigator.mediaDevices?.getUserMedia)
  const supported = speechSupported || recorderSupported
  const online = typeof navigator === 'undefined' || navigator.onLine
  const available = supported && online

  const startBrowserRecognition = useCallback(() => {
    if (!speechSupported) return
    const SpeechRecognitionCtor = getSpeechRecognitionCtor()
    const recognition = new SpeechRecognitionCtor()
    recognition.lang = lang
    recognition.interimResults = true
    recognition.continuous = true
    recognition.maxAlternatives = 1

    recognition.onresult = (event) => {
      const transcript = Array.from(event.results)
        .map((r) => r[0].transcript)
        .join(' ')
        .trim()
      if (transcript) {
        hasBrowserTranscriptRef.current = true
        onResult?.(transcript)
      }
    }
    recognition.onerror = (event) => {
      if (event.error === 'not-allowed') setError('permissionDenied')
    }
    recognition.onend = () => {
      // recognition ended naturally
    }

    recognitionRef.current = recognition
    try {
      recognition.start()
    } catch {}
  }, [speechSupported, lang, onResult])

  const start = useCallback(async () => {
    setError(null)
    hasBrowserTranscriptRef.current = false

    if (!supported) {
      setError('unsupported')
      return
    }
    if (!online) {
      setError('offline')
      return
    }

    setListening(true)

    // 1. Start live browser recognition immediately for instant real-time transcription
    if (speechSupported) {
      startBrowserRecognition()
    }

    // 2. Also start MediaRecorder if supported for server Whisper refinement on stop
    if (recorderSupported) {
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
          if (blob.size > 0) {
            try {
              const serverTranscript = await transcribeAudio(blob, LANG_TO_ISO[lang])
              if (serverTranscript?.trim()) {
                onResult?.(serverTranscript.trim())
              }
            } catch (err) {
              console.warn('[VitalNet] Server transcription unavailable, preserving browser transcript:', err)
            }
          }
          setListening(false)
        }

        mediaRecorderRef.current = recorder
        recorder.start()
      } catch (err) {
        console.warn('[VitalNet] Mic stream access error:', err)
        if (!speechSupported) {
          setError(err.name === 'NotAllowedError' ? 'permissionDenied' : 'failed')
          setListening(false)
        }
      }
    }
  }, [supported, online, speechSupported, recorderSupported, lang, onResult, startBrowserRecognition])

  const stop = useCallback(() => {
    if (recognitionRef.current) {
      try {
        recognitionRef.current.stop()
      } catch {}
    }
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      try {
        mediaRecorderRef.current.stop()
      } catch {}
    } else {
      setListening(false)
    }
  }, [])

  return { start, stop, listening, error, supported, available }
}
