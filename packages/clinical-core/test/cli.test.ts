// Exercises cli.mjs as an actual subprocess (not by importing its internals)
// — this is the exact invocation shape tools/training/train_classifier.py
// (Phase 6) will use, so a drift between cli.mjs and dist/index.js's
// exports fails here first. Requires dist/ to be built (package.json's
// "pretest" hook builds before vitest runs).

import { spawnSync } from "node:child_process";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const here = dirname(fileURLToPath(import.meta.url));
const cliPath = join(here, "../cli.mjs");

function runCli(command: string, inputLines: string[]) {
  const result = spawnSync(process.execPath, [cliPath, command], {
    input: inputLines.join("\n") + "\n",
    encoding: "utf8",
  });
  return result;
}

describe("cli.mjs label", () => {
  it("labels a healthy patient ROUTINE (0) and an extreme-BP patient EMERGENCY (2)", () => {
    const result = runCli("label", [
      JSON.stringify({
        patient_age: 40,
        bp_systolic: 120,
        bp_diastolic: 80,
        spo2: 98,
        heart_rate: 74,
        temperature: 37.0,
        symptoms: [],
      }),
      JSON.stringify({
        patient_age: 40,
        bp_systolic: 65,
        bp_diastolic: 40,
        spo2: 98,
        heart_rate: 74,
        temperature: 37.0,
        symptoms: [],
      }),
    ]);

    expect(result.status).toBe(0);
    const lines = result.stdout.trim().split("\n").map((l) => JSON.parse(l));
    expect(lines).toEqual([{ label: 0 }, { label: 2 }]);
  });

  it("exits non-zero with a line number on malformed JSON", () => {
    const result = runCli("label", ["not json"]);
    expect(result.status).toBe(1);
    expect(result.stderr).toMatch(/line 1/);
  });
});

describe("cli.mjs engineer-features", () => {
  it("emits a flat feature map matching buildFeatureMap's keys", () => {
    const result = runCli("engineer-features", [
      JSON.stringify({
        patient_age: 40,
        patient_sex: "male",
        bp_systolic: 120,
        bp_diastolic: 80,
        spo2: 98,
        heart_rate: 74,
        temperature: 37.0,
        symptoms: [],
        chief_complaint: "Fever",
        complaint_duration: "1-3 days",
        location: "Rural District",
        known_conditions: "",
      }),
    ]);

    expect(result.status).toBe(0);
    const [features] = result.stdout.trim().split("\n").map((l) => JSON.parse(l));
    expect(features.age).toBe(40);
    expect(features.bp_systolic).toBe(120);
    expect(typeof features.shock_index).toBe("number");
  });
});
