import { useCallback, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { useVoiceInput } from '../hooks/useVoiceInput'

export default function VoiceInputButton({ onTranscript, lang, value = '' }) {
  const { t } = useTranslation()
  const baseTextRef = useRef('')
  const containerRef = useRef(null)

  const handleResult = useCallback((sessionTranscript) => {
    const base = baseTextRef.current
    const updated = base
      ? `${base.trim()} ${sessionTranscript.trim()}`.trim()
      : sessionTranscript.trim()
    onTranscript?.(updated)
  }, [onTranscript])

  const { start, stop, listening, error, supported, available } = useVoiceInput({
    lang,
    onResult: handleResult,
    containerRef,
  })

  const handleStart = () => {
    baseTextRef.current = value || ''
    start()
  }

  if (!supported) return null

  return (
    <span className="inline-flex items-center gap-1.5" ref={containerRef}>
      <button
        type="button"
        onClick={listening ? stop : handleStart}
        disabled={!available}
        title={!available ? t('intakeForm.voice.offline') : t(listening ? 'intakeForm.voice.stop' : 'intakeForm.voice.start')}
        aria-label={t(listening ? 'intakeForm.voice.stop' : 'intakeForm.voice.start')}
        className={`shrink-0 w-8 h-8 flex items-center justify-center rounded-full text-sm transition-colors cursor-pointer
          ${listening ? 'bg-emergency text-white animate-pulse' : 'bg-surface2 text-text2 hover:bg-surface3'}
          disabled:opacity-40 disabled:cursor-not-allowed`}
      >
        🎤
      </button>
      {error && (
        <span className="text-xs text-emergency">{t(`intakeForm.voice.${error}`)}</span>
      )}
    </span>
  )
}
