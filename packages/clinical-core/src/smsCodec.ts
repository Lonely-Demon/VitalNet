// 28-Byte Authenticated Compact Emergency SMS Codec (ADR §51).
// Encodes and decodes 28-byte binary frames to/from "VN1:<Base64url>" (42 ASCII characters)
// with CRC24 error detection, transmitting zero PII and fitting within a single 160-char SMS.

import { ALLOWED_SYMPTOMS, type Symptom } from "./schema.js";
import type { Tier } from "./rules/engine.js";

export interface SmsFrameInput {
  client_id?: string;
  clientId?: string;
  patient_age?: number;
  patientAge?: number;
  age?: number;
  age_months?: number | null;
  ageMonths?: number | null;
  patient_sex?: "male" | "female" | "other" | string;
  patientSex?: "male" | "female" | "other" | string;
  sex?: "male" | "female" | "other" | string;
  is_pregnant?: boolean | null;
  isPregnant?: boolean | null;
  triage_level?: Tier | string;
  triageTier?: Tier | string;
  tier?: Tier | string;
  symptoms: readonly string[];
  bp_systolic?: number | null;
  bpSystolic?: number | null;
  bp_diastolic?: number | null;
  bpDiastolic?: number | null;
  spo2?: number | null;
  heart_rate?: number | null;
  heartRate?: number | null;
  temperature?: number | null;
}

export interface DecodedSmsFrame {
  client_id: string;
  clientId: string;
  patient_age: number;
  patientAge: number;
  age_months?: number | null;
  ageMonths?: number | null;
  patient_sex: "male" | "female" | "other";
  patientSex: "male" | "female" | "other";
  sex?: "male" | "female" | "other";
  is_pregnant: boolean;
  isPregnant: boolean;
  triage_level: Tier;
  triageTier: Tier;
  tier?: Tier;
  symptoms: Symptom[];
  bp_systolic: number | null;
  bpSystolic: number | null;
  bp_diastolic: number | null;
  bpDiastolic: number | null;
  spo2: number | null;
  heart_rate: number | null;
  heartRate: number | null;
  temperature: number | null;
  version: number;
}

export const CRC24_INIT = 0xb704ce;
export const CRC24_POLY = 0x1864cfb;

/**
 * Computes CRC-24-Radix64 over a Uint8Array.
 */
export function computeCrc24(bytes: Uint8Array, length: number = bytes.length): number {
  let crc = CRC24_INIT;
  for (let i = 0; i < length; i++) {
    crc ^= bytes[i]! << 16;
    for (let j = 0; j < 8; j++) {
      crc <<= 1;
      if (crc & 0x1000000) {
        crc ^= CRC24_POLY;
      }
    }
  }
  return crc & 0xffffff;
}

export function uuidToBytes(uuidStr: string): Uint8Array {
  const hex = (uuidStr || "").replace(/-/g, "");
  if (hex.length !== 32) {
    throw new Error(`InvalidUUID: Expected 32 hex chars, got ${hex.length}`);
  }
  const bytes = new Uint8Array(16);
  for (let i = 0; i < 16; i++) {
    bytes[i] = Number.parseInt(hex.slice(i * 2, i * 2 + 2), 16);
  }
  return bytes;
}

export function bytesToUuid(bytes: Uint8Array): string {
  const hex: string[] = [];
  for (let i = 0; i < 16; i++) {
    hex.push(bytes[i]!.toString(16).padStart(2, "0"));
  }
  return `${hex.slice(0, 4).join("")}-${hex.slice(4, 6).join("")}-${hex.slice(6, 8).join("")}-${hex.slice(8, 10).join("")}-${hex.slice(10, 16).join("")}`;
}

