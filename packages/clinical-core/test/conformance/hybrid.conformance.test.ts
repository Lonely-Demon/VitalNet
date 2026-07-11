// The one-time (+ re-runnable) conformance gate for the TypeScript
// migration (Round 6 rebuild plan, Phase 1 / DECISIONS.md §32): replays
// the 10,000 patients in patients_with_python_tier.jsonl — each already
// labeled by the CURRENT PRODUCTION Python path
// (app.ml.classifier.predict_triage, via
// backend/scripts/export_conformance_patients.py) — through clinical-core's
// triage() in "hybrid" mode, which reproduces that exact safety-net ->
// model -> NEWS2-floor order. Any mismatch here is a real port bug, not an
// expected divergence: hybrid mode's entire purpose is bit-for-bit parity
// with today's production semantics before rules_first ever ships.
//
// Regenerate the fixture with:
//   cd backend && python scripts/export_conformance_patients.py [N]

import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { createInterface } from "node:readline";
import { createReadStream } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { triage, type TriageFormInput } from "../../src/triage.js";
import type { TreeJson } from "../../src/treeEvaluator.js";

const here = dirname(fileURLToPath(import.meta.url));
const patientsPath = join(here, "patients_with_python_tier.jsonl");
const reportPath = join(here, "report.md");
const treesPath = join(here, "../../../../apps/web/public/models/triage_trees.json");
const featuresConfigPath = join(here, "../../../../apps/web/public/models/features_config.json");

interface ConformanceRecord extends TriageFormInput {
  python_tier: "ROUTINE" | "URGENT" | "EMERGENCY";
  python_confidence: number;
  python_safety_net_triggered: boolean;
}

async function readJsonl(path: string): Promise<ConformanceRecord[]> {
  const records: ConformanceRecord[] = [];
  const rl = createInterface({ input: createReadStream(path, "utf8"), crlfDelay: Infinity });
  for await (const line of rl) {
    if (line.trim()) records.push(JSON.parse(line));
  }
  return records;
}

