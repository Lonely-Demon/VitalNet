/**
 * Serializes raw IntakeForm state into the clinical intake payload schema.
 * Ensures optional fields (such as human_review_reason) serialize as undefined
 * when absent/empty rather than null, matching the Zod schema expectation.
 * Enforces strict Number.isFinite validation on all numeric vitals (BUG-32).
 */
export function parseStrictInt(val) {
  if (val === undefined || val === null) return null
  if (typeof val === 'string' && val.trim() === '') return null
  if (typeof val === 'boolean') return null
  const num = Number(val)
  return Number.isFinite(num) ? Math.trunc(num) : null
}

export function parseStrictFloat(val) {
  if (val === undefined || val === null) return null
  if (typeof val === 'string' && val.trim() === '') return null
  if (typeof val === 'boolean') return null
  const num = Number(val)
  return Number.isFinite(num) ? num : null
}

export function serializeIntakePayload(form, patientKey, consentCapturedAt = new Date().toISOString()) {
  const parsedAge = parseStrictInt(form.patient_age)
  return {
    ...form,
    patient_key: patientKey,
    chief_complaint: form.chief_complaint === "Other" ? form.custom_complaint?.trim() || "" : form.chief_complaint,
    patient_name: form.patient_name?.trim() || "",
    patient_age: parsedAge !== null ? parsedAge : undefined,
    age_months: parseStrictInt(form.age_months),
    muac_mm: parseStrictInt(form.muac_mm),
    bp_systolic: parseStrictInt(form.bp_systolic ?? form.blood_pressure_systolic),
    bp_diastolic: parseStrictInt(form.bp_diastolic ?? form.blood_pressure_diastolic),
    spo2: parseStrictInt(form.spo2),
    heart_rate: parseStrictInt(form.heart_rate),
    respiratory_rate: parseStrictInt(form.respiratory_rate),
    temperature: parseStrictFloat(form.temperature),
    is_pregnant: Boolean(form.is_pregnant),
    human_review_requested: Boolean(form.human_review_requested),
    human_review_reason: form.human_review_reason?.trim() || undefined,
    consent_captured_at: consentCapturedAt,
  }
}
