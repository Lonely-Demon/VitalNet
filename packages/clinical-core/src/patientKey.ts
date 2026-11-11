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
 * Synchronous SHA-256 cryptographic hash function (FIPS 180-4 compliant).
 * Used with domain salt to ensure deterministic, irreversible patient and ABHA key derivation (BUG-66).
 */
function sha256Sync(message: string): Uint8Array {
  function rightRotate(value: number, amount: number): number {
    return (value >>> amount) | (value << (32 - amount));
  }

  const K = [
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
  ];

  let H0 = 0x6a09e667;
  let H1 = 0xbb67ae85;
  let H2 = 0x3c6ef372;
  let H3 = 0xa54ff53a;
  let H4 = 0x510e527f;
  let H5 = 0x9b05688c;
  let H6 = 0x1f83d9ab;
  let H7 = 0x5be0cd19;

  const utf8: number[] = [];
  for (let i = 0; i < message.length; i++) {
    let charcode = message.charCodeAt(i);
    if (charcode < 0x80) utf8.push(charcode);
    else if (charcode < 0x800) {
      utf8.push(0xc0 | (charcode >> 6), 0x80 | (charcode & 0x3f));
    } else if (charcode < 0xd800 || charcode >= 0xe000) {
      utf8.push(0xe0 | (charcode >> 12), 0x80 | ((charcode >> 6) & 0x3f), 0x80 | (charcode & 0x3f));
    } else {
      i++;
      charcode = 0x10000 + (((charcode & 0x3ff) << 10) | (message.charCodeAt(i) & 0x3ff));
      utf8.push(
        0xf0 | (charcode >> 18),
        0x80 | ((charcode >> 12) & 0x3f),
        0x80 | ((charcode >> 6) & 0x3f),
        0x80 | (charcode & 0x3f)
      );
    }
  }

  const bitLength = utf8.length * 8;
  utf8.push(0x80);
  while ((utf8.length % 64) !== 56) {
    utf8.push(0);
  }
  const hi = Math.floor(bitLength / 0x100000000);
  const lo = bitLength >>> 0;
  for (let b = 24; b >= 0; b -= 8) utf8.push((hi >> b) & 0xff);
  for (let b = 24; b >= 0; b -= 8) utf8.push((lo >> b) & 0xff);

  const W = new Int32Array(64);

  for (let chunk = 0; chunk < utf8.length; chunk += 64) {
    for (let i = 0; i < 16; i++) {
      const idx = chunk + i * 4;
      W[i] = (utf8[idx]! << 24) | (utf8[idx + 1]! << 16) | (utf8[idx + 2]! << 8) | utf8[idx + 3]!;
    }
    for (let i = 16; i < 64; i++) {
      const s0 = rightRotate(W[i - 15]!, 7) ^ rightRotate(W[i - 15]!, 18) ^ (W[i - 15]! >>> 3);
      const s1 = rightRotate(W[i - 2]!, 17) ^ rightRotate(W[i - 2]!, 19) ^ (W[i - 2]! >>> 10);
      W[i] = (((W[i - 16]! + s0) | 0) + ((W[i - 7]! + s1) | 0)) | 0;
    }

    let a = H0;
    let b = H1;
    let c = H2;
    let d = H3;
    let e = H4;
    let f = H5;
    let g = H6;
    let h = H7;

    for (let i = 0; i < 64; i++) {
      const S1 = rightRotate(e, 6) ^ rightRotate(e, 11) ^ rightRotate(e, 25);
      const ch = (e & f) ^ (~e & g);
      const temp1 = (((((h + S1) | 0) + ch) | 0) + ((K[i]! + W[i]!) | 0)) | 0;
      const S0 = rightRotate(a, 2) ^ rightRotate(a, 13) ^ rightRotate(a, 22);
      const maj = (a & b) ^ (a & c) ^ (b & c);
      const temp2 = (S0 + maj) | 0;

      h = g;
      g = f;
      f = e;
      e = (d + temp1) | 0;
      d = c;
      c = b;
      b = a;
      a = (temp1 + temp2) | 0;
    }

    H0 = (H0 + a) | 0;
    H1 = (H1 + b) | 0;
    H2 = (H2 + c) | 0;
    H3 = (H3 + d) | 0;
    H4 = (H4 + e) | 0;
    H5 = (H5 + f) | 0;
    H6 = (H6 + g) | 0;
    H7 = (H7 + h) | 0;
  }

  const result = new Uint8Array(32);
  const words = [H0, H1, H2, H3, H4, H5, H6, H7];
  for (let i = 0; i < 8; i++) {
    const w = words[i]!;
    result[i * 4] = (w >>> 24) & 0xff;
    result[i * 4 + 1] = (w >>> 16) & 0xff;
    result[i * 4 + 2] = (w >>> 8) & 0xff;
    result[i * 4 + 3] = w & 0xff;
  }
  return result;
}

const DOMAIN_SALT_PATIENT_KEY = "vitalnet_p52_patient_key_salt_v2_7a9f";
const DOMAIN_SALT_ABHA_KEY = "vitalnet_p52_abha_key_salt_v2_3e1b";

/**
 * Deterministic cryptographic derivation with domain salt mapped into the 30-character
 * VitalNet continuity key alphabet (XXXX-XXXX) (BUG-66).
 * Converts an external identifier (e.g. ABHA HIDN) into a schema-valid patient_key
 * synchronously and offline without leaking raw identifiers or allowing rainbow-table reversal.
 */
