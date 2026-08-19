/**
 * Serializes raw IntakeForm state into the clinical intake payload schema.
 * Ensures optional fields (such as human_review_reason) serialize as undefined
 * when absent/empty rather than null, matching the Zod schema expectation.
 */
export function serializeIntakePayload(form, patientKey, consentCapturedAt = new Date().toISOString()) {
  return {
    ...form,
    patient_key: patientKey,
    chief_complaint: form.chief_complaint === "Other" ? form.custom_complaint?.trim() || "" : form.chief_complaint,
    patient_name: form.patient_name?.trim() || "",
    patient_age: form.patient_age ? parseInt(form.patient_age) : undefined,
    age_months: form.age_months ? parseInt(form.age_months) : null,
    muac_mm: form.muac_mm ? parseInt(form.muac_mm) : null,
    bp_systolic: form.bp_systolic ? parseInt(form.bp_systolic) : null,
    bp_diastolic: form.bp_diastolic ? parseInt(form.bp_diastolic) : null,
    spo2: form.spo2 ? parseInt(form.spo2) : null,
    heart_rate: form.heart_rate ? parseInt(form.heart_rate) : null,
    temperature: form.temperature ? parseFloat(form.temperature) : null,
    is_pregnant: Boolean(form.is_pregnant),
    human_review_requested: Boolean(form.human_review_requested),
    human_review_reason: form.human_review_reason?.trim() || undefined,
    consent_captured_at: consentCapturedAt,
  }
}
