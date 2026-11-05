// Client-side patient continuity key generation & Indic phonetic recovery (ADR §49).
// An opaque XXXX-XXXX identifier an ASHA worker can hand a patient (printed or shown as a QR
// code) so a return visit can be linked to prior ones — entirely offline,
// with no centralized patient registry and no PII encoded in the key
// itself. Ported from frontend/src/utils/patientKey.js; the format regex is
// re-exported from schema.ts (PATIENT_KEY_RE) so there is exactly one
// definition of the key format across the whole package.

import { PATIENT_KEY_RE } from "./schema.js";

export { PATIENT_KEY_RE as PATIENT_KEY_FORMAT_RE };

// Excludes 0/O/1/I/L/Z so a handwritten or read-aloud key is never mis-copied.
export const ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXY"; // Length = 30
// Largest multiple of 30 <= 256 is 240 (8 * 30). Rejecting bytes >= 240 eliminates modulo bias.
export const MAX_UNBIASED_BYTE = 240;

/**
 * Generates a cryptographically unbiased random patient continuity key (XXXX-XXXX)
 * using CSPRNG rejection sampling with unbiased byte modulus (b < 240) to eliminate modulo bias.
 */
export function generatePatientKey(): string {
  const chars: string[] = [];
  const buf = new Uint8Array(16);
  while (chars.length < 8) {
    globalThis.crypto.getRandomValues(buf);
    for (let i = 0; i < buf.length && chars.length < 8; i++) {
      const b = buf[i]!;
      if (b < MAX_UNBIASED_BYTE) {
        chars.push(ALPHABET[b % 30]!);
      }
    }
  }
  return `${chars.slice(0, 4).join("")}-${chars.slice(4, 8).join("")}`;
}

export const generateUnbiasedPatientKey = generatePatientKey;

/** Normalizes user-typed input (trim, uppercase) and validates the format. */
export function normalizePatientKey(raw: string | null | undefined): string | null {
  const key = (raw || "").trim().toUpperCase();
  return PATIENT_KEY_RE.test(key) ? key : null;
}

/**
 * Deterministic, non-cryptographic dual 32-bit FNV-1a digest mapped into the 30-character
 * VitalNet continuity key alphabet (XXXX-XXXX).
 * Converts an external identifier (e.g. ABHA HIDN) into a schema-valid patient_key
 * synchronously and offline without leaking raw identifiers.
 */
export function deriveDeterministicPatientKey(namespace: string, identifier: string): string {
  const input = `${namespace}:${(identifier || "").trim().toLowerCase()}`;
  let h1 = 0x811c9dc5;
  let h2 = 0x01000193;
  for (let i = 0; i < input.length; i++) {
    const code = input.charCodeAt(i);
    h1 = Math.imul(h1 ^ code, 0x01000193) >>> 0;
    h2 = Math.imul(h2 ^ (code + i), 0x85ebca6b) >>> 0;
  }
  const p1: string[] = [];
  let temp1 = h1;
  for (let i = 0; i < 4; i++) {
    p1.push(ALPHABET[temp1 % 30]!);
    temp1 = Math.floor(temp1 / 30);
  }
  const p2: string[] = [];
  let temp2 = h2;
  for (let i = 0; i < 4; i++) {
    p2.push(ALPHABET[temp2 % 30]!);
    temp2 = Math.floor(temp2 / 30);
  }
  return `${p1.join("")}-${p2.join("")}`;
}

/**
 * Deterministic FNV-1a ABHA HIDN derivation producing a 16-character base32 key.
 */
export function deriveAbhaKey(abhaNumber: string): string {
  const clean = (abhaNumber || "").replace(/[^0-9A-Za-z]/g, "").toLowerCase();
  const BASE32 = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  let h1 = 0x811c9dc5;
  let h2 = 0x01000193;
  let h3 = 0x85ebca6b;
  for (let i = 0; i < clean.length; i++) {
    const code = clean.charCodeAt(i);
    h1 = Math.imul(h1 ^ code, 0x01000193) >>> 0;
    h2 = Math.imul(h2 ^ (code + i), 0x85ebca6b) >>> 0;
    h3 = Math.imul(h3 ^ (code + (i * 31)), 0x9e3779b9) >>> 0;
  }
  const chars: string[] = [];
  let v1 = h1;
  for (let i = 0; i < 6; i++) {
    chars.push(BASE32[v1 % 32]!);
    v1 = Math.floor(v1 / 32);
  }
  let v2 = h2;
  for (let i = 0; i < 5; i++) {
    chars.push(BASE32[v2 % 32]!);
    v2 = Math.floor(v2 / 32);
  }
  let v3 = h3;
  for (let i = 0; i < 5; i++) {
    chars.push(BASE32[v3 % 32]!);
    v3 = Math.floor(v3 / 32);
  }
  return chars.join("");
}

/**
 * Indic and Devanagari phonetic consonant normalization.
 * Transliterates Devanagari consonants to Latin equivalents, strips vowels,
 * collapses aspirated consonant digraphs and sibilants (bh->b, kh->k, th->t, ph->p, gh->g, ch->c, jh->j, dh->d, sh->s),
 * collapses geminates ((.)\1+ -> $1), strips non-letters, and returns an 8-character skeleton.
 *
 * Example equivalence:
 * buildIndicPhoneticSkeleton("रमेश पाटील") === buildIndicPhoneticSkeleton("Ramesh Patil") === "rmsptl"
 */
export function buildIndicPhoneticSkeleton(name: string): string {
  if (!name || typeof name !== "string") return "";

  const devanagariMap: Record<string, string> = {
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "n",
    "च": "c", "छ": "ch", "ज": "j", "झ": "jh", "ञ": "n",
    "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n",
    "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
    "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m",
    "य": "y", "र": "r", "ल": "l", "व": "v",
    "श": "s", "ष": "s", "स": "s", "ह": "h",
    "ळ": "l", "क्ष": "k", "ज्ञ": "g"
  };

  let transliterated = "";
  for (let i = 0; i < name.length; i++) {
    const char = name[i]!;
    if (devanagariMap[char]) {
      transliterated += devanagariMap[char];
    } else {
      transliterated += char.toLowerCase();
    }
  }

  // Strip vowels (Latin and Indic marks)
  let consonantsOnly = transliterated
    .replace(/[aeiouyāīūअ-औा-ौ\u0901-\u0903\u093e-\u094d]/gi, "");

  // Collapse aspirated digraphs and sibilants
  const digraphs: [RegExp, string][] = [
    [/bh/g, "b"], [/kh/g, "k"], [/th/g, "t"], [/ph/g, "p"],
    [/gh/g, "g"], [/ch/g, "c"], [/jh/g, "j"], [/dh/g, "d"],
    [/sh/g, "s"]
  ];
  for (const [pattern, replacement] of digraphs) {
    consonantsOnly = consonantsOnly.replace(pattern, replacement);
  }

  // Collapse geminate duplicate consonants (e.g. tt -> t, pp -> p)
  consonantsOnly = consonantsOnly.replace(/(.)\1+/g, "$1");

  // Keep letters only and truncate to 8 chars
  return consonantsOnly.replace(/[^a-z]/g, "").slice(0, 8);
}

export {
  parseAbhaQr,
  parseAbhaQrPayload,
  parsePatientQrPayload,
  type ParsedAbhaQr,
  type ParsedQrIdentity,
} from "./abhaScanner.js";
