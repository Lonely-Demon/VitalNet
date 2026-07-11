// frontend/src/components/ProtocolAssistant.jsx
//
// Protocol/guideline lookup assistant (docs/DECISIONS.md §27). Never asks
// about a specific patient — the backend LLM refuses those questions and
// points back to case submission. Grounded answers show immediately;
// ungrounded ones are queued for a supervisor/doctor/admin to curate, and
// curated answers join a shared, growing facility FAQ.
import { useState, useEffect, useCallback } from 'react'
import { askProtocolQuestion, listProtocolQuestions, curateProtocolAnswer } from '../lib/api'
import { useTranslation } from 'react-i18next'

const LANGUAGES = [
  { code: 'en', label: 'English' },
  { code: 'hi', label: 'Hindi' },
  { code: 'ta', label: 'Tamil' },
]

function QuestionCard({ q, canCurate, onCurated }) {
  const [answerDraft, setAnswerDraft] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  const finalAnswer = q.status === 'curated' ? q.curator_answer_text : q.llm_answer_text

  async function handleCurate() {
    if (!answerDraft.trim()) return
    setSubmitting(true)
    setError(null)
    try {
      const updated = await curateProtocolAnswer(q.id, answerDraft.trim())
      onCurated(updated)
    } catch (e) {
      setError(e.message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="rounded-lg border border-leaf/40 bg-surface p-4 shadow-card">
      <p className="text-sm font-medium text-text">{q.question_text}</p>
      {finalAnswer && (
        <p className="mt-2 text-sm text-text2">
          {finalAnswer}
          {q.status === 'curated' && (
            <span className="ml-2 text-xs font-mono text-routine">✓ curated</span>
          )}
        </p>
      )}
      {q.status === 'pending_curation' && (
        <>
          <p className="mt-2 text-xs text-urgent font-mono">Awaiting a curated answer</p>
          {canCurate && (
            <div className="mt-3 space-y-2">
              <textarea
                value={answerDraft}
                onChange={(e) => setAnswerDraft(e.target.value)}
                placeholder="Write the answer for the shared facility FAQ..."
                maxLength={2000}
                rows={3}
                className="w-full rounded-lg border border-leaf/40 bg-surface2 px-3 py-2 text-sm text-text placeholder:text-text3"
              />
              {error && <p className="text-xs text-emergency">{error}</p>}
              <button
                onClick={handleCurate}
                disabled={submitting || !answerDraft.trim()}
                className="rounded-pill bg-forest px-3 py-1.5 text-xs font-medium text-white disabled:opacity-50"
              >
                {submitting ? 'Saving…' : 'Save answer'}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  )
}

export default function ProtocolAssistant({ canCurate = false }) {
  const { i18n } = useTranslation()
  const [questions, setQuestions] = useState([])
  const [loading, setLoading] = useState(true)
  const [listError, setListError] = useState(null)

  const [questionText, setQuestionText] = useState('')
  const [language, setLanguage] = useState(LANGUAGES.some(l => l.code === i18n.language) ? i18n.language : 'en')
  const [asking, setAsking] = useState(false)
  const [askError, setAskError] = useState(null)

  const fetchQuestions = useCallback(async () => {
    setLoading(true)
    setListError(null)
    try {
      const data = await listProtocolQuestions()
      setQuestions(data.questions)
    } catch (e) {
      setListError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchQuestions()
  }, [fetchQuestions])

  async function handleAsk(e) {
    e.preventDefault()
    if (!questionText.trim()) return
    setAsking(true)
    setAskError(null)
    try {
      const created = await askProtocolQuestion({ questionText: questionText.trim(), language })
      setQuestions((prev) => [created, ...prev])
      setQuestionText('')
    } catch (e) {
      setAskError(e.message)
    } finally {
      setAsking(false)
    }
  }

  function handleCurated(updated) {
    setQuestions((prev) => prev.map((q) => (q.id === updated.id ? updated : q)))
  }

  const pending = questions.filter((q) => q.status === 'pending_curation')
  const answered = questions.filter((q) => q.status !== 'pending_curation')

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-sm font-mono font-semibold uppercase tracking-wide text-text3">
          Protocol Assistant
        </h2>
        <p className="mt-1 text-xs text-text3">
          Ask a general protocol or guideline question (ANC schedule, immunisation
          schedule, danger signs, referral criteria). This assistant never assesses a
          specific patient — submit a case for that instead.
        </p>
      </div>

      <form onSubmit={handleAsk} className="space-y-2">
        <textarea
          value={questionText}
          onChange={(e) => setQuestionText(e.target.value)}
          placeholder="e.g. When is the second ANC visit due?"
          maxLength={500}
          rows={2}
          className="w-full rounded-lg border border-leaf/40 bg-surface px-3 py-2 text-sm text-text placeholder:text-text3"
        />
        <div className="flex items-center gap-2">
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            className="rounded-pill border border-leaf/40 bg-surface2 px-2 py-1 text-xs font-mono text-text2"
          >
            {LANGUAGES.map((l) => (
              <option key={l.code} value={l.code}>{l.label}</option>
            ))}
          </select>
          <button
            type="submit"
            disabled={asking || !questionText.trim()}
            className="rounded-pill bg-forest px-4 py-1.5 text-sm font-medium text-white disabled:opacity-50"
          >
            {asking ? 'Asking…' : 'Ask'}
          </button>
        </div>
        {askError && <p className="text-xs text-emergency">{askError}</p>}
      </form>

      {loading && <p className="text-sm text-text3 py-4 text-center">Loading…</p>}
      {listError && <p className="text-sm text-emergency">Failed to load questions: {listError}</p>}

      {!loading && !listError && (
        <div className="space-y-4">
          {canCurate && pending.length > 0 && (
            <div className="space-y-2">
              <p className="text-xs font-mono font-semibold uppercase tracking-wide text-urgent">
                Needs curation ({pending.length})
              </p>
              {pending.map((q) => (
                <QuestionCard key={q.id} q={q} canCurate={canCurate} onCurated={handleCurated} />
              ))}
            </div>
          )}

          <div className="space-y-2">
            <p className="text-xs font-mono font-semibold uppercase tracking-wide text-text3">
              Facility FAQ
            </p>
            {answered.length === 0 ? (
              <p className="text-sm text-text3">No answered questions yet.</p>
            ) : (
              answered.map((q) => (
                <QuestionCard key={q.id} q={q} canCurate={canCurate} onCurated={handleCurated} />
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
