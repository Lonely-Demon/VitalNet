import { useState } from 'react'
import { submitCase } from '../lib/api'
import { useToast } from '../components/ToastProvider'
import { useLocalTriage } from '../hooks/useLocalTriage'

const COMPLAINTS = [
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

const DURATIONS = [
  "Less than 1 hour",
  "1–6 hours",
  "6–24 hours",
  "1–3 days",
  "More than 3 days",
]

const SYMPTOM_OPTIONS = [
  { id: "chest_pain", label: "Chest pain" },
  { id: "breathlessness", label: "Breathlessness" },
  { id: "high_fever", label: "High fever (>102°F)" },
  { id: "altered_consciousness", label: "Altered consciousness" },
  { id: "seizure", label: "Seizure" },
  { id: "severe_bleeding", label: "Severe bleeding" },
  { id: "severe_abdominal_pain", label: "Severe abdominal pain" },
  { id: "persistent_vomiting", label: "Persistent vomiting" },
  { id: "severe_headache", label: "Severe headache" },
  { id: "weakness_one_side", label: "Weakness on one side" },
  { id: "difficulty_speaking", label: "Difficulty speaking" },
  { id: "swelling_face_throat", label: "Swelling of face/throat" },
]

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
}

export default function IntakeForm() {
  const [form, setForm] = useState(emptyForm)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)
  const [localResult, setLocalResult] = useState(null)
  const { showToast } = useToast()
  const { classify } = useLocalTriage()

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

  const handleSubmit = async () => {
    setError(null)
    setLocalResult(null)

    // Required field validation
    if (!form.patient_name?.trim() || !form.patient_age || !form.patient_sex ||
        !form.chief_complaint || !form.complaint_duration || !form.location) {
      setError("Please fill all required fields (marked with *)")
      return
    }

    // Additional validation for "Other" complaint
    if (form.chief_complaint === "Other" && !form.custom_complaint?.trim()) {
      setError("Please specify the complaint when selecting 'Other'")
      return
    }

    // Vitals range validation (matches backend Pydantic constraints)
    const vitalsErrors = []
    if (form.bp_systolic && (form.bp_systolic < 50 || form.bp_systolic > 300)) {
      vitalsErrors.push("BP Systolic must be between 50 and 300 mmHg")
    }
    if (form.bp_diastolic && (form.bp_diastolic < 20 || form.bp_diastolic > 200)) {
      vitalsErrors.push("BP Diastolic must be between 20 and 200 mmHg")
    }
    if (form.spo2 && (form.spo2 < 50 || form.spo2 > 100)) {
      vitalsErrors.push("SpO2 must be between 50% and 100%")
    }
    if (form.heart_rate && (form.heart_rate < 20 || form.heart_rate > 250)) {
      vitalsErrors.push("Heart rate must be between 20 and 250 bpm")
    }
    if (form.temperature && (form.temperature < 30 || form.temperature > 45)) {
      vitalsErrors.push("Temperature must be between 30°C and 45°C")
    }
    if (vitalsErrors.length > 0) {
      setError(vitalsErrors.join(". "))
      return
    }

    setLoading(true)

    const payload = {
      ...form,
      // Use custom complaint when "Other" is selected
      chief_complaint: form.chief_complaint === "Other" ? form.custom_complaint.trim() : form.chief_complaint,
      patient_name: form.patient_name.trim(),
      patient_age: parseInt(form.patient_age),
      bp_systolic: form.bp_systolic ? parseInt(form.bp_systolic) : null,
      bp_diastolic: form.bp_diastolic ? parseInt(form.bp_diastolic) : null,
      spo2: form.spo2 ? parseInt(form.spo2) : null,
      heart_rate: form.heart_rate ? parseInt(form.heart_rate) : null,
      temperature: form.temperature ? parseFloat(form.temperature) : null,
    }

    // Run local ONNX triage immediately — before any network call
    const local = await classify(payload)
    if (local) {
      setLocalResult(local)
    }

    try {
      const data = await submitCase(payload)
      // When queued offline, keep local triage result for display
      if (data.queued) {
        setResult({ ...data, localTriage: local })
        showToast('Saved offline \u2014 will sync when connected', 'warning')
      } else {
        // Server result available — clear local preliminary result
        setResult(data)
        setLocalResult(null)
        showToast('Case submitted successfully', 'success')
      }
      setForm(emptyForm)
    } catch (err) {
      // If offline or network error — local result stays displayed
      // The Phase 8 queue handles the actual sync
      setError(err.message || "Submission failed. Check connection.")
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
                  {offlineTriage.confidence != null && (
                    <p className="text-xs text-text3 mt-2 font-mono">
                      Confidence: {(offlineTriage.confidence * 100).toFixed(0)}%
                    </p>
                  )}
                </div>
              )}
              <div className="mb-6">
                <span className="inline-block px-5 py-2 rounded-pill font-bold text-lg tracking-wide shadow-sm bg-sand text-urgent border border-urgent/20 font-mono">
                  SAVED OFFLINE
                </span>
              </div>
              <h2 className="text-text text-xl font-bold tracking-tight mb-2 font-display italic">Case Saved Locally</h2>
              <p className="text-text2 leading-relaxed mb-8">
                {offlineTriage
                  ? 'Preliminary AI triage shown above. Full analysis will be available when connectivity is restored.'
                  : 'It will be submitted automatically when connectivity is restored.'}
              </p>
            </>
          ) : (
            <>
              <div className="mb-6">
                <span className={`inline-block px-5 py-2 rounded-pill font-bold text-lg tracking-wide font-mono ${BADGE_COLORS[result.triage_level]}`}>
                  {result.triage_level}
                </span>
              </div>
              <h2 className="text-text text-xl font-bold tracking-tight mb-2 font-display italic">Case Successfully Logged</h2>
              <p className="text-text2 leading-relaxed mb-8">{result.risk_driver}</p>
            </>
          )}
          <button
            onClick={() => setResult(null)}
            className="bg-forest text-white px-8 py-3 rounded-pill font-medium cursor-pointer shadow-btn hover:shadow-card-hover transition-all active:scale-[0.98]"
          >
            Submit Another Case
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-xl mx-auto p-6 md:p-8 mt-6 mb-20 bg-surface shadow-card border border-leaf/40 rounded-xl hover:shadow-card-hover transition-shadow duration-300">
      <h1 className="text-2xl font-display italic text-forest tracking-tight mb-8 text-center">Patient Intake Form</h1>

      {error && (
        <div className="bg-emergency/10 border border-emergency/30 text-emergency px-4 py-3 rounded-md mb-4 text-sm">
          {error}
        </div>
      )}

      {/* Patient Location */}
      <Section title="Location">
        <Field label="Location / Village *">
          <input name="location" value={form.location} onChange={handleChange}
            placeholder="e.g. Rampur Village" className={inputClass} />
        </Field>
      </Section>

      {/* Patient */}
      <Section title="Patient Details">
        <Field label="Patient Name *">
          <input name="patient_name" value={form.patient_name} onChange={handleChange}
            placeholder="e.g. Priya Sharma" className={inputClass} maxLength={100} />
        </Field>
        <Field label="Age (years) *">
          <input name="patient_age" type="number" value={form.patient_age}
            onChange={handleChange} placeholder="e.g. 45" className={inputClass} />
        </Field>
        <Field label="Sex *">
          <div className="flex gap-4 mt-1">
            {["male", "female", "other"].map(s => (
              <label key={s} className="flex items-center gap-2 cursor-pointer group">
                <input type="radio" name="patient_sex" value={s}
                  checked={form.patient_sex === s} onChange={handleChange}
                  className="accent-forest" />
                <span className="capitalize text-sm text-text2 group-hover:text-forest transition-colors">{s}</span>
              </label>
            ))}
          </div>
        </Field>
      </Section>

      {/* Complaint */}
      <Section title="Chief Complaint">
        <Field label="Primary Complaint *">
          <select name="chief_complaint" value={form.chief_complaint}
            onChange={handleChange} className={inputClass}>
            <option value="">Select complaint</option>
            {COMPLAINTS.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </Field>
        {form.chief_complaint === "Other" && (
          <Field label="Please specify the complaint *">
            <input
              name="custom_complaint"
              value={form.custom_complaint}
              onChange={handleChange}
              placeholder="e.g. Joint pain, skin rash, vision problems..."
              className={inputClass}
              maxLength={200}
            />
          </Field>
        )}
        <Field label="Duration *">
          <select name="complaint_duration" value={form.complaint_duration}
            onChange={handleChange} className={inputClass}>
            <option value="">Select duration</option>
            {DURATIONS.map(d => <option key={d} value={d}>{d}</option>)}
          </select>
        </Field>
      </Section>

      {/* Vitals */}
      <Section title="Vitals (optional — record what is available)">
        <div className="grid grid-cols-2 gap-3">
          <Field label="BP Systolic (mmHg)">
            <input name="bp_systolic" type="number" value={form.bp_systolic}
              onChange={handleChange} placeholder="e.g. 120" className={inputClass} />
          </Field>
          <Field label="BP Diastolic (mmHg)">
            <input name="bp_diastolic" type="number" value={form.bp_diastolic}
              onChange={handleChange} placeholder="e.g. 80" className={inputClass} />
          </Field>
          <Field label="SpO2 (%)">
            <input name="spo2" type="number" value={form.spo2}
              onChange={handleChange} placeholder="e.g. 98" className={inputClass} />
          </Field>
          <Field label="Heart Rate (bpm)">
            <input name="heart_rate" type="number" value={form.heart_rate}
              onChange={handleChange} placeholder="e.g. 72" className={inputClass} />
          </Field>
          <Field label="Temperature (°C)">
            <input name="temperature" type="number" step="0.1" value={form.temperature}
              onChange={handleChange} placeholder="e.g. 37.2" className={inputClass} />
          </Field>
        </div>
      </Section>

      {/* Symptoms */}
      <Section title="Symptoms (select all that apply)">
        <div className="grid grid-cols-2 gap-3">
          {SYMPTOM_OPTIONS.map((s, idx) => {
            const isSelected = form.symptoms.includes(s.id);
            return (
              <label
                key={s.id}
                style={{ animationDelay: `${idx * 40}ms` }}
                className={`flex items-center justify-center p-3 rounded-lg border text-sm transition-all duration-200 cursor-pointer animate-fade-up
                ${isSelected
                  ? 'bg-forest text-white border-forest shadow-btn font-medium tracking-tight'
                  : 'bg-surface2 border-surface3 text-text2 hover:border-sage hover:shadow-card'
                }`}
              >
                <input type="checkbox" checked={isSelected}
                  onChange={() => handleSymptom(s.id)}
                  className="sr-only" />
                <span className="text-center">{s.label}</span>
              </label>
            )
          })}
        </div>
      </Section>

      {/* Observations */}
      <Section title="Observations (optional)">
        <textarea name="observations" value={form.observations} onChange={handleChange}
          placeholder="Any additional observations about the patient's condition..."
          rows={3} className={`${inputClass} resize-none`} maxLength={500} />
        <Field label="Known Conditions">
          <input name="known_conditions" value={form.known_conditions}
            onChange={handleChange} placeholder="e.g. diabetes, hypertension"
            className={inputClass} />
        </Field>
        <Field label="Current Medications">
          <input name="current_medications" value={form.current_medications}
            onChange={handleChange} placeholder="e.g. metformin, amlodipine"
            className={inputClass} />
        </Field>
      </Section>

      {/* Submit */}
      <button
        onClick={handleSubmit}
        disabled={loading}
        className="w-full bg-forest text-white py-4 rounded-pill font-bold text-lg mt-6 shadow-btn hover:shadow-card-hover disabled:opacity-75 disabled:cursor-wait transition-all duration-200 active:scale-[0.98] cursor-pointer flex justify-center items-center"
      >
        {loading ? <span className="animate-pulse">Analyzing Case...</span> : "Submit Case"}
      </button>

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
              Preliminary triage
            </span>
          </div>
          <p className="mt-2 text-xs text-text3">
            {navigator.onLine
              ? 'Sending to server for full analysis…'
              : 'Offline — queued for sync. Full briefing will appear for the doctor when connectivity returns.'}
          </p>
        </div>
      )}
    </div>
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

function Field({ label, children }) {
  return (
    <div>
      <label className="block text-sm font-medium text-text2 mb-2 ml-1">{label}</label>
      {children}
    </div>
  )
}
