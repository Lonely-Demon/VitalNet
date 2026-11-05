import { describe, expect, it } from "vitest";
import {
  generatePatientKey,
  generateUnbiasedPatientKey,
  normalizePatientKey,
  deriveDeterministicPatientKey,
  deriveAbhaKey,
  buildIndicPhoneticSkeleton,
  ALPHABET,
  PATIENT_KEY_FORMAT_RE,
} from "../src/patientKey.js";
import { PATIENT_KEY_RE } from "../src/schema.js";

describe("Patient Continuity Key & Indic Phonetics (ADR §49)", () => {
  it("generates schema-compliant XXXX-XXXX keys matching PATIENT_KEY_RE", () => {
    for (let i = 0; i < 50; i++) {
      const key = generatePatientKey();
      expect(PATIENT_KEY_RE.test(key)).toBe(true);
      expect(key.length).toBe(9);
      expect(key[4]).toBe("-");
    }
  });

  it("never contains ambiguous characters (0, 1, I, L, O)", () => {
    const forbidden = ["0", "1", "I", "L", "O"];
    for (let i = 0; i < 100; i++) {
      const key = generateUnbiasedPatientKey();
      for (const char of forbidden) {
        expect(key.includes(char)).toBe(false);
      }
    }
  });

  it("proves uniform unbiased rejection sampling via Chi-squared test (p > 0.01)", () => {
    const sampleKeys = 10000;
    const totalChars = sampleKeys * 8;
    const counts = new Array(30).fill(0);

    for (let k = 0; k < sampleKeys; k++) {
      const key = generatePatientKey();
      const raw = key.replace("-", "");
      for (let c = 0; c < 8; c++) {
        const idx = ALPHABET.indexOf(raw[c]!);
        expect(idx).toBeGreaterThanOrEqual(0);
        counts[idx]++;
      }
    }

    const expected = totalChars / 30; // ~2666.67
    let chiSquare = 0;
    for (let i = 0; i < 30; i++) {
      const diff = counts[i]! - expected;
      chiSquare += (diff * diff) / expected;
    }

    // Critical value for chi-square distribution with df = 29 at alpha = 0.01 is ~49.59
    // p > 0.01 requires chiSquare < 49.59
    expect(chiSquare).toBeLessThan(49.59);
  });

  it("normalizes user-typed input and rejects malformed keys", () => {
    expect(normalizePatientKey("  2345-6789  ")).toBe("2345-6789");
    expect(normalizePatientKey("abcd-efgh")).toBe("ABCD-EFGH");
    expect(normalizePatientKey("1234-5678")).toBeNull(); // contains 1
    expect(normalizePatientKey("ABCD-EFG")).toBeNull();  // too short
    expect(normalizePatientKey(null)).toBeNull();
  });

  it("derives deterministic 16-character base32 ABHA HIDN key via deriveAbhaKey", () => {
    const abha1 = "91-2345-6789-0123";
    const abha1Clean = "91234567890123";
    const key1a = deriveAbhaKey(abha1);
    const key1b = deriveAbhaKey(abha1Clean);
    expect(key1a).toBe(key1b);
    expect(key1a.length).toBe(16);
    expect(/^[A-Z2-7]{16}$/.test(key1a)).toBe(true);

    const abha2 = "91-2345-6789-0124";
    const key2 = deriveAbhaKey(abha2);
    expect(key1a).not.toBe(key2);
  });

  it("derives deterministic XXXX-XXXX patient key via deriveDeterministicPatientKey", () => {
    const abha1 = "91234567890123";
    const key1a = deriveDeterministicPatientKey("abha", abha1);
    const key1b = deriveDeterministicPatientKey("abha", abha1);
    expect(key1a).toBe(key1b);
    expect(PATIENT_KEY_FORMAT_RE.test(key1a)).toBe(true);

    const abha2 = "91234567890124";
    const key2 = deriveDeterministicPatientKey("abha", abha2);
    expect(key1a).not.toBe(key2);
    expect(PATIENT_KEY_FORMAT_RE.test(key2)).toBe(true);
  });

  it("normalizes Devanagari and Latin phonetic spelling variants to the same skeleton", () => {
    expect(buildIndicPhoneticSkeleton("रमेश पाटील")).toBe("rmsptl");
    expect(buildIndicPhoneticSkeleton("Ramesh Patil")).toBe("rmsptl");
    expect(buildIndicPhoneticSkeleton("रमेश पाटील")).toBe(buildIndicPhoneticSkeleton("Ramesh Patil"));

    expect(buildIndicPhoneticSkeleton("सुनील गावस्कर")).toBe(buildIndicPhoneticSkeleton("Sunil Gavaskar"));
    expect(buildIndicPhoneticSkeleton("सुनील")).toBe(buildIndicPhoneticSkeleton("Sunil"));
  });

  it("collapses aspirated consonant digraphs and geminates", () => {
    expect(buildIndicPhoneticSkeleton("Bharat")).toBe("brt");
    expect(buildIndicPhoneticSkeleton("Khatri")).toBe("ktr");
    expect(buildIndicPhoneticSkeleton("Patte")).toBe("pt");
    expect(buildIndicPhoneticSkeleton("Bharati")).toBe(buildIndicPhoneticSkeleton("Barti"));
    expect(buildIndicPhoneticSkeleton("")).toBe("");
  });
});
