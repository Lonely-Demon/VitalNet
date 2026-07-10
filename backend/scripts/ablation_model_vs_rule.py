"""
Disagreement ablation — does the trained model deviate from the heuristic
(`train_classifier.py::assign_triage_label`) it was trained to reproduce, and
in which direction?

VitalNet's model is a distillation: it is trained to reproduce a deterministic,
evidence-informed scoring rule on synthetic patients the same rule labelled.
No real ground truth exists, so the most meaningful measurable question is how
often — and in which direction — the learned model departs from that
transparent rule. Over-triage (model > rule) is the safe direction;
under-triage (model < rule) is the clinically dangerous one, and every such
departure is an UNVALIDATED de-escalation below an evidence-based rule.

Measured at two levels:
  (1) raw model  = clf.predict()      — isolates the learned model
  (2) production = predict_triage()   — safety net + NEWS2 floor + model (shipped)

Patients are freshly generated with a seed DIFFERENT from training (12345 vs
42), so they are genuinely out-of-sample.

This is the empirical basis for docs/CLINICAL_RISK_MANAGEMENT.md §3 and the
rules-primary architecture question in docs/VALIDATION_PROTOCOL.md.

Run:
    cd backend && pip install -r requirements.txt      # needs numpy, scikit-learn, shap
    PYTHONPATH=. python scripts/ablation_model_vs_rule.py

(The onnx export path used by train_classifier.py is stubbed here — this
ablation never exports a model, so onnx/skl2onnx are not required.)
"""
import importlib.util
import os
import sys
import types
import warnings

import numpy as np

warnings.filterwarnings("ignore")

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, BACKEND_DIR)

# Stub the onnx-only export module so importing train_classifier doesn't require
# onnx/skl2onnx. The ablation reuses only the generator + label functions.
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
    print(f"\n=== {name} vs heuristic rule (n={n}) ===")
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
    rule = np.array([tc.assign_triage_label(p) for p in patients])
    print("Rule-label distribution on fresh sample:",
          {LABEL[k]: int((rule == k).sum()) for k in (0, 1, 2)})

    X = np.array([[tc.engineer.engineer_features(p)[nm] for nm in tc.FEATURE_NAMES]
                  for p in patients], dtype=np.float32)

    raw = clf_mod._classifier.predict(X)
    prod = np.array([LEVEL_IDX[clf_mod.predict_triage(p)["triage_level"]] for p in patients])

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
