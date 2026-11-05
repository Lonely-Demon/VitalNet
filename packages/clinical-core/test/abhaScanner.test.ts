import { describe, expect, it } from "vitest";
import {
  parseAbhaQr,
  parseAbhaQrPayload,
  parsePatientQrPayload,
} from "../src/abhaScanner.js";
import { deriveDeterministicPatientKey, deriveAbhaKey } from "../src/patientKey.js";
import { PATIENT_KEY_RE } from "../src/schema.js";

describe("ABDM ABHA QR Scanner Parser (ADR §49)", () => {
  it("parses ABDM ABHA QR v3 JSON payload extracting key demographics and deterministic keys", () => {
    const abhaJson = JSON.stringify({
      hidn: "91-2345-6789-0123",
      name: "Sunita Deshmukh",
      gender: "F",
      dob: "15/06/1996",
      address: "Pune, Maharashtra",
      mobile: "9876543210",
    });

    const parsed = parseAbhaQr(abhaJson);
    expect(parsed).not.toBeNull();
    expect(parsed!.source).toBe("abdm_abha");
    expect(parsed!.version).toBe("v3");
    expect(parsed!.hidn).toBe("91234567890123");
    expect(parsed!.patientName).toBe("Sunita Deshmukh");
    expect(parsed!.patientSex).toBe("female");
    expect(PATIENT_KEY_RE.test(parsed!.patientKey)).toBe(true);
    expect(parsed!.patientKey).toBe(deriveDeterministicPatientKey("abha", "91234567890123"));
    expect(parsed!.abhaKey).toBe(deriveAbhaKey("91234567890123"));

    const currentYear = new Date().getFullYear();
    expect(parsed!.patientAge).toBe(currentYear - 1996);
  });

  it("handles numeric yob field in ABDM ABHA JSON", () => {
    const abhaJson = JSON.stringify({
      hidn: "91-8888-7777-6666",
      name: "Rajesh Kumar",
      gender: "MALE",
      yob: 1985,
    });

    const parsed = parseAbhaQr(abhaJson);
    expect(parsed).not.toBeNull();
    expect(parsed!.patientSex).toBe("male");
    expect(parsed!.patientName).toBe("Rajesh Kumar");
    const currentYear = new Date().getFullYear();
    expect(parsed!.patientAge).toBe(currentYear - 1985);
  });

  it("parses legacy delimited ABHA QR payloads", () => {
    const legacyQr = "91-1234-5678-9012|Amitabh Verma|M|1975";
    const parsed = parseAbhaQr(legacyQr);
    expect(parsed).not.toBeNull();
    expect(parsed!.source).toBe("legacy");
    expect(parsed!.version).toBe("legacy");
    expect(parsed!.hidn).toBe("91123456789012");
    expect(parsed!.patientName).toBe("Amitabh Verma");
    expect(parsed!.patientSex).toBe("male");
    expect(PATIENT_KEY_RE.test(parsed!.patientKey)).toBe(true);
  });

  it("parses raw VitalNet QR key directly", () => {
    const rawKey = "2345-6789";
    const parsed = parseAbhaQr(rawKey);
    expect(parsed).not.toBeNull();
    expect(parsed!.patientKey).toBe("2345-6789");
    expect(parsed!.source).toBe("vitalnet_qr");
    expect(parsed!.version).toBe("raw");
  });

  it("supports parsePatientQrPayload backward compatibility interface", () => {
    const abhaJson = JSON.stringify({
      hidn: "91-2345-6789-0123",
      name: "Sunita Deshmukh",
      gender: "F",
      dob: "15/06/1996",
    });

    const parsed = parsePatientQrPayload(abhaJson);
    expect(parsed).not.toBeNull();
    expect(parsed!.source).toBe("abha_qr");
    expect(PATIENT_KEY_RE.test(parsed!.patientKey)).toBe(true);
    expect(parsed!.patientName).toBe("Sunita Deshmukh");
    expect(parsed!.patientSex).toBe("female");
  });

  it("returns null for malformed, empty, or short HIDN payloads", () => {
    expect(parseAbhaQr("")).toBeNull();
    expect(parseAbhaQr("   ")).toBeNull();
    expect(parseAbhaQr("invalid payload without key")).toBeNull();
    expect(parseAbhaQr(JSON.stringify({ hidn: "123" }))).toBeNull(); // HIDN < 8 chars
    expect(parseAbhaQr("{ malformed json }")).toBeNull();
  });
});
