import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { v4 as uuidv4 } from 'uuid'
import { submitCase } from '../lib/api'
import { useToast } from '../components/ToastProvider'
import { useAuth } from '../store/authStore'
import { useLocalTriage } from '../hooks/useLocalTriage'
import { useDraftSave } from '../hooks/useDraftSave'
import { validateForm } from '../utils/validation'
import VoiceInputButton from '../components/VoiceInputButton'
import { EmergencySmsAlert } from '../components/EmergencySmsAlert'

// Stable English identifiers — these are the actual values submitted to the
// API (chief_complaint is a free-text-ish field, not a coded enum server-
// side). Only the DISPLAYED label is translated (via the *_LABEL_KEYS maps
// below); selecting a different language never changes what gets submitted
// (FEATURES_ROADMAP §2.1 acceptance check).
const COMPLAINT_IDS = [
  "Chest pain / tightness",
  "Breathlessness / difficulty breathing",
  "Fever",
  "Abdominal pain",
  "Headache / dizziness",
  "Weakness / fatigue",
  "Altered consciousness / confusion",
  "Seizure",
  "Severe bleeding",
  "Nausea / vomiting",
  "Baby / child unwell",
  "Pregnancy complication",
  "Injury / trauma",
  "Other",
]

const COMPLAINT_LABEL_KEYS = {
  "Chest pain / tightness": "chestPain",
  "Breathlessness / difficulty breathing": "breathlessness",
  "Fever": "fever",
  "Abdominal pain": "abdominalPain",
  "Headache / dizziness": "headacheDizziness",
  "Weakness / fatigue": "weaknessFatigue",
  "Altered consciousness / confusion": "alteredConsciousness",
  "Seizure": "seizure",
  "Severe bleeding": "severeBleeding",
  "Nausea / vomiting": "nauseaVomiting",
  "Baby / child unwell": "babyChildUnwell",
  "Pregnancy complication": "pregnancyComplication",
  "Injury / trauma": "injuryTrauma",
  "Other": "other",
}

const DURATION_IDS = [
  "Less than 1 hour",
  "1–6 hours",
  "6–24 hours",
  "1–3 days",
  "More than 3 days",
]

const DURATION_LABEL_KEYS = {
  "Less than 1 hour": "lessThan1h",
  "1–6 hours": "oneToSixH",
  "6–24 hours": "sixToTwentyFourH",
  "1–3 days": "oneToThreeDays",
  "More than 3 days": "moreThanThreeDays",
}

// Symptom ids are both the stable wire value (sent as `symptoms: [ids...]`)
// AND the i18n key under intakeForm.symptoms.* — no separate label map needed.
const SYMPTOM_IDS = [
  "chest_pain",
  "breathlessness",
  "high_fever",
  "altered_consciousness",
  "seizure",
  "severe_bleeding",
  "severe_abdominal_pain",
  "persistent_vomiting",
  "severe_headache",
  "weakness_one_side",
  "difficulty_speaking",
  "swelling_face_throat",
]

const SEX_OPTIONS = ["male", "female", "other"]

const SPEECH_LANG_MAP = { en: "en-US", hi: "hi-IN", ta: "ta-IN" }

const BADGE_COLORS = {
  EMERGENCY: "bg-emergency/10 text-emergency border border-emergency/30",
  URGENT: "bg-urgent/10 text-urgent border border-urgent/30",
  ROUTINE: "bg-routine/10 text-routine border border-routine/30",
}

const emptyForm = {
  patient_name: "",
  patient_age: "",
  patient_sex: "",
  chief_complaint: "",
  custom_complaint: "",
  complaint_duration: "",
  location: "",
  bp_systolic: "",
  bp_diastolic: "",
  spo2: "",
  heart_rate: "",
  temperature: "",
  symptoms: [],
  observations: "",
  known_conditions: "",
  current_medications: "",
  human_review_requested: false,
  human_review_reason: "",
  consent_captured: false,
}