describe.skipIf(!existsSync(patientsPath))(
  "clinical-core triage() (hybrid mode) matches Python predict_triage",
  () => {
    it("agrees with the Python-labeled conformance set", async () => {
      const records = await readJsonl(patientsPath);
      const trees: TreeJson = JSON.parse(readFileSync(treesPath, "utf8"));
      const featuresConfig: { feature_names: string[] } = JSON.parse(readFileSync(featuresConfigPath, "utf8"));

      const confusion: Record<string, Record<string, number>> = {};
      const mismatches: Array<{ index: number; python: string; ts: string; patient: ConformanceRecord }> = [];

      for (let i = 0; i < records.length; i++) {
        const record = records[i]!;
        const result = triage(record, { mode: "hybrid", trees, featureNames: featuresConfig.feature_names });

        confusion[record.python_tier] ??= {};
        confusion[record.python_tier]![result.tier] = (confusion[record.python_tier]![result.tier] ?? 0) + 1;

        if (result.tier !== record.python_tier) {
          mismatches.push({ index: i, python: record.python_tier, ts: result.tier, patient: record });
        }
      }

      const n = records.length;
      const agreementPct = (((n - mismatches.length) / n) * 100).toFixed(3);

      const lines = [
        "# Hybrid-mode conformance report",
        "",
        `Generated from ${n} synthetic patients (backend/scripts/export_conformance_patients.py, seed 20260711).`,
        `Each was labeled by Python's \`predict_triage\` (production, pre-migration) and replayed through`,
        "clinical-core's `triage()` in `hybrid` mode (safety-net override -> trained model -> NEWS2 floor —",
        "the same order as the Python path).",
        "",
        `**Agreement: ${n - mismatches.length}/${n} (${agreementPct}%)**`,
        "",
        "## Confusion matrix (rows = Python tier, columns = TS tier)",
        "",
        "| Python \\ TS | ROUTINE | URGENT | EMERGENCY |",
        "|---|---|---|---|",
        ...(["ROUTINE", "URGENT", "EMERGENCY"] as const).map(
          (row) =>
            `| ${row} | ${confusion[row]?.ROUTINE ?? 0} | ${confusion[row]?.URGENT ?? 0} | ${confusion[row]?.EMERGENCY ?? 0} |`,
        ),
        "",
        mismatches.length > 0 ? "## Mismatches (first 20)" : "## Mismatches: none",
        "",
        ...mismatches.slice(0, 20).map(
          (m) =>
            `- #${m.index}: python=${m.python} ts=${m.ts} — age=${m.patient.patient_age}, ` +
            `bp=${m.patient.bp_systolic}/${m.patient.bp_diastolic}, hr=${m.patient.heart_rate}, ` +
            `spo2=${m.patient.spo2}, temp=${m.patient.temperature}, symptoms=${JSON.stringify(m.patient.symptoms)}`,
        ),
        "",
      ];
      writeFileSync(reportPath, lines.join("\n"));

      // Hybrid mode's entire purpose is exact parity with the Python path —
      // any mismatch is a real port bug to fix, not an expected divergence.
      expect(mismatches.length, `${mismatches.length} mismatch(es) — see ${reportPath}`).toBe(0);
    });

    // Informational only (not a pass/fail gate): quantifies how the TARGET
    // architecture (rules_first — rules engine 100% authoritative, model
    // advisory-only) would have triaged the same 10k patients differently
    // from today's production (Python predict_triage, replayed above as the
    // hybrid-mode baseline). This is the delta DECISIONS §32 must record
    // when rules_first ships (Phase 4) — generated here because the same
    // conformance set and harness make it nearly free.
    it("quantifies the rules_first vs. current-production delta (informational)", async () => {
      const records = await readJsonl(patientsPath);
      const trees: TreeJson = JSON.parse(readFileSync(treesPath, "utf8"));
      const featuresConfig: { feature_names: string[] } = JSON.parse(readFileSync(featuresConfigPath, "utf8"));

      const confusion: Record<string, Record<string, number>> = {};
      const deltas: Array<{ index: number; python: string; rulesFirst: string; modelAgreed: boolean }> = [];

      for (let i = 0; i < records.length; i++) {
        const record = records[i]!;
        const result = triage(record, { mode: "rules_first", trees, featureNames: featuresConfig.feature_names });

        confusion[record.python_tier] ??= {};
        confusion[record.python_tier]![result.tier] = (confusion[record.python_tier]![result.tier] ?? 0) + 1;

        if (result.tier !== record.python_tier) {
          deltas.push({ index: i, python: record.python_tier, rulesFirst: result.tier, modelAgreed: result.modelAgreed ?? false });
        }
      }

      const n = records.length;
      const changedPct = ((deltas.length / n) * 100).toFixed(3);
      const upgrades = deltas.filter((d) => rank(d.rulesFirst) > rank(d.python)).length;
      const downgrades = deltas.filter((d) => rank(d.rulesFirst) < rank(d.python)).length;

      const lines = [
        "",
        "---",
        "",
        "# rules_first vs. current-production delta (informational, DECISIONS §32 input)",
        "",
        `Same ${n} patients, replayed through \`triage()\` in \`rules_first\` mode (the target end-state:`,
        "rules engine 100% authoritative, model advisory-only) instead of `hybrid` mode above.",
        "",
        `**Changed: ${deltas.length}/${n} (${changedPct}%)** — ${upgrades} upgraded to a higher tier, ${downgrades} downgraded to a lower tier.`,
        "",
        "## Confusion matrix (rows = Python/hybrid tier, columns = rules_first tier)",
        "",
        "| Python \\ rules_first | ROUTINE | URGENT | EMERGENCY |",
        "|---|---|---|---|",
        ...(["ROUTINE", "URGENT", "EMERGENCY"] as const).map(
          (row) =>
            `| ${row} | ${confusion[row]?.ROUTINE ?? 0} | ${confusion[row]?.URGENT ?? 0} | ${confusion[row]?.EMERGENCY ?? 0} |`,
        ),
        "",
        deltas.length > 0 ? "## Sample of changed cases (first 20)" : "## No changes",
        "",
        ...deltas
          .slice(0, 20)
          .map((d) => `- #${d.index}: python=${d.python} -> rules_first=${d.rulesFirst} (model agreed with rules_first: ${d.modelAgreed})`),
        "",
      ];

      // Append to the same report file — informational, no assertion on the
      // delta size (rules_first is EXPECTED to differ by design; that's the
      // point of item 2 in the rebuild plan).
      const existing = readFileSync(reportPath, "utf8");
      writeFileSync(reportPath, existing + lines.join("\n"));
    });
  },
);

function rank(tier: string): number {
  return tier === "EMERGENCY" ? 2 : tier === "URGENT" ? 1 : 0;
}
