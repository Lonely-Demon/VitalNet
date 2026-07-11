// The single IntakeForm schema — replaces the previously hand-mirrored pair
// backend/app/models/schemas.py::IntakeForm (Pydantic) and
// frontend/src/utils/validation.js::clinicalSchema (Zod). Every bound here
// is the merge of both: where they previously disagreed (bp_diastolic floor
// was 10 in Pydantic vs 30 in Zod), the STRICTER (Pydantic, server-enforced)
// bound wins, since that's what actually gated production data.

import { z } from "zod";

/** Allow-list of symptom IDs. Keeps the ML feature pipeline's input space
 * bounded — free-form symptom strings would let a caller inject arbitrary
 * tokens into engineered features and the LLM prompt. */
export const ALLOWED_SYMPTOMS = [
  "chest_pain",
  "breathlessness",
  "altered_consciousness",
  "severe_bleeding",
  "seizure",
  "high_fever",
  "severe_abdominal_pain",
  "persistent_vomiting",
  "severe_headache",
  "weakness_one_side",
  "difficulty_speaking",
  "swelling_face_throat",
] as const;

export type Symptom = (typeof ALLOWED_SYMPTOMS)[number];
export const ALLOWED_SYMPTOMS_SET: ReadonlySet<string> = new Set(ALLOWED_SYMPTOMS);

export const MAX_SYMPTOMS = 20; // generous ceiling — real forms send at most ~12

/** Unambiguous alphabet for patient continuity keys — excludes 0/O/1/I/L so
 * a key read aloud or handwritten from a QR-code printout is never
 * mis-copied. */
export const PATIENT_KEY_RE = /^[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{4}-[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{4}$/;

/** Strip non-printable/control characters that have no clinical meaning but
 * can be used to smuggle formatting/instructions into the LLM prompt (e.g.
 * embedded newlines mimicking prompt structure). */
export function stripControlChars(v: string): string {
  return [...v].filter((ch) => ch === "\n" || ch === "\t" || /\P{Cc}/u.test(ch)).join("").trim();
}

const controlCharField = (max: number) => z.string().max(max).transform(stripControlChars);
const optionalControlCharField = (max: number) =>
  z
    .string()
    .max(max)
    .transform(stripControlChars)
    .optional();

export const intakeFormSchema = z
  .object({
    // Patient identifiers
    patient_name: controlCharField(100).pipe(z.string().min(1, "Patient name is required")),
    patient_age: z.number().int().min(0).max(120),
    patient_sex: z.enum(["male", "female", "other"]),

    chief_complaint: controlCharField(200).pipe(z.string().min(1, "Chief complaint is required")),
    complaint_duration: z.string().min(1).max(50),
    location: controlCharField(200).pipe(z.string().min(1, "Location / village is required")),

    // Vitals — optional but bounded when present (bounds match the stricter
    // of the two previously-mirrored schemas)
    bp_systolic: z.number().int().min(30).max(300).nullish(),
    bp_diastolic: z.number().int().min(10).max(200).nullish(),
    spo2: z.number().int().min(50).max(100).nullish(),
    heart_rate: z.number().int().min(10).max(250).nullish(),
    temperature: z.number().min(25.0).max(45.0).nullish(),

    // Structured pregnancy flag — feeds the preeclampsia rule (rules.ts).
    // Deliberately a real field rather than relying on free-text keyword
    // matching, which remains a soft ML feature signal only (features.ts).
    is_pregnant: z.boolean().nullish(),

    symptoms: z
      .array(z.string())
      .max(MAX_SYMPTOMS)
      .refine((v) => v.every((s) => ALLOWED_SYMPTOMS_SET.has(s)), {
        message: "Unrecognised symptom id(s)",
      })
      .default([]),

    observations: optionalControlCharField(500),
    known_conditions: optionalControlCharField(300),
    current_medications: optionalControlCharField(300),

    // Offline sync metadata
    client_id: z.string().uuid().optional(),
    client_submitted_at: z.string().datetime({ offset: true }).optional(),
    created_offline: z.boolean().default(false),

    human_review_requested: z.boolean().default(false),
    human_review_reason: optionalControlCharField(500),

    // Patient (or guardian) consent to data collection and AI-assisted
    // triage. Enforced below, not just as a frontend UX gate.
    consent_captured: z.boolean().default(false),
    consent_captured_at: z.string().datetime({ offset: true }).optional(),

    patient_key: z
      .string()
      .transform((v) => v.trim().toUpperCase())
      .refine((v) => PATIENT_KEY_RE.test(v), {
        message: "patient_key must match format XXXX-XXXX (no 0/O/1/I/L)",
      })
      .optional(),
  })
  .superRefine((form, ctx) => {
    if (form.bp_systolic != null && form.bp_diastolic != null && form.bp_diastolic >= form.bp_systolic) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Diastolic BP must be lower than systolic BP",
        path: ["bp_diastolic"],
      });
    }
    if (form.human_review_requested && !form.human_review_reason?.trim()) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "human_review_reason is required when review is requested",
        path: ["human_review_reason"],
      });
    }
    if (!form.consent_captured) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        message: "Patient consent is required before submission",
        path: ["consent_captured"],
      });
    }
  });

export type IntakeForm = z.infer<typeof intakeFormSchema>;

/** Convenience wrapper matching the previous validateForm()'s
 * { success, errors } shape used across the frontend forms. */
export function validateIntakeForm(
  raw: unknown,
): { success: true; data: IntakeForm } | { success: false; errors: Record<string, string> } {
  const result = intakeFormSchema.safeParse(raw);
  if (result.success) return { success: true, data: result.data };

  const errors: Record<string, string> = {};
  for (const issue of result.error.issues) {
    errors[issue.path.join(".")] = issue.message;
  }
  return { success: false, errors };
}