export default function IntakeForm() {
  const { t, i18n } = useTranslation()
  const speechLang = SPEECH_LANG_MAP[i18n.language] || "en-US"

  const [clientId] = useState(() => uuidv4())
  const [form, setForm] = useState(emptyForm)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [fieldErrors, setFieldErrors] = useState({})
  const [localResult, setLocalResult] = useState(null)

  const { profile } = useAuth()
  const { showToast } = useToast()
  const { classify } = useLocalTriage()

  // Tie draft strictly to the authenticated worker so tab evictions safely restore
  const { loadDraft, saveDraft, clearDraft } = useDraftSave(profile?.id || 'anonymous')

  // Load draft on mount
  useEffect(() => {
    let mounted = true
    loadDraft().then(draft => {
      if (mounted && draft) {
        setForm(draft)
        showToast('Restored unsaved draft', 'info')
      }
    }).catch(console.error)
    return () => { mounted = false }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Auto-save draft on form change (debounced 1s)
  useEffect(() => {
    if (form === emptyForm) return
    const timer = setTimeout(() => {
      saveDraft(form).catch(console.error)
    }, 1000)
    return () => clearTimeout(timer)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [form])

  const handleChange = (e) => {
    const { name, value } = e.target
    setForm(prev => {
      const updated = { ...prev, [name]: value }
      // Clear custom complaint when changing away from "Other"
      if (name === 'chief_complaint' && value !== 'Other') {
        updated.custom_complaint = ''
      }
      return updated
    })
  }

  const handleSymptom = (symptomId) => {
    setForm(prev => ({
      ...prev,
      symptoms: prev.symptoms.includes(symptomId)
        ? prev.symptoms.filter(s => s !== symptomId)
        : [...prev.symptoms, symptomId]
    }))
  }

  // Appends a voice transcript to the named field rather than overwriting it
  // — the transcribed text always stays visible in the field for the worker
  // to review/edit before submit (never auto-submitted).
  const appendVoiceTranscript = (field) => (transcript) => {
    setForm(prev => ({
      ...prev,
      [field]: prev[field] ? `${prev[field]} ${transcript}` : transcript,
    }))
  }

  const handleSubmit = async (e) => {
    if (e?.preventDefault) e.preventDefault()
    setError(null)
    setFieldErrors({})
    setLocalResult(null)
    setLoading(true)

    if (!form.consent_captured) {
      setError(t('intakeForm.errors.consentRequired'))
      setFieldErrors({ consent_captured: t('intakeForm.errors.consentRequiredShort') })
      setLoading(false)
      return
    }

    const payload = {
      ...form,
      chief_complaint: form.chief_complaint === "Other" ? form.custom_complaint?.trim() || "" : form.chief_complaint,
      patient_name: form.patient_name?.trim() || "",
      patient_age: form.patient_age ? parseInt(form.patient_age) : undefined,
      bp_systolic: form.bp_systolic ? parseInt(form.bp_systolic) : null,
      bp_diastolic: form.bp_diastolic ? parseInt(form.bp_diastolic) : null,
      spo2: form.spo2 ? parseInt(form.spo2) : null,
      heart_rate: form.heart_rate ? parseInt(form.heart_rate) : null,
      temperature: form.temperature ? parseFloat(form.temperature) : null,
      human_review_requested: Boolean(form.human_review_requested),
      human_review_reason: form.human_review_reason?.trim() || null,
      consent_captured_at: new Date().toISOString(),
    }

    // Zod clinical boundary validation
    const validation = validateForm(payload)
    if (!validation.success) {
      setError(t('intakeForm.errors.validationFailed'))
      setFieldErrors(validation.errors)
      setLoading(false)
      return
    }

    // Run local offline triage immediately — before any network call
    const local = await classify(payload)
    if (local) {
      setLocalResult(local)
    }

    try {
      const data = await submitCase(payload)

      // Clear draft since it is successfully saved or queued
      await clearDraft().catch(console.error)

      if (data.queued) {
        setResult({ ...data, localTriage: local })
        showToast('Saved offline — will sync when connected', 'warning')
      } else {
        setResult(data)
        setLocalResult(null)
        showToast('Case submitted successfully', 'success')
      }
      setForm(emptyForm)
    } catch (err) {
      // If offline or network error — local result stays displayed
      // The Phase 8 queue handles the actual sync
      setError(err.message?.includes('queue is full')
        ? t('intakeForm.errors.queueFull')
        : (err.message || t('intakeForm.errors.submissionFailed')))
    } finally {
      setLoading(false)
    }
  }

  if (result) {
    const isQueued = result.queued
    const offlineTriage = result.localTriage
    return (
      <div className="max-w-lg mx-auto p-4 mt-8 animate-fade-up">
        <div className="bg-surface rounded-xl shadow-card border border-leaf/40 p-8 text-center hover:shadow-card-hover transition-shadow duration-300">
          {isQueued ? (
            <>
              {offlineTriage && (
                <div className="mb-4">
                  <span className={`inline-block px-5 py-2 rounded-pill font-bold text-lg tracking-wide font-mono ${BADGE_COLORS[offlineTriage.triageLevel]}`}>
                    {offlineTriage.triageLevel}
                  </span>
                  {offlineTriage.lowConfidence && (
                    <p className="text-xs text-urgent mt-2 font-mono">{t('intakeForm.result.lowConfidenceShort')}</p>
                  )}
                </div>
              )}
              {offlineTriage?.triageLevel === 'EMERGENCY' && <EmergencySmsAlert />}
              <div className="mb-6">
                <span className="inline-block px-5 py-2 rounded-pill font-bold text-lg tracking-wide shadow-sm bg-sand text-urgent border border-urgent/20 font-mono">
                  {t('intakeForm.result.savedOfflineBadge')}
                </span>
              </div>
              <h2 className="text-text text-xl font-bold tracking-tight mb-2 font-display italic">{t('intakeForm.result.savedLocallyTitle')}</h2>
              <p className="text-text2 leading-relaxed mb-8">
                {offlineTriage
                  ? t('intakeForm.result.savedLocallyWithTriage')
                  : t('intakeForm.result.savedLocallyNoTriage')}
              </p>
            </>
          ) : (
            <>
              <div className="mb-6">
                <span className={`inline-block px-5 py-2 rounded-pill font-bold text-lg tracking-wide font-mono ${BADGE_COLORS[result.triage_level]}`}>
                  {result.triage_level}
                </span>
              </div>
              <h2 className="text-text text-xl font-bold tracking-tight mb-2 font-display italic">{t('intakeForm.result.successTitle')}</h2>
              <p className="text-text2 leading-relaxed mb-8">{result.risk_driver}</p>
            </>
          )}
          <button
            onClick={() => setResult(null)}
            className="bg-forest text-white px-8 py-3 rounded-pill font-medium cursor-pointer shadow-btn hover:shadow-card-hover transition-all active:scale-[0.98]"
          >
            {t('intakeForm.actions.submitAnother')}
          </button>
        </div>
      </div>
    )
  }

  return (
    <form onSubmit={handleSubmit} className="max-w-xl mx-auto p-6 md:p-8 mt-6 mb-20 bg-surface shadow-card border border-leaf/40 rounded-xl hover:shadow-card-hover transition-shadow duration-300 relative pb-32">
      <h1 className="text-2xl font-display italic text-forest tracking-tight mb-8 text-center">{t('intakeForm.title')}</h1>

      {error && (
        <div role="alert" aria-live="assertive" className="bg-emergency/10 border border-emergency/30 text-emergency px-4 py-3 rounded-md mb-4 text-sm">
          {error}
        </div>
      )}

      {/* Patient Location */}
      <Section title={t('intakeForm.sections.location')}>
        <Field label={t('intakeForm.fields.location')} error={fieldErrors.location} id="location">
          <input id="location" name="location" value={form.location} onChange={handleChange} required
            aria-describedby={fieldErrors.location ? "location-error" : undefined}
            placeholder={t('intakeForm.placeholders.location')} maxLength={200} className={`${inputClass} ${fieldErrors.location ? 'border-emergency/50 ring-1 ring-emergency/50' : ''}`} />
        </Field>
      </Section>

      {/* Patient */}
      <Section title={t('intakeForm.sections.patientDetails')}>
        <Field label={t('intakeForm.fields.patientName')} error={fieldErrors.patient_name} id="patient_name">
          <input id="patient_name" name="patient_name" value={form.patient_name} onChange={handleChange}
            aria-describedby={fieldErrors.patient_name ? "patient_name-error" : undefined}
            placeholder={t('intakeForm.placeholders.patientName')} className={`${inputClass} ${fieldErrors.patient_name ? 'border-emergency/50 ring-1 ring-emergency/50' : ''}`} maxLength={100} />
        </Field>
        <Field label={t('intakeForm.fields.patientAge')} error={fieldErrors.patient_age} id="patient_age">
          <input id="patient_age" name="patient_age" type="number" value={form.patient_age}
            onChange={handleChange} aria-describedby={fieldErrors.patient_age ? "patient_age-error" : undefined}
            placeholder={t('intakeForm.placeholders.patientAge')} className={`${inputClass} ${fieldErrors.patient_age ? 'border-emergency/50 ring-1 ring-emergency/50' : ''}`} />
        </Field>
        <Field label={t('intakeForm.fields.patientSex')} error={fieldErrors.patient_sex} id="patient_sex">
          <fieldset className="mt-1">
            <legend className="sr-only">{t('intakeForm.fields.patientSex')}</legend>
            <div className="flex gap-4" aria-describedby={fieldErrors.patient_sex ? "patient_sex-error" : undefined}>
              {SEX_OPTIONS.map(s => (
                <label key={s} className="flex items-center gap-2 cursor-pointer group p-2 min-w-[44px] min-h-[44px]">
                  <input type="radio" name="patient_sex" value={s}
                    checked={form.patient_sex === s} onChange={handleChange}
                    className="accent-forest w-5 h-5" />
                  <span className="capitalize text-sm text-text2 group-hover:text-forest transition-colors">{t(`intakeForm.sexOptions.${s}`)}</span>
                </label>
              ))}
            </div>
          </fieldset>
        </Field>
      </Section>

      {/* Complaint */}
      <Section title={t('intakeForm.sections.chiefComplaint')}>
        <Field label={t('intakeForm.fields.chiefComplaint')} error={fieldErrors.chief_complaint} id="chief_complaint">
          <select id="chief_complaint" name="chief_complaint" value={form.chief_complaint}
            onChange={handleChange} aria-describedby={fieldErrors.chief_complaint ? "chief_complaint-error" : undefined}
            className={`${inputClass} ${fieldErrors.chief_complaint ? 'border-emergency/50 ring-1 ring-emergency/50' : ''}`}>
            <option value="">{t('intakeForm.placeholders.selectComplaint')}</option>
            {COMPLAINT_IDS.map(id => (
              <option key={id} value={id}>{t(`intakeForm.complaints.${COMPLAINT_LABEL_KEYS[id]}`)}</option>
            ))}
          </select>
        </Field>
        {form.chief_complaint === "Other" && (
          <Field label={t('intakeForm.fields.customComplaint')} error={fieldErrors.chief_complaint} id="custom_complaint">
            <input
              id="custom_complaint"
              name="custom_complaint"
              value={form.custom_complaint}
              onChange={handleChange}
              aria-describedby={fieldErrors.chief_complaint ? "custom_complaint-error" : undefined}
              placeholder={t('intakeForm.placeholders.customComplaint')}
              className={inputClass}
              maxLength={200}
            />
          </Field>
        )}
        <Field label={t('intakeForm.fields.duration')} error={fieldErrors.complaint_duration} id="complaint_duration">
          <select id="complaint_duration" name="complaint_duration" value={form.complaint_duration}
            onChange={handleChange} aria-describedby={fieldErrors.complaint_duration ? "complaint_duration-error" : undefined}
            className={`${inputClass} ${fieldErrors.complaint_duration ? 'border-emergency/50 ring-1 ring-emergency/50' : ''}`}>
            <option value="">{t('intakeForm.placeholders.selectDuration')}</option>
            {DURATION_IDS.map(id => (
              <option key={id} value={id}>{t(`intakeForm.durations.${DURATION_LABEL_KEYS[id]}`)}</option>
            ))}
          </select>
        </Field>
      </Section>

      {/* Vitals */}
      <Section title={t('intakeForm.sections.vitals')}>
        <div className="grid grid-cols-2 gap-3">
          <Field label={t('intakeForm.fields.bpSystolic')} error={fieldErrors.bp_systolic} id="bp_systolic">
            <input id="bp_systolic" name="bp_systolic" type="number" value={form.bp_systolic}
              onChange={handleChange} aria-describedby={fieldErrors.bp_systolic ? "bp_systolic-error" : undefined}
              placeholder={t('intakeForm.placeholders.bpSystolic')} className={`${inputClass} ${fieldErrors.bp_systolic ? 'border-emergency/50 ring-1 ring-emergency/50' : ''}`} />
          </Field>
          <Field label={t('intakeForm.fields.bpDiastolic')} error={fieldErrors.bp_diastolic} id="bp_diastolic">
            <input id="bp_diastolic" name="bp_diastolic" type="number" value={form.bp_diastolic}
              onChange={handleChange} aria-describedby={fieldErrors.bp_diastolic ? "bp_diastolic-error" : undefined}
              placeholder={t('intakeForm.placeholders.bpDiastolic')} className={`${inputClass} ${fieldErrors.bp_diastolic ? 'border-emergency/50 ring-1 ring-emergency/50' : ''}`} />
          </Field>
          <Field label={t('intakeForm.fields.spo2')} error={fieldErrors.spo2} id="spo2">
            <input id="spo2" name="spo2" type="number" value={form.spo2}
              onChange={handleChange} aria-describedby={fieldErrors.spo2 ? "spo2-error" : undefined}
              placeholder={t('intakeForm.placeholders.spo2')} className={`${inputClass} ${fieldErrors.spo2 ? 'border-emergency/50 ring-1 ring-emergency/50' : ''}`} />
          </Field>
          <Field label={t('intakeForm.fields.heartRate')} error={fieldErrors.heart_rate} id="heart_rate">
            <input id="heart_rate" name="heart_rate" type="number" value={form.heart_rate}
              onChange={handleChange} aria-describedby={fieldErrors.heart_rate ? "heart_rate-error" : undefined}
              placeholder={t('intakeForm.placeholders.heartRate')} className={`${inputClass} ${fieldErrors.heart_rate ? 'border-emergency/50 ring-1 ring-emergency/50' : ''}`} />
          </Field>
          <Field label={t('intakeForm.fields.temperature')} error={fieldErrors.temperature} id="temperature">
            <input id="temperature" name="temperature" type="number" step="0.1" value={form.temperature}
              onChange={handleChange} aria-describedby={fieldErrors.temperature ? "temperature-error" : undefined}
              placeholder={t('intakeForm.placeholders.temperature')} className={`${inputClass} ${fieldErrors.temperature ? 'border-emergency/50 ring-1 ring-emergency/50' : ''}`} />
          </Field>
        </div>
      </Section>

      {/* Symptoms */}
      <Section title={t('intakeForm.sections.symptoms')}>
        <div className="grid grid-cols-2 gap-3">
          {SYMPTOM_IDS.map((id, idx) => {
            const isSelected = form.symptoms.includes(id);
            return (
              <label
                key={id}
                style={{ animationDelay: `${idx * 40}ms` }}
                className={`flex items-center justify-center p-3 rounded-lg border text-sm transition-all duration-200 cursor-pointer animate-fade-up
                ${isSelected
                  ? 'bg-forest text-white border-forest shadow-btn font-medium tracking-tight'
                  : 'bg-surface2 border-surface3 text-text2 hover:border-sage hover:shadow-card'
                }`}
              >
                <input type="checkbox" checked={isSelected}
                  onChange={() => handleSymptom(id)}
                  className="sr-only" />
                <span className="text-center">{t(`intakeForm.symptoms.${id}`)}</span>
              </label>
            )
          })}
        </div>
      </Section>

      {/* Observations */}
      <Section title={t('intakeForm.sections.observations')}>
        <Field label={t('intakeForm.fields.observations')} id="observations">
          <div className="flex items-start gap-2">
            <textarea id="observations" name="observations" value={form.observations} onChange={handleChange}
              placeholder={t('intakeForm.placeholders.observations')}
              rows={3} className={`${inputClass} resize-none flex-1`} maxLength={500} />
            <VoiceInputButton lang={speechLang} onTranscript={appendVoiceTranscript('observations')} />
          </div>
        </Field>
        <Field label={t('intakeForm.fields.knownConditions')} id="known_conditions">
          <div className="flex items-center gap-2">
            <input id="known_conditions" name="known_conditions" value={form.known_conditions}
              onChange={handleChange} placeholder={t('intakeForm.placeholders.knownConditions')}
              maxLength={300} className={`${inputClass} flex-1`} />
            <VoiceInputButton lang={speechLang} onTranscript={appendVoiceTranscript('known_conditions')} />
          </div>
        </Field>
        <Field label={t('intakeForm.fields.currentMedications')} id="current_medications">
          <div className="flex items-center gap-2">
            <input id="current_medications" name="current_medications" value={form.current_medications}
              onChange={handleChange} placeholder={t('intakeForm.placeholders.currentMedications')}
              maxLength={300} className={`${inputClass} flex-1`} />
            <VoiceInputButton lang={speechLang} onTranscript={appendVoiceTranscript('current_medications')} />
          </div>
        </Field>
      </Section>

      {/* Patient Consent */}
      <Section title={t('intakeForm.sections.consent')}>
        <div className={`p-4 rounded-lg border ${fieldErrors.consent_captured ? 'border-emergency/50 bg-emergency/5' : 'border-surface3 bg-surface2'}`}>
          <label className="flex items-start gap-3 cursor-pointer">
            <input
              type="checkbox"
              name="consent_captured"
              checked={form.consent_captured}
              onChange={(e) => setForm(prev => ({ ...prev, consent_captured: e.target.checked }))}
              aria-describedby={fieldErrors.consent_captured ? "consent_captured-error" : undefined}
              className="mt-1 w-5 h-5 accent-forest rounded"
            />
            <span className="text-sm text-text2 leading-relaxed">
              <strong className="text-text">{t('intakeForm.consent.title')}</strong>
              <br />
              {t('intakeForm.consent.intro')}
              <ul className="mt-2 ml-4 list-disc space-y-1 text-text3">
                {t('intakeForm.consent.items', { returnObjects: true }).map((item, i) => (
                  <li key={i}>{item}</li>
                ))}
              </ul>
            </span>
          </label>
          {fieldErrors.consent_captured && (
            <p id="consent_captured-error" role="alert" className="text-emergency text-xs mt-2 font-medium">{fieldErrors.consent_captured}</p>
          )}
        </div>
      </Section>

      {/* Clinician Review Request */}
      <Section title={t('intakeForm.sections.clinicianReview')}>
        <div className="p-4 rounded-lg border border-leaf/40 bg-surface2">
          <label className="flex items-start gap-3 cursor-pointer">
            <input
              type="checkbox"
              name="human_review_requested"
              checked={form.human_review_requested}
              onChange={(e) => setForm(prev => ({ ...prev, human_review_requested: e.target.checked }))}
              className="mt-1 w-5 h-5 accent-forest rounded"
            />
            <span className="text-sm text-text2 leading-relaxed">
              <strong className="text-text">{t('intakeForm.review.title')}</strong>
              <br />
              {t('intakeForm.review.description')}
            </span>
          </label>
          {form.human_review_requested && (
            <textarea
              name="human_review_reason"
              value={form.human_review_reason}
              onChange={handleChange}
              placeholder={t('intakeForm.placeholders.reviewReason')}
              aria-label={t('intakeForm.placeholders.reviewReason')}
              rows={2}
              maxLength={500}
              className={`${inputClass} mt-3 resize-none`}
            />
          )}
        </div>
      </Section>

      {/* Submit */}
      <div className="fixed sm:absolute bottom-0 left-0 right-0 sm:left-auto sm:right-auto sm:w-full p-4 bg-surface sm:bg-transparent border-t border-surface3 sm:border-none shadow-[0_-4px_10px_rgba(0,0,0,0.1)] sm:shadow-none z-20">
        <button
          type="submit"
          disabled={loading}
          className="w-full bg-forest text-white py-4 rounded-pill font-bold text-lg shadow-btn hover:shadow-card-hover disabled:opacity-75 disabled:cursor-wait transition-all duration-200 active:scale-[0.98] cursor-pointer flex justify-center items-center min-h-[56px]"
        >
          {loading ? <span className="animate-pulse">{t('intakeForm.actions.analyzing')}</span> : t('intakeForm.actions.submit')}
        </button>
      </div>

      {/* Preliminary Triage Result Display */}
      {localResult && (
        <div className={`mt-4 rounded-lg border p-4 animate-fade-up ${
          localResult.triageLevel === 'EMERGENCY'
            ? 'border-emergency/30 bg-emergency/5'
            : localResult.triageLevel === 'URGENT'
            ? 'border-urgent/30 bg-urgent/5'
            : 'border-routine/30 bg-routine/5'
        }`}>
          <div className="flex items-center gap-3">
            <span className={`inline-flex items-center rounded-pill px-3 py-1 text-xs font-bold tracking-widest uppercase font-mono ${
              localResult.triageLevel === 'EMERGENCY'
                ? 'bg-emergency/10 text-emergency'
                : localResult.triageLevel === 'URGENT'
                ? 'bg-urgent/10 text-urgent'
                : 'bg-routine/10 text-routine'
            }`}>
              {localResult.triageLevel}
            </span>
            <span className="text-sm font-medium text-text2">
              {t('intakeForm.preliminary.label')}
            </span>
          </div>
          {localResult.lowConfidence && (
            <p className="mt-2 text-xs text-urgent font-medium">
              {t('intakeForm.preliminary.lowConfidence')}
            </p>
          )}
          <p className="mt-2 text-xs text-text3">
            {navigator.onLine
              ? t('intakeForm.preliminary.sendingOnline')
              : t('intakeForm.preliminary.sendingOffline')}
          </p>
        </div>
      )}
    </form>
  )
}

// Utility components
const inputClass = "w-full border border-surface3 rounded-md px-4 py-3 text-sm text-text bg-surface2 shadow-sm transition-all duration-200 outline-none focus:ring-2 focus:ring-leaf focus:border-sage hover:border-sage"

function Section({ title, children }) {
  return (
    <div className="mb-8">
      <h2 className="text-xs font-mono font-bold text-text3 uppercase tracking-widest mb-4 flex items-center gap-3">
        {title}
        <div className="h-px bg-leaf/60 flex-1"></div>
      </h2>
      <div className="space-y-4">{children}</div>
    </div>
  )
}

function Field({ label, error, id, children }) {
  return (
    <div>
      <label htmlFor={id} className="block text-sm font-medium text-text2 mb-2 ml-1">{label}</label>
      {children}
      {error && (
        <p id={id ? `${id}-error` : undefined} role="alert" className="text-emergency text-xs mt-1.5 ml-1 animate-fade-up font-medium">
          {error}
        </p>
      )}
    </div>
  )
}
