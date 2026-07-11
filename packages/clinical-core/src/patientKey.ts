// Client-side patient continuity key generation. An opaque XXXX-XXXX
// identifier an ASHA worker can hand a patient (printed or shown as a QR
// code) so a return visit can be linked to prior ones — entirely offline,
// with no centralized patient registry and no PII encoded in the key
// itself. Ported from frontend/src/utils/patientKey.js; the format regex is
// re-exported from schema.ts (PATIENT_KEY_RE) so there is exactly one
// definition of the key format across the whole package.

import { PATIENT_KEY_RE } from "./schema.js";

export { PATIENT_KEY_RE as PATIENT_KEY_FORMAT_RE };

// Excludes 0/O/1/I/L so a handwritten or read-aloud key is never mis-copied.
const ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ";

/** Generates a new random patient continuity key, format XXXX-XXXX. Uses
 * crypto.getRandomValues — works fully offline, no network/server call.
 * Works in both browser and Node (18.17+) runtimes via globalThis.crypto. */
export function generatePatientKey(): string {
  const bytes = new Uint8Array(8);
  globalThis.crypto.getRandomValues(bytes);
  let out = "";
  for (let i = 0; i < 8; i++) {
    if (i === 4) out += "-";
    out += ALPHABET[bytes[i]! % ALPHABET.length];
  }
  return out;
}

/** Normalizes user-typed input (trim, uppercase) and validates the format. */
export function normalizePatientKey(raw: string | null | undefined): string | null {
  const key = (raw || "").trim().toUpperCase();
  return PATIENT_KEY_RE.test(key) ? key : null;
}
