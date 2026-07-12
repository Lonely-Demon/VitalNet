"""
Disagreement ablation — does the trained model deviate from the rule
(clinical-core's `assignTier`, via `train_classifier.py::assign_triage_labels`)
it was trained to reproduce, and in which direction?

VitalNet's model is a distillation: it is trained to reproduce a deterministic,
evidence-informed rules engine on synthetic patients the same engine labelled.
No real ground truth exists, so the most meaningful measurable question is how
often — and in which direction — the learned model departs from that
transparent rule. Over-triage (model > rule) is the safe direction;
under-triage (model < rule) is the clinically dangerous one, and every such
departure is an UNVALIDATED de-escalation below an evidence-based rule.

Measured at two levels:
  (1) raw model  = clf.predict()      — isolates the learned model
  (2) production = predict_triage()   — backend/app/ml/classifier.py's live,
                                         model-primary path (safety net +
                                         model + NEWS2 floor) — unaffected by
                                         the Round 6 rebuild's training-side
                                         rewiring below

This is a DIFFERENT, complementary question to the one
packages/clinical-core/test/conformance/report.md already answers. That
report compares the server's PRODUCTION tier against clinical-core's
`rules_first` tier (i.e. does today's deployed behaviour match the target
end-state). This script instead isolates the RAW model from every guardrail,
so it can answer "how much of the guardrail layer's work is actually
necessary" — how many of the model's own under-triages would reach a real
user if the safety net and NEWS2 floor did not exist. Read both.

*** A note on the RAW MODEL numbers below, found while adapting this script
to the Round 6 rebuild (verified with a direct old-vs-new label diff, not
assumed): they will look considerably worse here than a pre-Round-6 run of
this same ablation reported (raw under-triage ~7% here vs ~0.7% before). This
is NOT a model regression — the reference standard changed, not the model.
Pre-migration, `train_classifier.py::assign_triage_label` (used only to
generate TRAINING labels) never called the NEWS2-floor check; that check
(`_news2_concerning_vital`) ran ONLY at inference time, as the last layer of
`predict_triage()`. clinical-core's `assignTier()` unifies both roles behind
one function (Round 6's whole point), so `packages/clinical-core/cli.mjs
label` — this script's rule reference — now applies that floor to labels
too, a scope widening the original two-function Python split never had. The
shipped v3.1.0 model was trained on the OLD, floor-free labels, so of course
it now "disagrees" more with a reference that floors ~7% of cases the raw
model alone wouldn't. The PRODUCTION-path numbers below are the ones that
actually matter for real users today, and they are ~unchanged from the
pre-migration run (predict_triage() has always applied this exact floor at
inference) — see "Do the deterministic guardrails rescue..." below: ~96% of
the raw model's now-larger under-triage set is caught by that same existing
floor before it would ever reach a patient. The real, forward-looking
consequence is for the NEXT retrain: piping labels through assignTier()
means future models will be trained on a measurably more conservative label
set near the ROUTINE/URGENT boundary than v3.1.0 was — worth a DECISIONS.md
note before that retrain happens, not a silent drift.

Patients are freshly generated with a seed DIFFERENT from training (12345 vs
42), so they are genuinely out-of-sample.

This is the empirical basis for docs/CLINICAL_RISK_MANAGEMENT.md §3 and the
rules-primary architecture question in docs/VALIDATION_PROTOCOL.md /
docs/RULES_PRIMARY_DESIGN.md.

Run:
    pnpm --filter @vitalnet/clinical-core build   # cli.mjs imports dist/, not src/
    cd backend && pip install -r requirements.txt      # needs numpy, scikit-learn, shap
    PYTHONPATH=backend python tools/training/ablation_model_vs_rule.py

(The onnx export path used by train_classifier.py is stubbed here — this
ablation never exports a model, so onnx/skl2onnx are not required. Labeling
and feature engineering both shell out to Node via clinical-core's cli.mjs,
same as train_classifier.py itself — see that file's module docstring.)
"""
import importlib.util
import os
import sys
import types
import warnings

import numpy as np

warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
sys.path.insert(0, BACKEND_DIR)

# Stub the onnx-only export module so importing train_classifier doesn't require
# onnx/skl2onnx. The ablation reuses only the generator + CLI-bridging functions.
_stub = types.ModuleType("tree_export")
_stub.onnx_to_tree_json = lambda *a, **k: None
_stub.evaluate_tree_json = lambda *a, **k: (None,)
sys.modules["tree_export"] = _stub

_spec = importlib.util.spec_from_file_location(
    "train_classifier", os.path.join(HERE, "train_classifier.py")
)
tc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tc)

from app.ml import classifier as clf_mod  # noqa: E402

