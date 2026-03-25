// frontend/src/utils/validation.js
// Hard clinical sanity bounds for the IntakeForm.
// Must be applied BEFORE a case enters the offline IndexedDB queue —
// the ONNX model is garbage-in-garbage-out. Invalid vitals (HR=900, SpO2=150%)
// produce absurd confidence scores and corrupt the triage output silently.
//
// Uses Zod for schema validation. Run: npm install zod

import { z } from 'zod'

// Helper: accepts a number in a valid clinical range, or empty string / null / undefined
// (vitals are optional — ASHA workers may not always have them available)
function optionalVital(min, max, label) {
  return z
    .union([
      z.literal(''),
      z.null(),
      z.undefined(),
      z.number({ invalid_type_error: `${label} must be a number` }).min(min, `${label} must be ≥ ${min}`).max(max, `${label} must be ≤ ${max}`),
    ])
    .optional()
}

export const clinicalSchema = z.object({
  // Patient identifiers
  patient_name:    z.string().min(2, 'Patient name is required (min 2 characters)'),
  patient_age:     z.number({ invalid_type_error: 'Age must be a number' })
                    .min(0, 'Age must be 0 or above')
                    .max(120, 'Age must be realistic (max 120)'),
  patient_sex:     z.enum(['male', 'female', 'other'], {
                     errorMap: () => ({ message: 'Sex must be male, female, or other' }),
                   }),

  // Vitals — optional but bounded when present
  bp_systolic:     optionalVital(50,  300, 'Systolic BP'),
  bp_diastolic:    optionalVital(30,  200, 'Diastolic BP'),
  spo2:            optionalVital(50,  100, 'SpO2'),
  heart_rate:      optionalVital(20,  300, 'Heart rate'),
  temperature:     optionalVital(28,   44, 'Temperature (°C)'),

  // Required clinical context
  chief_complaint:      z.string().min(3, 'Chief complaint is required'),
  complaint_duration:   z.string().min(1, 'Complaint duration is required'),

  // Optional rich context
  symptoms:             z.array(z.string()).optional().default([]),
  observations:         z.string().optional().default(''),
  known_conditions:     z.string().optional().default(''),
  current_medications:  z.string().optional().default(''),
  location:             z.string().optional().default(''),
})

/**
 * Validate form data against the clinical schema.
 * Returns { success: true } or { success: false, errors: Record<string, string> }
 *
 * @param {object} formData - raw form values from IntakeForm state
 * @returns {{ success: boolean, errors?: Record<string, string> }}
 */
export function validateForm(formData) {
  const result = clinicalSchema.safeParse(formData)
  if (result.success) return { success: true }

  const errors = {}
  for (const issue of result.error.issues) {
    const field = issue.path.join('.')
    errors[field] = issue.message
  }
  return { success: false, errors }
}
