import { describe, expect, it } from "vitest";
import {
  encodeEmergencySms,
  decodeEmergencySms,
  computeCrc24,
  base64UrlEncode,
  base64UrlDecode,
  assessFeatureCompleteness,
  computeRiskDriver,
  explainPrediction,
  evaluateSingleTree,
  evaluateTrees,
  getUnmeasuredFeatureSet,
  triage,
  buildIndicPhoneticSkeleton,
  deriveDeterministicPatientKey,
  deriveAbhaKey,
  parseDob,
  parseAbhaQr,
  calculatePediatricGcs,
  normalizeSymptomDuration,
  resolveEffectiveAge,
  checkOverrides,
  type TreeJson,
  type TreeNode,
} from "../src/index.js";

describe("Milestone 2 (Phase 52) Adversarial Empirical Verification Suite", () => {
  // =========================================================================
  // 1. SMS Codec Adversarial Stress Tests
  // =========================================================================
  describe("1. SMS Codec Edge Cases & Boundary Injections", () => {
    it("handles truncated frames and throws standardized InvalidSmsFrame errors", () => {
      // Empty string
      expect(() => decodeEmergencySms("")).toThrow(/InvalidSmsFrame/);

      // Bare prefix with zero payload
      expect(() => decodeEmergencySms("VN1:")).toThrow(/InvalidSmsFrame: Malformed or truncated VN1 frame/);

      // Sub-37 character payload (36 chars)
      const shortPayload = "VN1:" + "A".repeat(36);
      expect(() => decodeEmergencySms(shortPayload)).toThrow(/InvalidSmsFrame: Malformed or truncated VN1 frame/);

      // Super-39 character payload (40 chars)
      const longPayload = "VN1:" + "A".repeat(40);
      expect(() => decodeEmergencySms(longPayload)).toThrow(/InvalidSmsFrame: Malformed or truncated VN1 frame/);

      // Random non-base64 noise
      expect(() => decodeEmergencySms("VN1:???***$$$%%%&&&")).toThrow(/InvalidSmsFrame/);
    });

    it("parses valid frames embedded in noisy/surrounding SMS text with delimiter boundaries", () => {
      const valid = encodeEmergencySms({
        patient_age: 32,
        patient_sex: "female",
        triage_level: "URGENT",
        symptoms: ["severe_headache"],
      });
      const validPayload = valid.slice(4);

      // Embedded in brackets
      const bracketed = `DISPATCH REQUIRED [VN1:${validPayload}] IMMEDIATELY`;
      const decoded1 = decodeEmergencySms(bracketed);
      expect(decoded1.patient_age).toBe(32);
      expect(decoded1.patient_sex).toBe("female");
      expect(decoded1.triage_level).toBe("URGENT");

      // Embedded in parentheses
      const parenthesized = `Urgent alert: (VN1:${validPayload}) at Subcentre 4`;
      const decoded2 = decodeEmergencySms(parenthesized);
      expect(decoded2.patient_age).toBe(32);

      // Trailing whitespace and newline
      const spaced = `   \n\t  VN1:${validPayload}   \r\n `;
      const decoded3 = decodeEmergencySms(spaced);
      expect(decoded3.patient_age).toBe(32);
    });

    it("rejects corrupted CRC24 checksum frames without state corruption", () => {
      const valid = encodeEmergencySms({
        patient_age: 45,
        patient_sex: "male",
        triage_level: "ROUTINE",
        symptoms: [],
      });

      const rawBase64 = valid.slice(4);
      const rawBytes = base64UrlDecode(rawBase64);
      expect(rawBytes.length).toBe(28);

      // Flip bit in payload byte 5
      rawBytes[5]! ^= 0x01;
      const corruptedBase64 = "VN1:" + base64UrlEncode(rawBytes);

      expect(() => decodeEmergencySms(corruptedBase64)).toThrow(/CRC24 integrity check failed/);
    });

    it("correctly encodes sub-year neonate (<0.25y) vs 1-year infant vs 100-year elder in byte 17", () => {
      // 1. Sub-year neonate (< 0.25y, e.g. 1 month old = 0.083y) -> Byte 17 is 200 + 1 = 201 (REG-01)
      const neonate1m = encodeEmergencySms({
        patient_age: 0,
        age_months: 1,
        patient_sex: "male",
        triage_level: "EMERGENCY",
        symptoms: [],
      });
      const neonate1mBytes = base64UrlDecode(neonate1m.slice(4));
      expect(neonate1mBytes[17]).toBe(201);
      const decodedNeonate = decodeEmergencySms(neonate1m);
      expect(decodedNeonate.patient_age).toBe(0);
      expect(decodedNeonate.age_months).toBe(1);

      // 2. Sub-year neonate specified as fractional age (< 0.25y, age: 0.15 -> round(0.15*12) = 2 months)
      const neonateFractional = encodeEmergencySms({
        patient_age: 0.15,
        patient_sex: "female",
        triage_level: "ROUTINE",
        symptoms: [],
      });
      const neonateFracBytes = base64UrlDecode(neonateFractional.slice(4));
      expect(neonateFracBytes[17]).toBe(202);
      const decodedNeonateFrac = decodeEmergencySms(neonateFractional);
      expect(decodedNeonateFrac.patient_age).toBe(0);
      expect(decodedNeonateFrac.age_months).toBe(2);

      // 3. 1-year infant/toddler with age_months: 12 -> Byte 17 is 200 + 12 = 212 (REG-01)
      const infant1y = encodeEmergencySms({
        patient_age: 1,
        age_months: 12,
        patient_sex: "female",
        triage_level: "ROUTINE",
        symptoms: [],
      });
      const infant1yBytes = base64UrlDecode(infant1y.slice(4));
      expect(infant1yBytes[17]).toBe(212);
      const decodedInfant = decodeEmergencySms(infant1y);
      expect(decodedInfant.patient_age).toBe(1);
      expect(decodedInfant.age_months).toBe(12);

      // 3b. 1-year child without explicit age_months -> Byte 17 is integer age 1
      const child1y = encodeEmergencySms({
        patient_age: 1,
        patient_sex: "female",
        triage_level: "ROUTINE",
        symptoms: [],
      });
      const child1yBytes = base64UrlDecode(child1y.slice(4));
      expect(child1yBytes[17]).toBe(1);
      const decodedChild = decodeEmergencySms(child1y);
      expect(decodedChild.patient_age).toBe(1);
      expect(decodedChild.age_months).toBeNull();

      // 4. 100-year elder -> Byte 17 must be 100
      const elder100 = encodeEmergencySms({
        patient_age: 100,
        patient_sex: "male",
        triage_level: "URGENT",
        symptoms: [],
      });
      const elder100Bytes = base64UrlDecode(elder100.slice(4));
      expect(elder100Bytes[17]).toBe(100);
      const decodedElder = decodeEmergencySms(elder100);
      expect(decodedElder.patient_age).toBe(100);

      // 5. Extreme age boundary (140y clamped to 120)
      const elder140 = encodeEmergencySms({
        patient_age: 140,
        patient_sex: "female",
        triage_level: "ROUTINE",
        symptoms: [],
      });
      const elder140Bytes = base64UrlDecode(elder140.slice(4));
      expect(elder140Bytes[17]).toBe(120);
    });

    it("accepts aliases (age, sex, tier) without defaulting to male neonate ROUTINE", () => {
      const aliasPayload = {
        age: 62,
        sex: "female" as const,
        tier: "URGENT" as const,
        symptoms: ["severe_headache", "chest_pain"],
      };

      const encoded = encodeEmergencySms(aliasPayload);
      const decoded = decodeEmergencySms(encoded);

      expect(decoded.patient_age).toBe(62);
      expect(decoded.patient_sex).toBe("female");
      expect(decoded.triage_level).toBe("URGENT");
      expect(decoded.tier).toBe("URGENT");
      expect(decoded.symptoms).toContain("severe_headache");
      expect(decoded.symptoms).toContain("chest_pain");

      // Verify case-insensitivity on aliases
      const casePayload = {
        age: 50,
        sex: "FEMALE" as any,
        tier: "emergency" as any,
        symptoms: [],
      };
      const caseEncoded = encodeEmergencySms(casePayload);
      const caseDecoded = decodeEmergencySms(caseEncoded);
      expect(caseDecoded.patient_sex).toBe("female");
      expect(caseDecoded.triage_level).toBe("EMERGENCY");
    });
  });

  // =========================================================================
  // 2. Tree Evaluator & Attribution Adversarial Tests
  // =========================================================================
  describe("2. Tree Evaluator & Saabas Attribution Invariants", () => {
    it("strictly ranks positive risk drivers (+delta) ahead of protective negative deltas (-delta)", () => {
      // Construct a synthetic 4-feature tree with known node values:
      // feat 0 (heart_rate): +0.40 positive risk driver
      // feat 1 (spo2): -0.85 protective negative factor (normal saturation)
      // feat 2 (bp_systolic): +0.15 mild positive risk driver
      // feat 3 (temperature): -0.30 protective negative factor
      const treeJson: TreeJson = {
        n_features: 4,
        n_classes: 3,
        labels: [0, 1, 2],
        base_values: [0, 0, 0],
        post_transform: "NONE",
        trees: [
          {
            feat: [0, 1, 2, 3, -1, -1, -1, -1, -1],
            thr: [50, 50, 50, 50, 0, 0, 0, 0, 0],
            left: [1, 2, 3, 4, -1, -1, -1, -1, -1],
            right: [-1, -1, -1, -1, -1, -1, -1, -1, -1],
            leaf: [null, null, null, null, [[2, 0.5]], null, null, null, null],
            nodeVal: [
              [0, 0, 0.0],
              [0, 0, 0.40],  // feat 0 delta = +0.40
              [0, 0, -0.45], // feat 1 delta = -0.85
              [0, 0, -0.30], // feat 2 delta = +0.15
              [0, 0, -0.60], // feat 3 delta = -0.30
            ],
          },
        ],
      };

      const featureVector = [10, 10, 10, 10]; // Traverses 0 -> 1 -> 2 -> 3 -> 4
      const featureNames = ["heart_rate", "spo2", "bp_systolic", "temperature"];

      const attributions = explainPrediction(treeJson, featureVector, 2);
      expect(attributions.length).toBe(4);

      // Verify positive risk contributors are placed ahead of negative protective deltas
      expect(attributions[0]!.featureIndex).toBe(0); // heart_rate (+0.40)
      expect(attributions[0]!.contribution).toBeCloseTo(0.40, 4);

      expect(attributions[1]!.featureIndex).toBe(2); // bp_systolic (+0.15)
      expect(attributions[1]!.contribution).toBeCloseTo(0.15, 4);

      // Negative factors follow, sorted by magnitude descending (|-0.85| > |-0.30|)
      expect(attributions[2]!.featureIndex).toBe(1); // spo2 (-0.85)
      expect(attributions[2]!.contribution).toBeCloseTo(-0.85, 4);

      expect(attributions[3]!.featureIndex).toBe(3); // temperature (-0.30)
      expect(attributions[3]!.contribution).toBeCloseTo(-0.30, 4);

      // computeRiskDriver must select heart_rate (+0.40), NEVER spo2 (-0.85)
      const topDriver = computeRiskDriver(treeJson, featureVector, 2, featureNames);
      expect(topDriver).not.toBeNull();
      expect(topDriver?.featureName).toBe("heart_rate");
      expect(topDriver?.contribution).toBeCloseTo(0.40, 4);
    });

    it("resists IEEE-754 NaN, Infinity, and -Infinity inputs in assessFeatureCompleteness", () => {
      const maliciousVitals = {
        bp_systolic: NaN,
        bp_diastolic: Infinity,
        heart_rate: -Infinity,
        spo2: -0,
        temperature: -1.0,
        chief_complaint: "dizziness",
      };

      const completeness = assessFeatureCompleteness(maliciousVitals);
      // All 5 vitals must be flagged as missing
      expect(completeness.missingVitals.length).toBe(5);
      expect(completeness.missingCriticalVitals.length).toBe(5);
      expect(completeness.status).toBe("SPARSE_CONTEXT");
      expect(completeness.lowConfidence).toBe(true);
      expect(completeness.missingCriticalVitals).toEqual([
        "bp_systolic",
        "bp_diastolic",
        "heart_rate",
        "spo2",
        "temperature",
      ]);
    });

    it("detects IEEE-754 NaN and non-finite vitals in getUnmeasuredFeatureSet and cascades to derived features", () => {
      const formInput = {
        patient_age: 40,
        patient_sex: "male" as const,
        bp_systolic: NaN,
        bp_diastolic: 80,
        heart_rate: Infinity,
        spo2: -Infinity,
        temperature: null,
        symptoms: [],
        chief_complaint: "malaise",
        complaint_duration: "1 day",
        location: "rural",
        known_conditions: null,
      };

      const unmeasured = getUnmeasuredFeatureSet(formInput);

      expect(unmeasured.has("bp_systolic")).toBe(true);
      expect(unmeasured.has("heart_rate")).toBe(true);
      expect(unmeasured.has("spo2")).toBe(true);
      expect(unmeasured.has("temperature")).toBe(true);

      // Cascading derived features
      expect(unmeasured.has("shock_index")).toBe(true);
      expect(unmeasured.has("mean_arterial_pressure")).toBe(true);
      expect(unmeasured.has("pulse_pressure")).toBe(true);
      expect(unmeasured.has("spo2_age_ratio")).toBe(true);
      expect(unmeasured.has("temp_deviation")).toBe(true);
    });

    it("strictly rejects whitespace-only chief complaints from COMPLETE status", () => {
      const completeVitals = {
        patient_age: 35,
        bp_systolic: 120,
        bp_diastolic: 80,
        heart_rate: 72,
        spo2: 98,
        temperature: 37.0,
        symptoms: [],
      };

      // 1. Valid chief complaint -> COMPLETE
      const validRes = assessFeatureCompleteness({
        ...completeVitals,
        chief_complaint: "mild headache",
      });
      expect(validRes.status).toBe("COMPLETE");

      // 2. Spaces-only -> PARTIAL_VITALS
      const spacesRes = assessFeatureCompleteness({
        ...completeVitals,
        chief_complaint: "     ",
      });
      expect(spacesRes.status).toBe("PARTIAL_VITALS");

      // 3. Tabs, newlines, carriage returns -> PARTIAL_VITALS
      const whitespaceRes = assessFeatureCompleteness({
        ...completeVitals,
        chief_complaint: "\t\r\n   \t  ",
      });
      expect(whitespaceRes.status).toBe("PARTIAL_VITALS");
    });

    it("exempts blood pressure from critical vitals for pediatric visits (age < 5)", () => {
      // 3-year-old toddler without BP cuff
      const toddlerForm = {
        patient_age: 3,
        bp_systolic: null,
        bp_diastolic: null,
        heart_rate: 105,
        spo2: 99,
        temperature: 37.2,
        chief_complaint: "rash",
        symptoms: [],
      };

      const toddlerRes = assessFeatureCompleteness(toddlerForm);
      expect(toddlerRes.missingCriticalVitals).toEqual([]);
      expect(toddlerRes.missingVitals).toEqual(["bp_systolic", "bp_diastolic"]);
      expect(toddlerRes.status).toBe("COMPLETE");
      expect(toddlerRes.lowConfidence).toBe(false);

      // 4-month-old infant (age: 0, age_months: 4 -> effectiveAge = 0.33y < 5)
      const infantForm = {
        patient_age: 0,
        age_months: 4,
        bp_systolic: null,
        bp_diastolic: null,
        heart_rate: 120,
        spo2: 98,
        temperature: 36.8,
        chief_complaint: "feeding difficulty",
        symptoms: [],
      };

      const infantRes = assessFeatureCompleteness(infantForm);
      expect(infantRes.missingCriticalVitals).toEqual([]);
      expect(infantRes.status).toBe("COMPLETE");

      // 25-year-old adult without BP cuff -> must NOT be exempt
      const adultForm = {
        patient_age: 25,
        bp_systolic: null,
        bp_diastolic: null,
        heart_rate: 75,
        spo2: 98,
        temperature: 37.0,
        chief_complaint: "cough",
        symptoms: [],
      };

      const adultRes = assessFeatureCompleteness(adultForm);
      expect(adultRes.missingCriticalVitals).toContain("bp_systolic");
      expect(adultRes.missingCriticalVitals).toContain("bp_diastolic");
      expect(adultRes.status).toBe("PARTIAL_VITALS");
    });
  });

  // =========================================================================
  // 3. Patient Key & ABHA Scanner Adversarial Tests
  // =========================================================================
  describe("3. Patient Key & ABHA Scanner Invariants", () => {
    it("retains initial vowels for Indic names while collapsing consonants and stripping subsequent vowels", () => {
      // Anil -> anl
      expect(buildIndicPhoneticSkeleton("Anil")).toBe("anl");
      // Asha -> as
      expect(buildIndicPhoneticSkeleton("Asha")).toBe("as");
      // Uma -> um
      expect(buildIndicPhoneticSkeleton("Uma")).toBe("um");
      // Imran -> imrn
      expect(buildIndicPhoneticSkeleton("Imran")).toBe("imrn");
      // Omkar -> omkr
      expect(buildIndicPhoneticSkeleton("Omkar")).toBe("omkr");

      // Devanagari equivalence
      expect(buildIndicPhoneticSkeleton("अनिल")).toBe("anl");
      expect(buildIndicPhoneticSkeleton("आशा")).toBe("as");
      expect(buildIndicPhoneticSkeleton("उमा")).toBe("um");

      // Collision resistance across different first names
      expect(buildIndicPhoneticSkeleton("Ramesh Patil")).not.toBe(buildIndicPhoneticSkeleton("Suresh Patil"));
      expect(buildIndicPhoneticSkeleton("Deepak Sharma")).not.toBe(buildIndicPhoneticSkeleton("Dilip Sharma"));

      // Isolated vowels with zero consonants must return empty string
      expect(buildIndicPhoneticSkeleton("A")).toBe("");
      expect(buildIndicPhoneticSkeleton("AEIOU")).toBe("");
      expect(buildIndicPhoneticSkeleton("12345")).toBe("");
      expect(buildIndicPhoneticSkeleton("")).toBe("");
    });

    it("verifies collision resistance and schema compliance across deterministic patient keys", () => {
      const generatedKeys = new Set<string>();
      const N = 500;

      for (let i = 0; i < N; i++) {
        const hidn = `12-3456-7890-${String(i).padStart(4, "0")}`;
        const key = deriveDeterministicPatientKey("abha", hidn);

        // Verify format regex
        expect(key).toMatch(/^[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{4}-[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{4}$/);
        // Exclude ambiguous chars: 0, O, 1, I, L, Z
        expect(key).not.toMatch(/[01OILZ]/i);

        // Verify collision resistance
        expect(generatedKeys.has(key)).toBe(false);
        generatedKeys.add(key);
      }
      expect(generatedKeys.size).toBe(N);
    });

    it("accurately parses both ISO (YYYY-MM-DD) and Indian (DD/MM/YYYY, DD-MM-YYYY) dates in parseDob", () => {
      const ref = new Date("2026-11-08T00:00:00Z");

      // ISO: YYYY-MM-DD
      const iso = parseDob("1992-05-15", ref);
      expect(iso.yob).toBe(1992);
      expect(iso.age).toBe(34);

      // Indian slash: DD/MM/YYYY
      const indSlash = parseDob("15/05/1992", ref);
      expect(indSlash.yob).toBe(1992);
      expect(indSlash.age).toBe(34);

      // Indian dash: DD-MM-YYYY
      const indDash = parseDob("15-05-1992", ref);
      expect(indDash.yob).toBe(1992);
      expect(indDash.age).toBe(34);

      // Indian dot: DD.MM.YYYY
      const indDot = parseDob("15.05.1992", ref);
      expect(indDot.yob).toBe(1992);
      expect(indDot.age).toBe(34);

      // Exact birthday boundary check:
      // Birthday today (Nov 8): age = 2026 - 2000 = 26
      const bdayToday = parseDob("08/11/2000", ref);
      expect(bdayToday.age).toBe(26);

      // Birthday tomorrow (Nov 9): age = 2026 - 2000 - 1 = 25
      const bdayTomorrow = parseDob("09/11/2000", ref);
      expect(bdayTomorrow.age).toBe(25);

      // Birthday yesterday (Nov 7): age = 2026 - 2000 = 26
      const bdayYesterday = parseDob("07/11/2000", ref);
      expect(bdayYesterday.age).toBe(26);

      // Leap day Feb 29, 2000
      const leapDay = parseDob("29/02/2000", ref);
      expect(leapDay.yob).toBe(2000);
      expect(leapDay.age).toBe(26);

      // Year-only fallback
      const yearOnly = parseDob("1984", ref);
      expect(yearOnly.yob).toBe(1984);
      expect(yearOnly.age).toBe(42);

      // Malformed string
      const invalid = parseDob("not-a-date", ref);
      expect(invalid).toEqual({});
    });
  });

  // =========================================================================
  // 4. Clinical Rules Adversarial Tests (pGCS, Durations & Future Timestamps)
  // =========================================================================
  describe("4. Clinical Rules: pGCS Division-by-Zero & Duration Clamping", () => {
    it("safely handles degenerate maxScore bounds (0, negative, NaN, Infinity) in calculatePediatricGcs", () => {
      // Normal standard pGCS
      const normal = calculatePediatricGcs(4, 5, 6, 15);
      expect(normal.totalScore).toBe(15);
      expect(normal.scoreRatio).toBe(1.0);
      expect(normal.tier).toBe("ROUTINE");
      expect(normal.isComa).toBe(false);

      // maxScore = 0: must safely default to 15 to avoid division by zero
      const zeroMax = calculatePediatricGcs(3, 4, 5, 0);
      expect(zeroMax.maxScore).toBe(15);
      expect(zeroMax.totalScore).toBe(12);
      expect(zeroMax.scoreRatio).toBeCloseTo(12 / 15, 4);
      expect(Number.isFinite(zeroMax.scoreRatio)).toBe(true);

      // maxScore = -5: must safely default to 15
      const negMax = calculatePediatricGcs(2, 3, 4, -5);
      expect(negMax.maxScore).toBe(15);
      expect(negMax.totalScore).toBe(9);
      expect(negMax.scoreRatio).toBeCloseTo(9 / 15, 4);

      // maxScore = NaN: must safely default to 15
      const nanMax = calculatePediatricGcs(1, 1, 1, NaN);
      expect(nanMax.maxScore).toBe(15);
      expect(nanMax.totalScore).toBe(3);
      expect(nanMax.scoreRatio).toBeCloseTo(3 / 15, 4);
      expect(nanMax.tier).toBe("EMERGENCY");
      expect(nanMax.isComa).toBe(true);

      // maxScore = Infinity: must safely default to 15
      const infMax = calculatePediatricGcs(4, 5, 6, Infinity);
      expect(infMax.maxScore).toBe(15);
      expect(infMax.totalScore).toBe(15);

      // Clamping of out-of-range component scores:
      // Eye (1-4), Verbal (1-5), Motor (1-6)
      const clampedHigh = calculatePediatricGcs(99, 99, 99, 15);
      expect(clampedHigh.eye).toBe(4);
      expect(clampedHigh.verbal).toBe(5);
      expect(clampedHigh.motor).toBe(6);
      expect(clampedHigh.totalScore).toBe(15);

      const clampedLow = calculatePediatricGcs(-10, -10, -10, 15);
      expect(clampedLow.eye).toBe(1);
      expect(clampedLow.verbal).toBe(1);
      expect(clampedLow.motor).toBe(1);
      expect(clampedLow.totalScore).toBe(3);
      expect(clampedLow.isComa).toBe(true);
    });

    it("clamps negative duration inputs and future timestamps in normalizeSymptomDuration", () => {
      const referenceNow = 1731085200000; // Fixed timestamp

      // 1. Negative text duration: "-10 days" -> clamped to 0
      const negDays = normalizeSymptomDuration("-10 days", null, referenceNow);
      expect(negDays.durationMinutes).toBe(0);
      expect(negDays.durationHours).toBe(0);
      expect(negDays.durationDays).toBe(0);
      expect(negDays.isNegativeAdjusted).toBe(true);
      expect(negDays.standardizedText).toBe("acute (< 1 hour)");

      // 2. Negative text duration: "-5 hours" -> clamped to 0
      const negHours = normalizeSymptomDuration("-5 hours", null, referenceNow);
      expect(negHours.durationMinutes).toBe(0);
      expect(negHours.isNegativeAdjusted).toBe(true);

      // 3. Negative numeric duration: -48 -> clamped to 0
      const negNum = normalizeSymptomDuration(-48, null, referenceNow);
      expect(negNum.durationMinutes).toBe(0);
      expect(negNum.isNegativeAdjusted).toBe(true);

      // 4. Future timestamp (+12 hours relative to reference time) -> clamped to 0
      const futureTime = referenceNow + 12 * 3600 * 1000;
      const futureRes = normalizeSymptomDuration(null, futureTime, referenceNow);
      expect(futureRes.durationMinutes).toBe(0);
      expect(futureRes.isFutureTimestampAdjusted).toBe(true);
      expect(futureRes.standardizedText).toBe("acute (< 1 hour)");

      // 5. Valid past timestamp (4 hours ago) -> 240 minutes
      const pastTime = referenceNow - 4 * 3600 * 1000;
      const pastRes = normalizeSymptomDuration(null, pastTime, referenceNow);
      expect(pastRes.durationMinutes).toBe(240);
      expect(pastRes.durationHours).toBe(4);
      expect(pastRes.isNegativeAdjusted).toBe(false);
      expect(pastRes.isFutureTimestampAdjusted).toBe(false);

      // 6. Valid text durations: "3 days"
      const threeDays = normalizeSymptomDuration("3 days", null, referenceNow);
      expect(threeDays.durationMinutes).toBe(4320);
      expect(threeDays.durationDays).toBe(3);
    });
  });
});
