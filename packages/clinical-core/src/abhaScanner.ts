// Offline ABDM ABHA QR scanner parser (ADR §49).
// Parses official Ayushman Bharat Digital Mission (ABDM) ABHA QR payloads (v3 and legacy formats),
// extracting patient demographics and mapping HIDN deterministically into a schema-valid patientKey.

import { PATIENT_KEY_RE } from "./schema.js";
import { deriveAbhaKey, deriveDeterministicPatientKey } from "./patientKey.js";

export interface ParsedAbhaQr {
  patientKey: string;
  abhaKey?: string;
  hidn?: string;
  abhaNumber?: string;
  patientName?: string;
  name?: string;
  patientSex?: "male" | "female" | "other";
  gender?: "male" | "female" | "other";
  patientAge?: number;
  age?: number;
  dob?: string;
  yob?: number;
  source: "abdm_abha" | "vitalnet_qr" | "legacy";
  version: "v3" | "legacy" | "raw";
}

export interface ParsedQrIdentity {
  patientKey: string;
  patientName?: string;
  patientAge?: number;
  patientSex?: "male" | "female" | "other";
  source: "vitalnet_qr" | "abha_qr" | "abdm_abha" | "legacy";
  hidn?: string;
}

/**
 * Parses an offline QR string representing an ABDM ABHA QR card (v3 JSON or legacy delimited)
 * or a plain VitalNet patient continuity key.
 */
export function parseAbhaQr(qrText: string): ParsedAbhaQr | null {
  if (!qrText || typeof qrText !== "string") return null;
  const trimmed = qrText.trim();

  // 1. Direct VitalNet key check ("XXXX-XXXX")
  if (PATIENT_KEY_RE.test(trimmed.toUpperCase())) {
    const key = trimmed.toUpperCase();
    return {
      patientKey: key,
      source: "vitalnet_qr",
      version: "raw",
    };
  }

  // 2. ABDM ABHA QR v3 (JSON format)
  if (trimmed.startsWith("{") && trimmed.endsWith("}")) {
    try {
      const data = JSON.parse(trimmed) as Record<string, unknown>;
      const rawHidn = String(
        data.hidn || data.abhaNumber || data.healthIdNumber || data.phr || data.id || ""
      );
      const sanitizedHidn = rawHidn.replace(/[^0-9A-Za-z]/g, "");
      if (sanitizedHidn.length < 8) return null;

      const patientKey = deriveDeterministicPatientKey("abha", sanitizedHidn);
      const abhaKey = deriveAbhaKey(sanitizedHidn);
      const name = typeof data.name === "string" ? data.name.trim().slice(0, 100) : undefined;

      const rawGender = String(data.gender || data.sex || "").toUpperCase();
      let gender: "male" | "female" | "other" | undefined;
      if (rawGender === "M" || rawGender === "MALE") gender = "male";
      else if (rawGender === "F" || rawGender === "FEMALE") gender = "female";
      else if (rawGender) gender = "other";

      let age: number | undefined;
      const currentYear = new Date().getFullYear();
      let yob: number | undefined;
      let dob: string | undefined;

      if (typeof data.yob === "number") {
        yob = data.yob;
        age = Math.max(0, currentYear - yob);
      } else if (typeof data.dob === "string") {
        dob = data.dob.trim();
        const parts = dob.split(/[/.-]/);
        if (parts.length === 3) {
          const parsedYear = Number.parseInt(parts[2]!, 10);
          if (!Number.isNaN(parsedYear) && parsedYear > 1900 && parsedYear <= currentYear) {
            yob = parsedYear;
            age = Math.max(0, currentYear - parsedYear);
          }
        }
      }

      if (age === undefined) {
        const yearMatch = String(data.dob || data.yob || "").match(/\b(19\d{2}|20\d{2})\b/);
        if (yearMatch) {
          const parsed = Number.parseInt(yearMatch[1]!, 10);
          yob = parsed;
          age = Math.max(0, currentYear - parsed);
        }
      }

      return {
        patientKey,
        abhaKey,
        hidn: sanitizedHidn,
        abhaNumber: sanitizedHidn,
        patientName: name,
        name,
        patientSex: gender,
        gender,
        patientAge: age,
        age,
        dob,
        yob,
        source: "abdm_abha",
        version: "v3",
      };
    } catch {
      return null;
    }
  }

  // 3. Legacy ABDM QR formats (pipe or comma delimited: HIDN|Name|Gender|DOB or CSV)
  const delimiters = ["|", ","];
  for (const delim of delimiters) {
    if (trimmed.includes(delim)) {
      const parts = trimmed.split(delim).map((p) => p.trim());
      // Expecting at least [HIDN, Name, Gender, ...]
      const candidateHidn = parts[0]?.replace(/[^0-9A-Za-z]/g, "") ?? "";
      if (candidateHidn.length >= 8) {
        const patientKey = deriveDeterministicPatientKey("abha", candidateHidn);
        const abhaKey = deriveAbhaKey(candidateHidn);
        const name = parts[1] || undefined;
        const gRaw = (parts[2] || "").toUpperCase();
        const gender =
          gRaw === "M" || gRaw === "MALE"
            ? "male"
            : gRaw === "F" || gRaw === "FEMALE"
            ? "female"
            : gRaw
            ? "other"
            : undefined;

        let age: number | undefined;
        let dob: string | undefined;
        let yob: number | undefined;
        if (parts[3]) {
          dob = parts[3];
          const yearMatch = dob.match(/\b(19\d{2}|20\d{2})\b/);
          if (yearMatch) {
            yob = Number.parseInt(yearMatch[1]!, 10);
            age = Math.max(0, new Date().getFullYear() - yob);
          }
        }

        return {
          patientKey,
          abhaKey,
          hidn: candidateHidn,
          abhaNumber: candidateHidn,
          patientName: name,
          name,
          patientSex: gender,
          gender,
          patientAge: age,
          age,
          dob,
          yob,
          source: "legacy",
          version: "legacy",
        };
      }
    }
  }

  return null;
}

/**
 * Backward-compatible helper conforming to test_adr49_continuity.js:
 * returns { patientKey, patientName, patientSex, patientAge, hidn, source }.
 */
export function parseAbhaQrPayload(rawQrText: string): (ParsedAbhaQr & { source: "abdm_abha" | "vitalnet_qr" | "legacy" }) | null {
  return parseAbhaQr(rawQrText);
}

/**
 * Backward-compatible helper conforming to Section 3.3 / Section 12.1 in spec:
 * returns ParsedQrIdentity.
 */
export function parsePatientQrPayload(rawQrText: string): ParsedQrIdentity | null {
  const parsed = parseAbhaQr(rawQrText);
  if (!parsed) return null;
  return {
    patientKey: parsed.patientKey,
    ...(parsed.patientName ? { patientName: parsed.patientName } : {}),
    ...(parsed.patientAge !== undefined ? { patientAge: parsed.patientAge } : {}),
    ...(parsed.patientSex ? { patientSex: parsed.patientSex } : {}),
    source: parsed.source === "abdm_abha" ? "abha_qr" : parsed.source,
    ...(parsed.hidn ? { hidn: parsed.hidn } : {}),
  };
}
