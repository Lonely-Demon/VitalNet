// Golden-vector regression snapshot for buildFeatureMap. Historically this
// fixture was Python-generated (ClinicalFeatureEngineer) and proved the JS
// port matched it; tools/training/train_classifier.py now regenerates
// apps/web/tests/fixtures/golden_feature_vectors.json from THIS package's
// own engineer_features_batch (via cli.mjs) on every training run, so this
// is a snapshot/regression guard, not a cross-language parity check — an
// unreviewed change to features.ts that isn't paired with a fixture
// regeneration + review will fail this test.

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
