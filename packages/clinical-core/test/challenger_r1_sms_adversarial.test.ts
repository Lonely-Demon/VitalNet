/**
 * Challenger 1: Empirical Adversarial Verification of SMS Codec (REG-01)
 *
 * Verifies:
 * 1. Byte space stress testing across all 256 values (0..255) for byte 17.
 * 2. Exact sub-year boundaries: 0, 1, 2, 3, 11, 12, 23, 24 months.
 * 3. Clinical safety: True neonates (0..2 months) with fever (>=38.0C) trigger neonatal_fever EMERGENCY override.
 * 4. Backward compatibility: Legacy byte 254 decodes to patient_age 0, age_months 6 without firing neonatal_fever.
 * 5. Corrupted, truncated, and adversarial payloads fail closed.
 */

import { describe, it, expect } from "vitest";
import {
  encodeEmergencySms,
  decodeEmergencySms,
  computeCrc24,
  base64UrlEncode,
  base64UrlDecode,
  type SmsFrameInput,
} from "../src/smsCodec.js";
import { assignTier, type EngineInput } from "../src/rules/engine.js";

describe("Challenger 1 — Empirical SMS Codec Adversarial Verification", () => {
  const TEST_UUID = "12345678-1234-5678-1234-567812345678";

  function createFrameWithAgeByte(ageByte: number): string {
    const buf = new Uint8Array(28);
    // UUID bytes 0..15
    for (let i = 0; i < 16; i++) buf[i] = i;
    // Byte 16: version 1, sex male (0), not pregnant (0), tier routine (0)
    buf[16] = (1 & 0x7) << 5;
    // Byte 17: Age byte under test
    buf[17] = ageByte & 0xff;
    // Bytes 18..24: All 0 (no symptoms, no vitals)
    for (let i = 18; i <= 24; i++) buf[i] = 0;
    // Bytes 25..27: CRC24
    const crc = computeCrc24(buf, 25);
    buf[25] = (crc >> 16) & 0xff;
    buf[26] = (crc >> 8) & 0xff;
    buf[27] = crc & 0xff;
    return `VN1:${base64UrlEncode(buf)}`;
  }

  describe("1. Exhaustive Byte Space Stress Test (0..255 for Byte 17)", () => {
    it("correctly decodes every byte from 0 to 255 without throwing or producing NaN", () => {
      for (let b = 0; b <= 255; b++) {
        const frame = createFrameWithAgeByte(b);
        const decoded = decodeEmergencySms(frame);

        expect(Number.isNaN(decoded.patient_age)).toBe(false);

        if (b >= 200 && b <= 223) {
          // Sub-year / toddler range: 0..23 months
          const expectedMonths = b - 200;
          const expectedYears = Math.floor(expectedMonths / 12);
          expect(decoded.age_months).toBe(expectedMonths);
          expect(decoded.patient_age).toBe(expectedYears);
        } else if (b === 254) {
          // Legacy sentinel
          expect(decoded.patient_age).toBe(0);
          expect(decoded.age_months).toBe(6);
        } else {
          // Normal year range or unmapped sentinel: decoded as raw byte years, age_months null
          expect(decoded.patient_age).toBe(b);
          expect(decoded.age_months).toBeNull();
        }
      }
    });
  });

  describe("2. Sub-Year Boundaries Matrix (0, 1, 2, 3, 11, 12, 23, 24 months)", () => {
    const boundaryMatrix = [
      { months: 0, expectedYears: 0, expectedByte: 200, label: "Neonate day 0 (0 months)" },
      { months: 1, expectedYears: 0, expectedByte: 201, label: "Neonate 1 month" },
      { months: 2, expectedYears: 0, expectedByte: 202, label: "Neonate 2 months" },
      { months: 3, expectedYears: 0, expectedByte: 203, label: "Post-neonate infant 3 months" },
      { months: 11, expectedYears: 0, expectedByte: 211, label: "Infant 11 months" },
      { months: 12, expectedYears: 1, expectedByte: 212, label: "1-year toddler 12 months" },
      { months: 23, expectedYears: 1, expectedByte: 223, label: "Toddler 23 months (upper boundary)" },
      { months: 24, expectedYears: 2, expectedByte: 2, label: "Child 24 months (2 years)" },
    ];

    for (const { months, expectedYears, expectedByte, label } of boundaryMatrix) {
      it(`encodes and decodes ${label} properly`, () => {
        const input: SmsFrameInput = {
          client_id: TEST_UUID,
          age_months: months,
          patient_age: expectedYears,
          symptoms: [],
        };
        const encoded = encodeEmergencySms(input);
        const rawBytes = base64UrlDecode(encoded.slice(4));
        expect(rawBytes[17]).toBe(expectedByte);

        const decoded = decodeEmergencySms(encoded);
        expect(decoded.patient_age).toBe(expectedYears);
        if (months <= 23) {
          expect(decoded.age_months).toBe(months);
        } else {
          expect(decoded.age_months).toBeNull();
        }
      });
    }

    it("handles fractional patient_age when age_months is omitted", () => {
      // 0.25 years = 3 months -> byte 203
      const input3m: SmsFrameInput = {
        client_id: TEST_UUID,
        patient_age: 0.25,
        symptoms: [],
      };
      const enc3m = encodeEmergencySms(input3m);
      const dec3m = decodeEmergencySms(enc3m);
      expect(dec3m.age_months).toBe(3);
      expect(dec3m.patient_age).toBe(0);

      // 0.0833 years = 1 month -> byte 201
      const input1m: SmsFrameInput = {
        client_id: TEST_UUID,
        patient_age: 0.0833,
        symptoms: [],
      };
      const enc1m = encodeEmergencySms(input1m);
      const dec1m = decodeEmergencySms(enc1m);
      expect(dec1m.age_months).toBe(1);
      expect(dec1m.patient_age).toBe(0);

      // 0.5 years = 6 months -> byte 206
      const input6m: SmsFrameInput = {
        client_id: TEST_UUID,
        patient_age: 0.5,
        symptoms: [],
      };
      const enc6m = encodeEmergencySms(input6m);
      const dec6m = decodeEmergencySms(enc6m);
      expect(dec6m.age_months).toBe(6);
      expect(dec6m.patient_age).toBe(0);
    });
  });

  describe("3. Clinical Safety: Neonatal Fever Emergency Rule Override", () => {
    it("triggers neonatal_fever EMERGENCY for true neonates (0..2 months) with fever >= 38.0C", () => {
      const neonateMonths = [0, 1, 2];

      for (const m of neonateMonths) {
        const input: SmsFrameInput = {
          client_id: TEST_UUID,
          age_months: m,
          patient_age: 0,
          temperature: 38.5,
          symptoms: ["fever"],
        };

        const encoded = encodeEmergencySms(input);
        const decoded = decodeEmergencySms(encoded);

        const engineInput: EngineInput = {
          patient_age: decoded.patient_age,
          age_months: decoded.age_months,
          temperature: decoded.temperature,
          symptoms: decoded.symptoms,
          bp_systolic: decoded.bp_systolic,
          bp_diastolic: decoded.bp_diastolic,
          spo2: decoded.spo2,
          heart_rate: decoded.heart_rate,
          is_pregnant: decoded.is_pregnant,
          patient_sex: decoded.patient_sex,
        };

        const result = assignTier(engineInput);
        expect(result.tier).toBe("EMERGENCY");
        const hasNeonatalFever = result.firedRules.some((r) => r.id === "neonatal_fever");
        expect(hasNeonatalFever).toBe(true);
      }
    });

    it("does NOT trigger neonatal_fever for 3-month-old infant with fever 38.0C (effective age 0.25)", () => {
      const input: SmsFrameInput = {
        client_id: TEST_UUID,
        age_months: 3,
        patient_age: 0,
        temperature: 38.0,
        symptoms: ["fever"],
      };

      const encoded = encodeEmergencySms(input);
      const decoded = decodeEmergencySms(encoded);

      const engineInput: EngineInput = {
        patient_age: decoded.patient_age,
        age_months: decoded.age_months,
        temperature: decoded.temperature,
        symptoms: decoded.symptoms,
      };

      const result = assignTier(engineInput);
      const hasNeonatalFever = result.firedRules.some((r) => r.id === "neonatal_fever");
      expect(hasNeonatalFever).toBe(false);
    });

    it("tests neonatal temperature boundary: 37.9C does not fire, 38.0C fires", () => {
      // 1 month neonate at 37.9C
      const inputSub: SmsFrameInput = {
        client_id: TEST_UUID,
        age_months: 1,
        patient_age: 0,
        temperature: 37.9,
        symptoms: [],
      };
      const decSub = decodeEmergencySms(encodeEmergencySms(inputSub));
      const resSub = assignTier({
        patient_age: decSub.patient_age,
        age_months: decSub.age_months,
        temperature: decSub.temperature,
        symptoms: [],
      });
      expect(resSub.firedRules.some((r) => r.id === "neonatal_fever")).toBe(false);

      // 1 month neonate at 38.0C
      const inputCrit: SmsFrameInput = {
        client_id: TEST_UUID,
        age_months: 1,
        patient_age: 0,
        temperature: 38.0,
        symptoms: [],
      };
      const decCrit = decodeEmergencySms(encodeEmergencySms(inputCrit));
      const resCrit = assignTier({
        patient_age: decCrit.patient_age,
        age_months: decCrit.age_months,
        temperature: decCrit.temperature,
        symptoms: [],
      });
      expect(resCrit.firedRules.some((r) => r.id === "neonatal_fever")).toBe(true);
      expect(resCrit.tier).toBe("EMERGENCY");
    });

    it("verifies legacy byte 254 decodes to 6 months and does NOT fire neonatal_fever", () => {
      const legacyFrame = createFrameWithAgeByte(254);
      const decoded = decodeEmergencySms(legacyFrame);

      expect(decoded.patient_age).toBe(0);
      expect(decoded.age_months).toBe(6);

      // With temp 38.5C
      const res = assignTier({
        patient_age: decoded.patient_age,
        age_months: decoded.age_months,
        temperature: 38.5,
        symptoms: [],
      });
      // 6-month-old infant is not a neonate (<3m), so neonatal_fever must NOT fire
      expect(res.firedRules.some((r) => r.id === "neonatal_fever")).toBe(false);
    });
  });

  describe("4. Adversarial Malformed Frames & Edge Cases", () => {
    it("rejects truncated frames (< 33 base64 characters)", () => {
      expect(() => decodeEmergencySms("VN1:short")).toThrow(/Malformed or truncated VN1 frame/);
    });

    it("rejects frames without VN1: prefix", () => {
      const validFrame = createFrameWithAgeByte(200);
      const noPrefix = validFrame.slice(4);
      expect(() => decodeEmergencySms(noPrefix)).toThrow(/must start with VN1:/);
    });

    it("rejects corrupted checksums", () => {
      const validFrame = createFrameWithAgeByte(201);
      const buf = base64UrlDecode(validFrame.slice(4));
      // Corrupt CRC byte
      buf[27] = (buf[27]! ^ 0xff) & 0xff;
      const corruptFrame = `VN1:${base64UrlEncode(buf)}`;
      expect(() => decodeEmergencySms(corruptFrame)).toThrow(/CRC24 integrity check failed/);
    });

    it("rejects unsupported frame version", () => {
      const buf = new Uint8Array(28);
      // Byte 16: version 2
      buf[16] = (2 & 0x7) << 5;
      const crc = computeCrc24(buf, 25);
      buf[25] = (crc >> 16) & 0xff;
      buf[26] = (crc >> 8) & 0xff;
      buf[27] = crc & 0xff;
      const v2Frame = `VN1:${base64UrlEncode(buf)}`;
      expect(() => decodeEmergencySms(v2Frame)).toThrow(/Unsupported VN1 frame version/);
    });
  });
});
