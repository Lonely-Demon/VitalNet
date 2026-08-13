// The trained advisory tree model, bundled into this edge function so the
// ML "opinion" (clinical-core's triage() in rules_first mode, see
// routes/cases.ts) can run here too. Same artifact apps/web fetches at
// runtime from /models/*.json (backend/scripts/tree_export.py's output) —
// copied into _shared/models/ rather than fetched over the network, since
// `supabase functions deploy` bundles a function's own dependency graph
// rather than serving from a shared static host. Re-copy these two files
// whenever the model is retrained (tools/training/ once Phase 6 lands).
//
// The model is ALWAYS optional: rules/engine.ts is the sole authoritative
// tier source (see triage.ts's module header). If this import were ever
// missing or corrupt, the fix is to omit `trees`/`featureNames` from the
// triage() call, not to block submission — see this module's TRIAGE_TREES/
// FEATURE_NAMES being plain values (a parse failure here fails the whole
// isolate at boot, which is the loud, correct failure mode for a corrupt
// bundled asset — unlike a network fetch, there is no partial-failure case
// to degrade gracefully from).
import treesJson from "./models/triage_trees.json" with { type: "json" };
import featuresConfig from "./models/features_config.json" with { type: "json" };
// @deno-types="../../../../../../packages/clinical-core/dist/index.d.ts"
import type { TreeJson } from "@vitalnet/clinical-core";

export const TRIAGE_TREES = treesJson as unknown as TreeJson;
export const FEATURE_NAMES: readonly string[] = featuresConfig.feature_names;
