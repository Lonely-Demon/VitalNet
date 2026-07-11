/**
 * protocol.js — Stateless API wrappers for the protocol/guideline lookup assistant.
 */
import { authHeaders } from '@/api/auth'
import { getWithRetry } from '@/api/retry'

const BASE = import.meta.env.VITE_API_BASE_URL

export async function askProtocolQuestion({ questionText, language = 'en' }) {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/protocol/ask`, {
    method: 'POST',
    headers,
    body: JSON.stringify({ question_text: questionText, language }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function listProtocolQuestions({ status } = {}) {
  const headers = await authHeaders()
  const url = new URL(`${BASE}/api/protocol/questions`)
  if (status) url.searchParams.set('status', status)
  const res = await getWithRetry(url.toString(), headers)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function curateProtocolAnswer(questionId, curatorAnswerText) {
  const headers = await authHeaders()
  const res = await fetch(`${BASE}/api/protocol/questions/${questionId}/curate`, {
    method: 'PATCH',
    headers,
    body: JSON.stringify({ curator_answer_text: curatorAnswerText }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
