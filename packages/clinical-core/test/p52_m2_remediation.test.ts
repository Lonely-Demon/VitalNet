import { describe, expect, it } from "vitest";
import {
  encodeEmergencySms,
  decodeEmergencySms,
  assessFeatureCompleteness,
  computeRiskDriver,
  explainPrediction,
  evaluateSingleTree,
  getUnmeasuredFeatureSet,
  triage,
  buildIndicPhoneticSkeleton,
  deriveDeterministicPatientKey,
  deriveAbhaKey,
  parseDob,
  calculatePediatricGcs,
  normalizeSymptomDuration,
  type TreeJson,
  type TreeNode,
} from "../src/index.js";

describe("Milestone 2 (Phase 52) Remediation Suite", () => {
  describe("smsCodec (BUG-22, BUG-38, BUG-46)", () => {
    it("encodes and decodes using property aliases (age, sex, tier) without defaulting to male neonate (BUG-46)", () => {
      const input = {
        age: 28,
        sex: "female" as const,
        tier: "EMERGENCY" as const,
        is_pregnant: true,
        bp_systolic: 150,
        bp_diastolic: 95,
        heart_rate: 110,
        spo2: 91,
        temperature: 38.8,
        symptoms: ["severe_headache", "chest_pain"],
      };

      const encoded = encodeEmergencySms(input);
      expect(encoded.startsWith("VN1:")).toBe(true);

      const decoded = decodeEmergencySms(encoded);
      expect(decoded.patient_age).toBe(28);
      expect(decoded.patient_sex).toBe("female");
      expect(decoded.triage_level).toBe("EMERGENCY");
      expect(decoded.is_pregnant).toBe(true);
      expect(decoded.bp_systolic).toBe(150);
      expect(decoded.bp_diastolic).toBe(95);
      expect(decoded.heart_rate).toBe(110);
      expect(decoded.spo2).toBe(91);
      expect(decoded.temperature).toBe(38.8);
      expect(decoded.symptoms).toContain("severe_headache");
      expect(decoded.symptoms).toContain("chest_pain");
    });

    it("encodes sub-year infant age with byte 17 sentinel value 254 (BUG-22)", () => {
      // Infant with age: 0, age_months: 6
      const infantInput = {
        age: 0,
        age_months: 6,
        sex: "female" as const,
        tier: "ROUTINE" as const,
      };

      const encoded = encodeEmergencySms(infantInput);
      const decoded = decodeEmergencySms(encoded);
      expect(decoded.patient_age).toBe(0);
      expect(decoded.age_months).toBe(6);
    });

    it("rejects malformed or truncated frames with descriptive error (BUG-38)", () => {
      // Missing prefix
      expect(() => decodeEmergencySms("INVALID_PAYLOAD")).toThrow(
        /InvalidSmsFrame: No VN1 emergency frame found in SMS body/
      );

      // Truncated frame
      expect(() => decodeEmergencySms("VN1:short_frame")).toThrow(
        /InvalidSmsFrame: Malformed or truncated VN1 frame/
      );

      // Frame with corrupted CRC
      const valid = encodeEmergencySms({ patient_age: 30, patient_sex: "male", triage_level: "ROUTINE" });
      const corrupted = valid.slice(0, -2) + (valid.slice(-1) === "A" ? "B" : "A") + valid.slice(-1);
      expect(() => decodeEmergencySms(corrupted)).toThrow(/CRC24 integrity check failed/);
    });
  });

  describe("treeEvaluator & featureCompleteness (BUG-12, BUG-16, BUG-18, BUG-61, BUG-62)", () => {
    it("assessFeatureCompleteness flags NaN vitals as missing (BUG-61)", () => {
      const result = assessFeatureCompleteness({
        bp_systolic: NaN,
        bp_diastolic: 80,
        heart_rate: 75,
        spo2: 98,
        temperature: 37.0,
      });

      expect(result.missingCriticalVitals).toContain("bp_systolic");
      expect(result.missingVitals).toContain("bp_systolic");
      expect(result.status).toBe("PARTIAL_VITALS");
    });

    it("assessFeatureCompleteness exempts BP for pediatric age < 5 (BUG-16)", () => {
      const pediatricForm = {
        patient_age: 3,
        bp_systolic: null,
        bp_diastolic: null,
        heart_rate: 100,
        spo2: 98,
        temperature: 37.0,
        chief_complaint: "cough",
        symptoms: [],
      };

      const res = assessFeatureCompleteness(pediatricForm);
      // Even though BP is unmeasured, pediatric age < 5 does not treat BP as critical
      expect(res.missingCriticalVitals).toEqual([]);
      expect(res.missingVitals).toEqual(["bp_systolic", "bp_diastolic"]);
      expect(res.status).toBe("COMPLETE");
      expect(res.lowConfidence).toBe(false);
    });

    it("assessFeatureCompleteness rejects whitespace-only chief complaints from COMPLETE status (BUG-16)", () => {
      const whitespaceForm = {
        patient_age: 30,
        bp_systolic: 120,
        bp_diastolic: 80,
        heart_rate: 75,
        spo2: 98,
        temperature: 37.0,
        chief_complaint: "   \t\n  ",
        symptoms: [],
      };

      const res = assessFeatureCompleteness(whitespaceForm);
      expect(res.status).toBe("PARTIAL_VITALS");
    });

    it("computeRiskDriver ranks positive risk contributions ahead of negative protective deltas (BUG-12, BUG-62)", () => {
      const treeJson: TreeJson = {
        n_features: 3,
        n_classes: 3,
        labels: [0, 1, 2],
        base_values: [0, 0, 0],
        post_transform: "NONE",
        trees: [
          {
            feat: [0, 1, -1, -1, -1],
            thr: [50, 50, 0, 0, 0],
            left: [1, 3, -1, -1, -1],
            right: [2, 4, -1, -1, -1],
            leaf: [null, null, [[2, 0.1]], [[2, 0.5]], [[2, -0.9]]],
            nodeVal: [
              [0, 0, 0],
              [0, 0, 0.5],
              [0, 0, -0.9],
              [0, 0, 0.5],
              [0, 0, -0.9],
            ],
          },
        ],
      };
      const featureNames = ["spo2", "heart_rate", "respiratory_rate"];
      const featureVector = [40, 40, 0]; // routes to node 1, then leaf 3

      const result = computeRiskDriver(treeJson, featureVector, 2, featureNames);
      expect(result).not.toBeNull();
      expect(result?.featureName).toBe("spo2");
      expect(result?.contribution).toBeGreaterThan(0);
    });

    it("evaluateSingleTree routes correctly to leaf node", () => {
      const tree: TreeNode = {
        feat: [0, -1, -1],
        thr: [50, 0, 0],
        left: [1, -1, -1],
        right: [2, -1, -1],
        defaultLeft: [1, 0, 0],
        leaf: [null, [[0, 0.2]], [[0, 0.8]]],
      };

      const resLeft = evaluateSingleTree(tree, [30]);
      expect(resLeft.leafIndex).toBe(1);
      expect(resLeft.leafValue).toEqual([[0, 0.2]]);

      const resRight = evaluateSingleTree(tree, [70]);
      expect(resRight.leafIndex).toBe(2);
      expect(resRight.leafValue).toEqual([[0, 0.8]]);
    });
  });

  describe("features (BUG-17, BUG-61)", () => {
    it("getUnmeasuredFeatureSet detects NaN and non-finite vitals (BUG-61)", () => {
      const unmeasured = getUnmeasuredFeatureSet({
        patient_age: 35,
        patient_sex: "male",
        bp_systolic: NaN,
        bp_diastolic: 80,
        heart_rate: Infinity,
        spo2: -1,
        temperature: null,
        symptoms: [],
        chief_complaint: "fever",
        complaint_duration: "1 day",
        location: "rural",
        known_conditions: null,
      });

      expect(unmeasured.has("bp_systolic")).toBe(true);
      expect(unmeasured.has("heart_rate")).toBe(true);
      expect(unmeasured.has("spo2")).toBe(true);
      expect(unmeasured.has("temperature")).toBe(true);
      expect(unmeasured.has("shock_index")).toBe(true);
      expect(unmeasured.has("mean_arterial_pressure")).toBe(true);
      expect(unmeasured.has("pulse_pressure")).toBe(true);
    });
  });

  describe("triage (BUG-11, BUG-16)", () => {
    it("propagates completenessState, lowConfidence, missingVitals, and needsReview", () => {
      const res = triage({
        patient_age: 45,
        patient_sex: "male",
        bp_systolic: null,
        bp_diastolic: null,
        heart_rate: null,
        spo2: null,
        temperature: null,
        symptoms: [],
        chief_complaint: "unwell",
        complaint_duration: "1 day",
        location: "remote",
      }, { mode: "rules_first" });

      expect(res.lowConfidence).toBe(true);
      expect(res.completenessState).toBe("SPARSE_CONTEXT");
      expect(res.missingVitals.length).toBe(5);
      expect(res.needsReview).toBe(true);
      expect(res.needs_review).toBe(true);
    });
  });

  describe("patientKey (BUG-20, BUG-66)", () => {
    it("retains initial vowels and maps retroflex consonants consistently in buildIndicPhoneticSkeleton", () => {
      // Anil: retains initial vowel 'a' -> 'anl'
      const anil = buildIndicPhoneticSkeleton("Anil");
      expect(anil.startsWith("a")).toBe(true);
      expect(anil).toBe("anl");

      // Suresh: 'srs'
      const suresh = buildIndicPhoneticSkeleton("Suresh");
      expect(suresh).toBe("srs");

      // Single vowel non-consonant 'A' reduces to empty string
      expect(buildIndicPhoneticSkeleton("A")).toBe("");
    });

    it("derives deterministic salted patient key matching XXXX-XXXX format (BUG-66)", () => {
      const key1 = deriveDeterministicPatientKey("abha", "12-3456-7890-1234");
      const key2 = deriveDeterministicPatientKey("abha", "12-3456-7890-1234");
      expect(key1).toBe(key2);
      expect(key1).toMatch(/^[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{4}-[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{4}$/);

      // Distinct salt from ABHA key
      const abhaKey = deriveAbhaKey("12-3456-7890-1234");
      expect(abhaKey.length).toBe(16);
      expect(abhaKey).not.toBe(key1);
    });
  });

  describe("abhaScanner (BUG-21)", () => {
    it("parseDob parses both ISO and Indian standard date formats", () => {
      const ref = new Date("2026-06-15T00:00:00Z");

      // ISO: YYYY-MM-DD
      const iso = parseDob("1995-03-20", ref);
      expect(iso).toEqual({ age: 31, yob: 1995 });

      // Indian standard: DD/MM/YYYY
      const indianSlash = parseDob("20/03/1995", ref);
      expect(indianSlash).toEqual({ age: 31, yob: 1995 });

      // Indian standard: DD-MM-YYYY
      const indianDash = parseDob("20-03-1995", ref);
      expect(indianDash).toEqual({ age: 31, yob: 1995 });

      // Year-only format
      const yearOnly = parseDob("1995", ref);
      expect(yearOnly).toEqual({ age: 31, yob: 1995 });
    });
  });

  describe("rules (BUG-39, BUG-40)", () => {
    it("calculatePediatricGcs computes pGCS with division-by-zero protection (BUG-39)", () => {
      const normal = calculatePediatricGcs(4, 5, 6, 15);
      expect(normal.totalScore).toBe(15);
      expect(normal.scoreRatio).toBe(1);
      expect(normal.tier).toBe("ROUTINE");
      expect(normal.isComa).toBe(false);

      const severe = calculatePediatricGcs(1, 2, 3, 15);
      expect(severe.totalScore).toBe(6);
      expect(severe.tier).toBe("EMERGENCY");
      expect(severe.isComa).toBe(true);

      // Division by zero protection: maxScore <= 0 or NaN falls back to 15
      const zeroMax = calculatePediatricGcs(4, 5, 6, 0);
      expect(zeroMax.maxScore).toBe(15);
      expect(Number.isFinite(zeroMax.scoreRatio)).toBe(true);

      const nanMax = calculatePediatricGcs(4, 5, 6, NaN);
      expect(nanMax.maxScore).toBe(15);
      expect(Number.isFinite(nanMax.scoreRatio)).toBe(true);
    });

    it("normalizeSymptomDuration disallows negative duration and handles future timestamps (BUG-40)", () => {
      const now = Date.now();

      // Negative numeric duration clamped to 0
      const negNum = normalizeSymptomDuration(-10);
      expect(negNum.durationMinutes).toBe(0);
      expect(negNum.isNegativeAdjusted).toBe(true);

      // Negative text duration clamped to 0
      const negText = normalizeSymptomDuration("-3 hours");
      expect(negText.durationMinutes).toBe(0);
      expect(negText.isNegativeAdjusted).toBe(true);

      // Valid text duration
      const validText = normalizeSymptomDuration("2 hours");
      expect(validText.durationMinutes).toBe(120);
      expect(validText.durationHours).toBe(2);

      // Future timestamp clamped to reference time
      const futureDate = new Date(now + 3600 * 1000 * 5); // 5 hours in future
      const futureRes = normalizeSymptomDuration(null, futureDate, now);
      expect(futureRes.durationMinutes).toBe(0);
      expect(futureRes.isFutureTimestampAdjusted).toBe(true);

      // Past timestamp
      const pastDate = new Date(now - 3600 * 1000 * 2); // 2 hours in past
      const pastRes = normalizeSymptomDuration(null, pastDate, now);
      expect(pastRes.durationMinutes).toBe(120);
      expect(pastRes.durationHours).toBe(2);
    });
  });
});