export function base64UrlEncode(bytes: Uint8Array): string {
  let binary = "";
  for (let i = 0; i < bytes.length; i++) {
    binary += String.fromCharCode(bytes[i]!);
  }
  const base64 = globalThis.btoa(binary);
  return base64.replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export function base64UrlDecode(str: string): Uint8Array {
  let base64 = str.replace(/-/g, "+").replace(/_/g, "/");
  while (base64.length % 4 !== 0) {
    base64 += "=";
  }
  const binary = globalThis.atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

// Symptom alias mapping for abbreviated or alternate symptom names
const SYMPTOM_ALIASES: Record<string, Symptom> = {
  abdominal_pain: "severe_abdominal_pain",
  severe_abdominal_pain: "severe_abdominal_pain",
  headache: "severe_headache",
  severe_headache: "severe_headache",
  vomiting_diarrhea: "persistent_vomiting",
  persistent_vomiting: "persistent_vomiting",
  focal_weakness: "weakness_one_side",
  weakness_one_side: "weakness_one_side",
};

/**
 * Encodes SMS frame input into 28-byte binary frame with CRC24 and returns "VN1:<Base64url>"
 */
export function encodeEmergencySms(input: SmsFrameInput): string {
  const buf = new Uint8Array(28);

  // Bytes 0..15: Client UUID
  const clientId = input.client_id || input.clientId || "00000000-0000-0000-0000-000000000000";
  const uuidBytes = uuidToBytes(clientId);
  buf.set(uuidBytes, 0);

  // Byte 16: Version (bits 7..5), Sex (bits 4..3), Pregnant (bit 2), Tier (bits 1..0)
  const version = 1;
  const rawSex = input.patient_sex ?? input.patientSex ?? input.sex ?? "male";
  const normalizedSex = String(rawSex).toLowerCase();
  let sexCode = 0;
  if (normalizedSex === "female") sexCode = 1;
  else if (normalizedSex === "other") sexCode = 2;

  const isPregnant = Boolean(input.is_pregnant ?? input.isPregnant);
  const pregCode = isPregnant ? 1 : 0;

  const rawTier = input.triage_level ?? input.triageTier ?? input.tier ?? "ROUTINE";
  const normalizedTier = String(rawTier).toUpperCase();
  let tierCode = 0;
  if (normalizedTier === "URGENT") tierCode = 1;
  else if (normalizedTier === "EMERGENCY") tierCode = 2;

  buf[16] = ((version & 0x7) << 5) | ((sexCode & 0x3) << 3) | ((pregCode & 0x1) << 2) | (tierCode & 0x3);

  // Byte 17: Patient Age (0..120 years, or 200..223 for sub-year/toddler 0..23 months, or 254 legacy sentinel)
  const rawAgeMonths = input.age_months ?? input.ageMonths;
  const rawAge = input.patient_age ?? input.patientAge ?? input.age;

  if (rawAgeMonths != null && rawAgeMonths >= 0 && rawAgeMonths <= 23) {
    buf[17] = 200 + Math.round(rawAgeMonths);
  } else if (rawAgeMonths == null && rawAge != null && rawAge > 0 && rawAge < 1) {
    const derivedMonths = Math.min(23, Math.max(0, Math.round(rawAge * 12)));
    buf[17] = 200 + derivedMonths;
  } else {
    const age = rawAge ?? 0;
    buf[17] = Math.min(120, Math.max(0, Math.round(age)));
  }

  // Bytes 18..19: Symptom Mask (16 bits)
  let mask = 0;
  if (Array.isArray(input.symptoms)) {
    for (const rawS of input.symptoms) {
      const canonical = SYMPTOM_ALIASES[rawS] || rawS;
      const idx = ALLOWED_SYMPTOMS.indexOf(canonical as Symptom);
      if (idx >= 0 && idx < 12) {
        mask |= 1 << idx;
      }
    }
  }
  buf[18] = (mask >> 8) & 0xff;
  buf[19] = mask & 0xff;

  // Byte 20: SBP (0 = null; 1..250 = SBP - 20)
  const sbp = input.bp_systolic ?? input.bpSystolic;
  if (sbp != null && sbp >= 21 && sbp <= 270) {
    buf[20] = Math.max(1, Math.min(250, Math.round(sbp) - 20));
  } else {
    buf[20] = 0;
  }

  // Byte 21: DBP (0 = null; 1..200 = DBP)
  const dbp = input.bp_diastolic ?? input.bpDiastolic;
  if (dbp != null && dbp >= 1 && dbp <= 200) {
    buf[21] = Math.max(1, Math.min(200, Math.round(dbp)));
  } else {
    buf[21] = 0;
  }

  // Byte 22: SpO2 (0 = null; 50..100 = SpO2)
  const spo2 = input.spo2;
  if (spo2 != null && spo2 >= 50 && spo2 <= 100) {
    buf[22] = Math.max(50, Math.min(100, Math.round(spo2)));
  } else {
    buf[22] = 0;
  }

  // Byte 23: Heart Rate (0 = null; 10..250 = HR)
  const hr = input.heart_rate ?? input.heartRate;
  if (hr != null && hr >= 10 && hr <= 250) {
    buf[23] = Math.max(10, Math.min(250, Math.round(hr)));
  } else {
    buf[23] = 0;
  }

  // Byte 24: Temp (0 = null; 1..200 = round((Temp - 25.0) * 10))
  const temp = input.temperature;
  if (temp != null && temp >= 25.1 && temp <= 45.0) {
    buf[24] = Math.max(1, Math.min(200, Math.round((temp - 25.0) * 10)));
  } else {
    buf[24] = 0;
  }

  // Bytes 25..27: CRC24 Checksum over bytes 0..24
  const crc = computeCrc24(buf, 25);
  buf[25] = (crc >> 16) & 0xff;
  buf[26] = (crc >> 8) & 0xff;
  buf[27] = crc & 0xff;

  return `VN1:${base64UrlEncode(buf)}`;
}

export const encodeEmergencySmsFrame = encodeEmergencySms;

/**
 * Decodes "VN1:<Base64url>" into structured SMS payload verifying CRC24.
 */
export function decodeEmergencySms(frameText: string): DecodedSmsFrame {
  if (!frameText || typeof frameText !== "string") {
    throw new Error("InvalidSmsFrame: Frame text must be non-empty string");
  }

  const trimmed = frameText.trim();
  let base64Part: string | null = null;
  const directMatch = trimmed.match(/^VN1:([A-Za-z0-9_-]{37,39})$/);
  if (directMatch) {
    base64Part = directMatch[1]!;
  } else {
    const embeddedMatch = trimmed.match(/(?:^|[\s\[(])VN1:([A-Za-z0-9_-]{37,39})(?=[\])\s]|$)/);
    if (embeddedMatch) {
      base64Part = embeddedMatch[1]!;
    }
  }

  if (!base64Part) {
    const vn1Idx = frameText.indexOf("VN1:");
    if (vn1Idx !== -1) {
      const rest = frameText.slice(vn1Idx + 4).trim().split(/[\s\])]/)[0]!;
      throw new Error(
        `InvalidSmsFrame: Malformed or truncated VN1 frame (payload length ${rest.length}, expected 37..39 Base64url chars)`
      );
    }
    throw new Error("InvalidSmsFrame: No VN1 emergency frame found in SMS body (must start with VN1:)");
  }

  const buf = base64UrlDecode(base64Part);

  if (buf.length !== 28) {
    throw new Error(`InvalidSmsFrame: Expected 28 bytes binary, got ${buf.length}`);
  }

  // Verify CRC24
  const expectedCrc = computeCrc24(buf, 25);
  const actualCrc = (buf[25]! << 16) | (buf[26]! << 8) | buf[27]!;

  if (expectedCrc !== actualCrc) {
    throw new Error(
      `CRC24 integrity check failed: expected 0x${expectedCrc.toString(16)}, got 0x${actualCrc.toString(16)}`
    );
  }

  const clientId = bytesToUuid(buf.subarray(0, 16));

  const flags = buf[16]!;
  const version = (flags >> 5) & 0x7;
  if (version !== 1) {
    throw new Error(`Unsupported VN1 frame version: ${version}`);
  }

  const sexCode = (flags >> 3) & 0x3;
  const pregCode = (flags >> 2) & 0x1;
  const tierCode = flags & 0x3;

  const patientSex = sexCode === 1 ? "female" : sexCode === 2 ? "other" : "male";
  const isPregnant = pregCode === 1;
  const triageTier: Tier = tierCode === 2 ? "EMERGENCY" : tierCode === 1 ? "URGENT" : "ROUTINE";

  const rawAgeByte = buf[17]!;
  let patientAge: number;
  let ageMonths: number | null = null;
  if (rawAgeByte >= 200 && rawAgeByte <= 223) {
    ageMonths = rawAgeByte - 200;
    patientAge = Math.floor(ageMonths / 12);
  } else if (rawAgeByte === 254) {
    patientAge = 0;
    ageMonths = 6;
  } else {
    patientAge = rawAgeByte;
  }

  const mask = (buf[18]! << 8) | buf[19]!;
  const symptoms: Symptom[] = [];
  for (let i = 0; i < 12; i++) {
    if ((mask & (1 << i)) !== 0) {
      symptoms.push(ALLOWED_SYMPTOMS[i]!);
    }
  }

  const bpSystolic = buf[20] === 0 ? null : buf[20]! + 20;
  const bpDiastolic = buf[21] === 0 ? null : buf[21]!;
  const spo2 = buf[22] === 0 ? null : buf[22]!;
  const heartRate = buf[23] === 0 ? null : buf[23]!;
  const temperature = buf[24] === 0 ? null : Math.round((25.0 + buf[24]! / 10.0) * 10) / 10;

  return {
    clientId,
    client_id: clientId,
    patientAge,
    patient_age: patientAge,
    ageMonths,
    age_months: ageMonths,
    patientSex,
    patient_sex: patientSex,
    sex: patientSex,
    isPregnant,
    is_pregnant: isPregnant,
    triageTier,
    triage_level: triageTier,
    tier: triageTier,
    symptoms,
    bpSystolic,
    bp_systolic: bpSystolic,
    bpDiastolic,
    bp_diastolic: bpDiastolic,
    spo2,
    heartRate,
    heart_rate: heartRate,
    temperature,
    version,
  };
}

export const decodeEmergencySmsFrame = decodeEmergencySms;
