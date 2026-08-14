import { test, expect } from '@playwright/test'
import { serializeIntakePayload } from '../src/pages/IntakeForm.jsx'
import { validateIntakeForm } from '@vitalnet/clinical-core'

const BASE_FORM = {
  patient_name: 'QA Phase42 Patient',
  patient_age: '30',
  patient_sex: 'female',
  location: 'QA Synthetic Village',
  chief_complaint: 'Fever',
  custom_complaint: '',
  complaint_duration: 'Less than 1 hour',
  bp_systolic: '',
  bp_diastolic: '',
  spo2: '',
  heart_rate: '',
  temperature: '',
  is_pregnant: false,
  human_review_requested: false,
  human_review_reason: '',
  consent_captured: true,
  symptoms: [],
}

test.describe('IntakeForm payload serialization & clinical-core validation', () => {
  test('Scenario 1: human_review_requested=false with blank reason serializes to undefined (not null) and passes validation', () => {
    const payload = serializeIntakePayload(
      { ...BASE_FORM, human_review_requested: false, human_review_reason: '' },
      '2345-6789',
      '2026-08-14T10:00:00.000Z',
    )

    // Verify exact serialization invariant: undefined, never null
    expect(payload.human_review_reason).toBeUndefined()
    expect(payload.human_review_reason).not.toBeNull()

    // Verify clinical-core Zod validation succeeds
    const validation = validateIntakeForm(payload)
    expect(validation.success).toBe(true)
    if (validation.success) {
      expect(validation.data.human_review_reason).toBeUndefined()
    }
  })

  test('Scenario 1b: human_review_requested=false with whitespace-only reason serializes to undefined and passes validation', () => {
    const payload = serializeIntakePayload(
      { ...BASE_FORM, human_review_requested: false, human_review_reason: '   ' },
      '2345-6789',
      '2026-08-14T10:00:00.000Z',
    )

    expect(payload.human_review_reason).toBeUndefined()
    expect(payload.human_review_reason).not.toBeNull()

    const validation = validateIntakeForm(payload)
    expect(validation.success).toBe(true)
  })

  test('Scenario 2: human_review_requested=true with nonblank reason preserves reason and passes validation', () => {
    const reason = 'Patient appears lethargic and pale'
    const payload = serializeIntakePayload(
      { ...BASE_FORM, human_review_requested: true, human_review_reason: reason },
      '2345-6789',
      '2026-08-14T10:00:00.000Z',
    )

    expect(payload.human_review_requested).toBe(true)
    expect(payload.human_review_reason).toBe(reason)

    const validation = validateIntakeForm(payload)
    expect(validation.success).toBe(true)
    if (validation.success) {
      expect(validation.data.human_review_reason).toBe(reason)
    }
  })

  test('Scenario 3: human_review_requested=true with blank reason fails validation with review-reason error', () => {
    const payload = serializeIntakePayload(
      { ...BASE_FORM, human_review_requested: true, human_review_reason: '' },
      '2345-6789',
      '2026-08-14T10:00:00.000Z',
    )

    expect(payload.human_review_requested).toBe(true)
    expect(payload.human_review_reason).toBeUndefined()

    const validation = validateIntakeForm(payload)
    expect(validation.success).toBe(false)
    if (!validation.success) {
      expect(validation.errors.human_review_reason).toBe(
        'human_review_reason is required when review is requested',
      )
    }
  })
})
