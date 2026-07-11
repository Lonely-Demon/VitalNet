/**
 * voice.js — server-side transcription (Groq Whisper) API wrapper. See
 * useVoiceInput.js for why this exists alongside the browser's own
 * SpeechRecognition path.
 */
import { authHeaders } from '@/api/auth'

const BASE = import.meta.env.VITE_API_BASE_URL

export async function transcribeAudio(blob, language) {
  const headers = await authHeaders()
  delete headers['Content-Type']   // let fetch set the multipart boundary itself

  const formData = new FormData()
  formData.append('file', blob, 'clip.webm')

  const url = new URL(`${BASE}/api/voice/transcribe`)
  if (language) url.searchParams.set('language', language)

  const res = await fetch(url.toString(), { method: 'POST', headers, body: formData })
  if (!res.ok) throw new Error(await res.text())
  const data = await res.json()
  return data.transcript
}
