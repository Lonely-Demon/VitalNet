import { describe, expect, it } from "vitest";
import {
  encodeEmergencySms,
  encodeEmergencySmsFrame,
  decodeEmergencySms,
  decodeEmergencySmsFrame,
  computeCrc24,
  uuidToBytes,
  bytesToUuid,
  base64UrlEncode,
  type SmsFrameInput,
} from "../src/smsCodec.js";
import { ALLOWED_SYMPTOMS } from "../src/schema.js";
import { assignTier } from "../src/rules/engine.js";

describe("VN1 Emergency SMS Binary Codec (ADR §51)", () => {
  it("round-trips a full EMERGENCY maternal preeclampsia case in 42 ASCII chars", () => {
    const input: SmsFrameInput = {
      client_id: "550e8400-e29b-41d4-a716-446655440000",
      patient_age: 26,
      patient_sex: "female",
      is_pregnant: true,
      triage_level: "EMERGENCY",
      symptoms: ["severe_headache", "severe_abdominal_pain"],
      bp_systolic: 168,
      bp_diastolic: 112,
      spo2: 96,
      heart_rate: 108,
      temperature: 37.4,
    };

    const encoded = encodeEmergencySmsFrame(input);
    expect(encoded.startsWith("VN1:")).toBe(true);
    expect(encoded.length).toBeLessThanOrEqual(43);

    const decoded = decodeEmergencySmsFrame(`Emergency alert [${encoded}]`);
    expect(decoded.client_id).toBe(input.client_id);
    expect(decoded.clientId).toBe(input.client_id);
    expect(decoded.patient_age).toBe(input.patient_age);
    expect(decoded.patientAge).toBe(input.patient_age);
    expect(decoded.patient_sex).toBe(input.patient_sex);
    expect(decoded.patientSex).toBe(input.patient_sex);
    expect(decoded.is_pregnant).toBe(true);
    expect(decoded.isPregnant).toBe(true);
    expect(decoded.triage_level).toBe("EMERGENCY");
    expect(decoded.triageTier).toBe("EMERGENCY");
    expect(decoded.symptoms.sort()).toEqual([...input.symptoms].sort());
    expect(decoded.bp_systolic).toBe(168);
    expect(decoded.bpSystolic).toBe(168);
    expect(decoded.bp_diastolic).toBe(112);
    expect(decoded.bpDiastolic).toBe(112);
    expect(decoded.spo2).toBe(96);
    expect(decoded.heart_rate).toBe(108);
    expect(decoded.heartRate).toBe(108);
    expect(decoded.temperature).toBe(37.4);
  });

  it("preserves null unmeasured vitals without fabricating values", () => {
    const input: SmsFrameInput = {
      client_id: "123e4567-e89b-12d3-a456-426614174000",
      patient_age: 4,
      patient_sex: "male",
      is_pregnant: false,
      triage_level: "EMERGENCY",
      symptoms: ["seizure", "high_fever"],
      bp_systolic: null,
      bp_diastolic: null,
      spo2: null,
      heart_rate: 175,
      temperature: 39.8,
    };

    const encoded = encodeEmergencySms(input);
    const decoded = decodeEmergencySms(encoded);
    expect(decoded.bp_systolic).toBeNull();
    expect(decoded.bpSystolic).toBeNull();
    expect(decoded.bp_diastolic).toBeNull();
    expect(decoded.bpDiastolic).toBeNull();
    expect(decoded.spo2).toBeNull();
    expect(decoded.heart_rate).toBe(175);
    expect(decoded.heartRate).toBe(175);
    expect(decoded.temperature).toBe(39.8);
  });

  it("preserves newborn age 0 without falsy coercion", () => {
    const input: SmsFrameInput = {
      clientId: "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
      patientAge: 0,
      patientSex: "female",
      triageTier: "EMERGENCY",
      symptoms: ["breathlessness"],
      heartRate: 160,
    };

    const encoded = encodeEmergencySms(input);
    const decoded = decodeEmergencySms(encoded);
    expect(decoded.patientAge).toBe(0);
    expect(decoded.patient_age).toBe(0);
  });

  it("rejects single-character bit-flip corruption via CRC24", () => {
    const encoded = encodeEmergencySmsFrame({
      client_id: "550e8400-e29b-41d4-a716-446655440000",
      patient_age: 50,
      patient_sex: "male",
      triage_level: "EMERGENCY",
      symptoms: ["chest_pain", "breathlessness"],
    });
    const lastChar = encoded[encoded.length - 1] === "A" ? "B" : "A";
    const corrupted = encoded.slice(0, -1) + lastChar;
    expect(() => decodeEmergencySmsFrame(corrupted)).toThrow(/CRC24/i);
  });

  it("handles boundary values for numeric vital encodings", () => {
    const input: SmsFrameInput = {
      clientId: "ffffffff-ffff-ffff-ffff-ffffffffffff",
      patientAge: 120,
      patientSex: "other",
      isPregnant: false,
      triageTier: "ROUTINE",
      symptoms: [],
      bpSystolic: 21, // lower bound (21 - 20 = 1)
      bpDiastolic: 1,  // lower bound (1)
      spo2: 50,       // lower bound (50)
      heartRate: 10,  // lower bound (10)
      temperature: 25.1, // lower bound (round((25.1 - 25.0)*10) = 1)
    };

    const encoded = encodeEmergencySms(input);
    const decoded = decodeEmergencySms(encoded);
    expect(decoded.bpSystolic).toBe(21);
    expect(decoded.bpDiastolic).toBe(1);
    expect(decoded.spo2).toBe(50);
    expect(decoded.heartRate).toBe(10);
    expect(decoded.temperature).toBe(25.1);

    const inputMax: SmsFrameInput = {
      clientId: "ffffffff-ffff-ffff-ffff-ffffffffffff",
      patientAge: 120,
      patientSex: "female",
      isPregnant: true,
      triageTier: "EMERGENCY",
      symptoms: [...ALLOWED_SYMPTOMS],
      bpSystolic: 270, // upper bound (270 - 20 = 250)
      bpDiastolic: 200, // upper bound (200)
      spo2: 100,       // upper bound (100)
      heartRate: 250,  // upper bound (250)
      temperature: 45.0, // upper bound (round((45.0 - 25.0)*10) = 200)
    };

    const encodedMax = encodeEmergencySms(inputMax);
    const decodedMax = decodeEmergencySms(encodedMax);
    expect(decodedMax.bpSystolic).toBe(270);
    expect(decodedMax.bpDiastolic).toBe(200);
    expect(decodedMax.spo2).toBe(100);
    expect(decodedMax.heartRate).toBe(250);
    expect(decodedMax.temperature).toBe(45.0);
    expect(decodedMax.symptoms.length).toBe(12);
  });

  it("fuzz tests 1,000 randomized payloads with bit-exact round-trip", () => {
    const sexes: Array<"male" | "female" | "other"> = ["male", "female", "other"];
    const tiers: Array<"ROUTINE" | "URGENT" | "EMERGENCY"> = ["ROUTINE", "URGENT", "EMERGENCY"];

    for (let i = 0; i < 1000; i++) {
      const age = Math.floor(Math.random() * 121);
      const sex = sexes[Math.floor(Math.random() * sexes.length)]!;
      const isPregnant = Math.random() > 0.5;
      const tier = tiers[Math.floor(Math.random() * tiers.length)]!;
      const numSymptoms = Math.floor(Math.random() * 4);
      const symptoms: string[] = [];
      for (let s = 0; s < numSymptoms; s++) {
        const sym = ALLOWED_SYMPTOMS[Math.floor(Math.random() * ALLOWED_SYMPTOMS.length)]!;
        if (!symptoms.includes(sym)) symptoms.push(sym);
      }

      const sbp = Math.random() > 0.3 ? Math.floor(Math.random() * 200) + 50 : null;
      const dbp = Math.random() > 0.3 ? Math.floor(Math.random() * 120) + 30 : null;
      const spo2 = Math.random() > 0.3 ? Math.floor(Math.random() * 51) + 50 : null;
      const hr = Math.random() > 0.3 ? Math.floor(Math.random() * 180) + 40 : null;
      const temp = Math.random() > 0.3 ? Math.round((35.0 + Math.random() * 6.0) * 10) / 10 : null;

      const randomHex = Array.from({ length: 32 }, () => Math.floor(Math.random() * 16).toString(16)).join("");
      const clientId = `${randomHex.slice(0, 8)}-${randomHex.slice(8, 12)}-${randomHex.slice(12, 16)}-${randomHex.slice(16, 20)}-${randomHex.slice(20, 32)}`;

      const input: SmsFrameInput = {
        client_id: clientId,
        patient_age: age,
        patient_sex: sex,
        is_pregnant: isPregnant,
        triage_level: tier,
        symptoms,
        bp_systolic: sbp,
        bp_diastolic: dbp,
        spo2,
        heart_rate: hr,
        temperature: temp,
      };

      const encoded = encodeEmergencySms(input);
      const decoded = decodeEmergencySms(encoded);

      expect(decoded.client_id).toBe(clientId);
      expect(decoded.patient_age).toBe(age);
      expect(decoded.patient_sex).toBe(sex);
      expect(decoded.is_pregnant).toBe(isPregnant);
      expect(decoded.triage_level).toBe(tier);
      expect(decoded.symptoms.sort()).toEqual([...symptoms].sort());
      expect(decoded.bp_systolic).toBe(sbp);
      expect(decoded.bp_diastolic).toBe(dbp);
      expect(decoded.spo2).toBe(spo2);
      expect(decoded.heart_rate).toBe(hr);
      expect(decoded.temperature).toBe(temp);
    }
  });

  it("handles UUID encoding and decoding helpers accurately", () => {
    const original = "550e8400-e29b-41d4-a716-446655440000";
    const bytes = uuidToBytes(original);
    expect(bytes.length).toBe(16);
    const reconstructed = bytesToUuid(bytes);
    expect(reconstructed).toBe(original);
  });

  describe("Sub-Year Infant & Toddler Age Encoding (REG-01)", () => {
    it("round-trips exact sub-year and toddler ages from 0 to 23 months (bytes 200..223)", () => {
      for (let months = 0; months <= 23; months++) {
        const input: SmsFrameInput = {
          client_id: "550e8400-e29b-41d4-a716-446655440000",
          patient_age: Math.floor(months / 12),
          age_months: months,
          patient_sex: "female",
          is_pregnant: false,
          triage_level: "ROUTINE",
          symptoms: [],
        };
        const encoded = encodeEmergencySmsFrame(input);
        const decoded = decodeEmergencySmsFrame(encoded);

        expect(decoded.age_months).toBe(months);
        expect(decoded.ageMonths).toBe(months);
        expect(decoded.patient_age).toBe(Math.floor(months / 12));
        expect(decoded.patientAge).toBe(Math.floor(months / 12));
      }
    });

    it("derives sub-year months when rawAge is a fractional year without explicit age_months", () => {
      const input: SmsFrameInput = {
        client_id: "550e8400-e29b-41d4-a716-446655440000",
        patient_age: 0.25, // 3 months
        patient_sex: "male",
        triage_level: "ROUTINE",
        symptoms: [],
      };
      const encoded = encodeEmergencySmsFrame(input);
      const decoded = decodeEmergencySmsFrame(encoded);

      expect(decoded.age_months).toBe(3);
      expect(decoded.patient_age).toBe(0);
    });

    it("maintains backward-compatibility for legacy byte 254 frames", () => {
      const buf = new Uint8Array(28);
      const uuid = uuidToBytes("550e8400-e29b-41d4-a716-446655440000");
      buf.set(uuid, 0);
      buf[16] = 1 << 5; // Version 1, male, not pregnant, ROUTINE
      buf[17] = 254; // Legacy sub-year sentinel
      const crc = computeCrc24(buf, 25);
      buf[25] = (crc >> 16) & 0xff;
      buf[26] = (crc >> 8) & 0xff;
      buf[27] = crc & 0xff;

      const rawEncoded = `VN1:${base64UrlEncode(buf)}`;
      const decoded = decodeEmergencySmsFrame(rawEncoded);

      expect(decoded.patient_age).toBe(0);
      expect(decoded.patientAge).toBe(0);
      expect(decoded.age_months).toBe(6);
      expect(decoded.ageMonths).toBe(6);
    });

    it("verifies encoded/decoded 1-month infant with temp 38.5 triggers neonatal_fever override in assignTier", () => {
      const input: SmsFrameInput = {
        client_id: "550e8400-e29b-41d4-a716-446655440000",
        patient_age: 0,
        age_months: 1,
        patient_sex: "female",
        is_pregnant: false,
        triage_level: "ROUTINE", // Naive / pre-rules level
        symptoms: [],
        temperature: 38.5,
      };

      const encoded = encodeEmergencySmsFrame(input);
      const decoded = decodeEmergencySmsFrame(encoded);

      expect(decoded.age_months).toBe(1);
      expect(decoded.patient_age).toBe(0);
      expect(decoded.temperature).toBe(38.5);

      // Verify that assignTier evaluates effective age < 0.25 years (1 month) with temp >= 38.0C
      const result = assignTier(decoded);
      expect(result.tier).toBe("EMERGENCY");
      const neonatalRule = result.firedRules.find((r) => r.id === "neonatal_fever");
      expect(neonatalRule).toBeDefined();
      expect(neonatalRule?.citation).toContain("Neonatal fever");
    });
  });
});