export function deriveDeterministicPatientKey(namespace: string, identifier: string): string {
  const cleanId = (identifier || "").trim().toLowerCase();
  const input = `${DOMAIN_SALT_PATIENT_KEY}:${namespace.trim().toLowerCase()}:${cleanId}`;
  const digest = sha256Sync(input);

  const word1 = ((digest[0]! << 24) | (digest[1]! << 16) | (digest[2]! << 8) | digest[3]!) >>> 0;
  const word2 = ((digest[4]! << 24) | (digest[5]! << 16) | (digest[6]! << 8) | digest[7]!) >>> 0;

  const p1: string[] = [];
  let temp1 = word1;
  for (let i = 0; i < 4; i++) {
    p1.push(ALPHABET[temp1 % 30]!);
    temp1 = Math.floor(temp1 / 30);
  }
  const p2: string[] = [];
  let temp2 = word2;
  for (let i = 0; i < 4; i++) {
    p2.push(ALPHABET[temp2 % 30]!);
    temp2 = Math.floor(temp2 / 30);
  }
  return `${p1.join("")}-${p2.join("")}`;
}

/**
 * Deterministic SHA-256 salted ABHA HIDN derivation producing a 16-character base32 key (BUG-66).
 */
export function deriveAbhaKey(abhaNumber: string): string {
  const clean = (abhaNumber || "").replace(/[^0-9A-Za-z]/g, "").toLowerCase();
  const input = `${DOMAIN_SALT_ABHA_KEY}:${clean}`;
  const digest = sha256Sync(input);
  const BASE32 = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";

  const chars: string[] = [];
  let bitBuf = 0;
  let bitCount = 0;
  for (let i = 0; i < 10; i++) {
    bitBuf = (bitBuf << 8) | digest[i]!;
    bitCount += 8;
    while (bitCount >= 5) {
      bitCount -= 5;
      const idx = (bitBuf >> bitCount) & 0x1f;
      chars.push(BASE32[idx]!);
    }
  }
  return chars.join("");
}

/**
 * Indic and Devanagari phonetic consonant normalization (BUG-20).
 * Transliterates Devanagari consonants and independent vowels to Latin equivalents,
 * preserves initial vowels while stripping subsequent vowels,
 * normalizes retroflex consonants to canonical dental tokens,
 * collapses aspirated consonant digraphs and sibilants (bh->b, kh->k, th->t, ph->p, gh->g, ch->c, jh->j, dh->d, sh->s),
 * collapses geminates ((.)\1+ -> $1), strips non-letters, and returns an up-to-8-character skeleton.
 *
 * Example equivalence:
 * buildIndicPhoneticSkeleton("रमेश पाटील") === buildIndicPhoneticSkeleton("Ramesh Patil") === "rmsptl"
 * buildIndicPhoneticSkeleton("अनिल") === buildIndicPhoneticSkeleton("Anil") === "anl"
 */
export function buildIndicPhoneticSkeleton(name: string): string {
  if (!name || typeof name !== "string") return "";

  const devanagariMap: Record<string, string> = {
    // Independent vowels (BUG-20)
    "अ": "a", "आ": "a", "इ": "i", "ई": "i", "उ": "u", "ऊ": "u", "ऋ": "r",
    "ए": "e", "ऐ": "e", "ओ": "o", "औ": "o",
    // Consonants with retroflex normalization
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "n",
    "च": "c", "छ": "ch", "ज": "j", "झ": "jh", "ञ": "n",
    "ट": "t", "ठ": "t", "ड": "d", "ढ": "d", "ण": "n",
    "ड़": "d", "ढ़": "d",
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

  const cleaned = transliterated.replace(/[^a-z]/gi, "").toLowerCase();
  if (!cleaned) return "";

  // Retain initial vowel if name starts with a vowel (BUG-20)
  const startsWithVowel = /^[aeiou]/.test(cleaned);
  const initialVowel = startsWithVowel ? cleaned[0]! : "";
  const rest = cleaned.slice(startsWithVowel ? 1 : 0);
  let consonants = rest.replace(/[aeiouyāīū]/gi, "");

  // If no consonants exist anywhere, return empty string ('A' -> '')
  if (consonants.length === 0) {
    return "";
  }

  let skeleton = initialVowel + consonants;

  // Collapse aspirated digraphs and sibilants
  const digraphs: [RegExp, string][] = [
    [/bh/g, "b"], [/kh/g, "k"], [/th/g, "t"], [/ph/g, "p"],
    [/gh/g, "g"], [/ch/g, "c"], [/jh/g, "j"], [/dh/g, "d"],
    [/sh/g, "s"]
  ];
  for (const [pattern, replacement] of digraphs) {
    skeleton = skeleton.replace(pattern, replacement);
  }

  // Collapse geminate duplicate consonants (e.g. tt -> t, pp -> p)
  skeleton = skeleton.replace(/(.)\1+/g, "$1");

  return skeleton.replace(/[^a-z]/g, "").slice(0, 8);
}

export {
  parseAbhaQr,
  parseAbhaQrPayload,
  parsePatientQrPayload,
  type ParsedAbhaQr,
  type ParsedQrIdentity,
} from "./abhaScanner.js";
