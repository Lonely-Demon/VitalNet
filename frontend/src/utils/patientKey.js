// patientKey.js — Client-side patient continuity key generation.
//
// An opaque XXXX-XXXX identifier an ASHA worker can hand a patient (printed
// or shown as a QR code) so a return visit can be linked to prior ones —
// entirely offline, with no centralized patient registry and no PII encoded
// in the key itself. Must mirror backend/app/models/schemas.py::PATIENT_KEY_RE.

// Excludes 0/O/1/I/L so a handwritten or read-aloud key is never mis-copied.
const ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"

export const PATIENT_KEY_FORMAT_RE = /^[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{4}-[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{4}$/

/**
 * Generates a new random patient continuity key, format XXXX-XXXX.
 * Uses crypto.getRandomValues — works fully offline, no network/server call.
 */
export function generatePatientKey() {
  const bytes = new Uint8Array(8)
  crypto.getRandomValues(bytes)
  let out = ""
  for (let i = 0; i < 8; i++) {
    if (i === 4) out += "-"
    out += ALPHABET[bytes[i] % ALPHABET.length]
  }
  return out
}

/** Normalizes user-typed input (trim, uppercase) and validates the format. */
export function normalizePatientKey(raw) {
  const key = (raw || "").trim().toUpperCase()
  return PATIENT_KEY_FORMAT_RE.test(key) ? key : null
}
