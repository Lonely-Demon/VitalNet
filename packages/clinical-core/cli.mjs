#!/usr/bin/env node
// JSONL subprocess CLI for tools/training/train_classifier.py (Phase 6) —
// the single point where Python's synthetic-data generator hands patients
// to THIS package for labeling and feature engineering, instead of
// maintaining a second copy of assign_triage_label/ClinicalFeatureEngineer.
// Import from dist, not src: run `pnpm --filter @vitalnet/clinical-core
// build` first.
//
// Usage (one JSON object per line on stdin, one JSON object per line on
// stdout, in the same order — callers zip input/output by line number):
//   node cli.mjs label              < patients.jsonl > labels.jsonl
//   node cli.mjs engineer-features  < patients.jsonl > features.jsonl
//
// `label` input shape matches rules/engine.ts's EngineInput (patient_age,
// bp_systolic, bp_diastolic, spo2, heart_rate, temperature, symptoms,
// is_pregnant?). Output: {"label": 0|1|2} (ROUTINE/URGENT/EMERGENCY, the
// same integer convention as the old assign_triage_label).
//
// `engineer-features` input shape matches features.ts's FeatureFormInput.
// Output: the flat feature map (feature name -> number), one per line —
// the Python side reindexes it to its own canonical FEATURE_NAMES order.
//
// Fails loudly (non-zero exit, stderr) on the first malformed line or
// thrown error: this is training tooling with a strict 1:1 line contract,
// not a user-facing path — silently skipping a line would desync line
// numbers between input and output.

import { createInterface } from "node:readline";
import { assignTier, buildFeatureMap } from "./dist/index.js";

const TIER_TO_LABEL = { ROUTINE: 0, URGENT: 1, EMERGENCY: 2 };

function usageAndExit() {
  console.error("usage: node cli.mjs <label|engineer-features>  (reads JSONL from stdin)");
  process.exit(2);
}

async function main() {
  const command = process.argv[2];
  if (command !== "label" && command !== "engineer-features") usageAndExit();

  const rl = createInterface({ input: process.stdin, crlfDelay: Infinity });
  let lineNo = 0;
  const out = [];

  for await (const rawLine of rl) {
    lineNo++;
    const line = rawLine.trim();
    if (!line) continue;

    let patient;
    try {
      patient = JSON.parse(line);
    } catch (err) {
      console.error(`cli.mjs: malformed JSON on stdin line ${lineNo}: ${err.message}`);
      process.exit(1);
    }

    try {
      if (command === "label") {
        const { tier } = assignTier(patient);
        out.push(JSON.stringify({ label: TIER_TO_LABEL[tier] }));
      } else {
        const features = buildFeatureMap(patient);
        out.push(JSON.stringify(features));
      }
    } catch (err) {
      console.error(`cli.mjs: ${command} failed on stdin line ${lineNo}: ${err.stack || err.message}`);
      process.exit(1);
    }
  }

  process.stdout.write(out.join("\n") + (out.length ? "\n" : ""));
}

main();