N = 60000
SEED = 12345  # != training seed (42)
LABEL = {0: "ROUTINE", 1: "URGENT", 2: "EMERGENCY"}
LEVEL_IDX = {"ROUTINE": 0, "URGENT": 1, "EMERGENCY": 2}


def _generate(n):
    np.random.seed(SEED)
    severities = ["healthy", "mild", "moderate", "severe", "critical"]
    weights = [0.30, 0.22, 0.22, 0.16, 0.10]
    pediatric_fraction = 0.22
    out = []
    for _ in range(n):
        sev = np.random.choice(severities, p=weights)
        ped = np.random.random() < pediatric_fraction
        out.append(tc.generate_patient(sev, pediatric=ped))
    return out


def _summarize(name, pred, rule, n):
    agree = int((pred == rule).sum())
    over = int((pred > rule).sum())
    under = int((pred < rule).sum())
    print(f"\n=== {name} vs rules-engine label (n={n}) ===")
    print(f"  agreement : {agree / n * 100:6.2f}%  ({agree})")
    print(f"  over-tri. : {over / n * 100:6.2f}%  ({over})   [safe: model > rule]")
    print(f"  UNDER-tri.: {under / n * 100:6.2f}%  ({under})   [UNSAFE: model < rule]")
    for r in (2, 1):
        for m in range(r):
            c = int(((rule == r) & (pred == m)).sum())
            if c:
                tag = "  <-- EMERGENCY missed" if r == 2 and m == 0 else ""
                print(f"     rule={LABEL[r]:9} -> pred={LABEL[m]:9}: {c:5d} "
                      f"({c / n * 100:.3f}%){tag}")


def main():
    clf_mod.load_classifier()  # loads the committed pkl (real shipped path)
    print("Model version:", clf_mod._model_version)

    patients = _generate(N)

    print(f"Labeling {N} patients via clinical-core cli.mjs (rules engine, "
          "the ground truth this ablation measures deviation from) ...")
    rule = np.array(tc.assign_triage_labels(patients))
    print("Rule-label distribution on fresh sample:",
          {LABEL[k]: int((rule == k).sum()) for k in (0, 1, 2)})

    print("Engineering features via clinical-core cli.mjs (same canonical "
          "path train_classifier.py uses; feeds the raw sklearn model) ...")
    feature_maps = tc.engineer_features_batch(patients)
    X = np.array([[fm[name] for name in tc.FEATURE_NAMES] for fm in feature_maps],
                 dtype=np.float32)

    raw = clf_mod._classifier.predict(X)
    # Production path is deliberately per-patient, unbatched: it's exactly
    # the function backend/app/api/routes/cases.py::submit_case calls for a
    # real submission, feature-engineered by the LIVE Python ClinicalFeatureEngineer
    # (backend/app/ml/clinical_features.py), not the CLI bridge above — this
    # is what actually runs in production today, so it must not be
    # substituted with the training-side path.
    prod = np.array([LEVEL_IDX[clf_mod.predict_triage(p)["triage_level"]] for p in patients])

    print("\n[note] The RAW MODEL numbers below reflect a reference standard that now")
    print("       includes the NEWS2 floor at label-generation time (Round 6 unified")
    print("       assignTier() into both roles) — the shipped v3.1.0 model was trained")
    print("       WITHOUT that floor in its labels, so raw under-triage vs this rule is")
    print("       higher than a pre-migration run of this script reported. This is a")
    print("       reference-standard change, not a model regression — see this file's")
    print("       module docstring for the full explanation. PRODUCTION PATH below is")
    print("       what real users actually get today, and is ~unchanged.")
    _summarize("RAW MODEL (clf.predict)", raw, rule, N)
    _summarize("PRODUCTION PATH (predict_triage)", prod, rule, N)

    raw_under = raw < rule
    rescued = int((raw_under & (prod >= rule)).sum())
    still = int((raw_under & (prod < rule)).sum())
    print("\n=== Do the deterministic guardrails rescue the model's under-triages? ===")
    print(f"  raw-model under-triages           : {int(raw_under.sum())}")
    print(f"  ...rescued by safety-net/NEWS2floor: {rescued}")
    print(f"  ...STILL under-triaged in prod     : {still}  ({still / N * 100:.3f}% of all cases)")

    em = rule == 2
    em_under = int((em & (prod < 2)).sum())
    print("\n=== EMERGENCY safety (rule=EMERGENCY) ===")
    print(f"  rule EMERGENCY count              : {int(em.sum())}")
    print(f"  ...shipped BELOW emergency (prod) : {em_under} "
          f"({em_under / max(1, int(em.sum())) * 100:.3f}% of rule-emergencies)")


if __name__ == "__main__":
    main()
