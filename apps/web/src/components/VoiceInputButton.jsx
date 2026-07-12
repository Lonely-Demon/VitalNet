// frontend/src/components/VoiceInputButton.jsx
// Mic button for a free-text field — always shows the transcript in the
// field for the worker to review/edit before submit (FEATURES_ROADMAP §2.2:
// never auto-submit voice input directly, given transcription error risk in
// a clinical context). Renders nothing on browsers without SpeechRecognition
// support (e.g. Firefox) rather than showing a dead button.
import { useTranslation } from 'react-i18next'
import { Mic } from 'lucide-react'
import { useVoiceInput } from '../hooks/useVoiceInput'

export default function VoiceInputButton({ onTranscript, lang }) {
  const { t } = useTranslation()
  const { start, stop, listening, error, supported, available } = useVoiceInput({
    lang,
    onResult: onTranscript,
  })

  if (!supported) return null

  return (
    <span className="inline-flex items-center gap-1.5">
      <button
        type="button"
        onClick={listening ? stop : start}
        disabled={!available}
        title={!available ? t('intakeForm.voice.offline') : t(listening ? 'intakeForm.voice.stop' : 'intakeForm.voice.start')}
        aria-label={t(listening ? 'intakeForm.voice.stop' : 'intakeForm.voice.start')}
        className={`shrink-0 w-8 h-8 flex items-center justify-center rounded-full text-sm transition-colors cursor-pointer
          ${listening ? 'bg-emergency text-white animate-pulse' : 'bg-surface2 text-text2 hover:bg-surface3'}
          disabled:opacity-40 disabled:cursor-not-allowed`}
      >
        <Mic size={15} aria-hidden="true" />
      </button>
      {error && (
        <span className="text-xs text-emergency">{t(`intakeForm.voice.${error}`)}</span>
      )}
    </span>
  )
}
