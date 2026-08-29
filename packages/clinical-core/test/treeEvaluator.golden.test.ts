// Golden-vector parity: evaluateTrees (this package) must match the model
// output on the same 300 vectors the pre-migration treeParity.test.mjs
// checked — proof the float32-comparison port (DECISIONS §31) carried over
// exactly. Reads the committed triage_trees.json + golden_vectors.json
// (apps/web/{public/models,tests/fixtures}) — unchanged by this migration.

import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { describe, expect, it } from "vitest";
import { evaluateTrees, type TreeJson } from "../src/treeEvaluator.js";

const here = dirname(fileURLToPath(import.meta.url));
const treesPath = join(here, "../../../apps/web/public/models/triage_trees.json");
const goldenPath = join(here, "../../../apps/web/tests/fixtures/golden_vectors.json");

const trees: TreeJson = JSON.parse(readFileSync(treesPath, "utf8"));
const golden: { model_version: string; vectors: Array<{ features: number[]; expected_class: number }> } = JSON.parse(
  readFileSync(goldenPath, "utf8"),
);

describe(`evaluateTrees matches the server model (v${golden.model_version})`, () => {
  it(`all ${golden.vectors.length} golden vectors agree exactly`, () => {
    let mismatches = 0;
    const details: string[] = [];
    for (const { features, expected_class } of golden.vectors) {
      const { classIndex } = evaluateTrees(trees, features);
      if (classIndex !== expected_class) {
        mismatches++;
        details.push(`expected ${expected_class}, got ${classIndex}`);
      }
    }
    expect(mismatches, details.slice(0, 10).join("\n")).toBe(0);
  });
});
