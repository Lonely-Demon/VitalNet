// Golden-vector parity: buildFeatureMap (this package) must match the
// EXACT same 240 vectors the pre-migration featureParity.test.mjs checked
// against ClinicalFeatureEngineer / triageClassifier.js — proof this port
// changed nothing. Reads the fixture committed at
// apps/web/tests/fixtures/golden_feature_vectors.json (unchanged by this
// migration; still the single source of golden data until the CLI, once
// wired into tools/training/, regenerates it from this package instead).

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { describe, expect, it } from "vitest";
import { buildFeatureMap, type FeatureFormInput } from "../src/features.js";

const here = dirname(fileURLToPath(import.meta.url));
const fixturePath = join(here, "../../../apps/web/tests/fixtures/golden_feature_vectors.json");
const vectors: Array<{ input: FeatureFormInput; features: Record<string, number> }> = JSON.parse(
  readFileSync(fixturePath, "utf8"),
);

const TOLERANCE = 1e-6;

describe("buildFeatureMap matches the committed golden feature vectors", () => {
  it(`all ${vectors.length} vectors agree within tolerance`, () => {
    let mismatches = 0;
    const details: string[] = [];

    for (const { input, features: expected } of vectors) {
      const computed = buildFeatureMap(input);
      const expectedKeys = Object.keys(expected).sort();
      const computedKeys = Object.keys(computed).sort();
      if (expectedKeys.join(",") !== computedKeys.join(",")) {
        mismatches++;
        details.push(`key mismatch: expected=${expectedKeys} got=${computedKeys}`);
        continue;
      }
      for (const key of expectedKeys) {
        if (Math.abs(computed[key]! - expected[key]!) > TOLERANCE) {
          mismatches++;
          details.push(`${key}: expected ${expected[key]}, got ${computed[key]}`);
        }
      }
    }

    expect(mismatches, details.slice(0, 10).join("\n")).toBe(0);
  });
});
