# Design proposal — rules-primary triage (ML demoted to advisory)

> **Status: DESIGN ONLY — not implemented, decision required.** This document
> proposes a change to how the *final* triage tier is chosen. It does **not**
> change any runtime behaviour on its own; merging this file is safe. Wiring the
> change into `classifier.py` must not happen without the validation gate in §5
> (and ideally clinician review of the rule), because it alters clinical output.

## 1. Why (the evidence)

The model-vs-rule ablation (`scripts/ablation_model_vs_rule.py`,
`CLINICAL_RISK_MANAGEMENT.md §3`) established:

- The trained model reproduces the deterministic evidence-based scorer 98.65% of
  the time — it is largely a **distillation** of that rule.
- Its deviations are **net-negative on safety**: raw under-triage 0.73% > raw
  over-triage 0.61%.
- After the current partial guardrails, **191/60,000 cases still ship *below*
  the evidence-based rule**, including **8 two-tier EMERGENCY→ROUTINE drops**;
  130 of 16,218 rule-EMERGENCY cases (0.80%) ship below EMERGENCY — each an
  **unvalidated** de-escalation.

There is no ground truth to justify those de-escalations, and an opaque model is
not clinician-reviewable. So the model should not be allowed to set a tier
*lower* than the transparent rule.

## 2. Current architecture (ML-primary)

```
T_final = model.predict()          # opaque, primary
          then safety_net()        # can only escalate the UNAMBIGUOUS extremes
          then news2_floor()       # can only lift ROUTINE→URGENT on one vital
```

The deterministic rules are a *partial* wrap that catches only the unambiguous
subset. The model owns the decision everywhere else — including the ambiguous
band where its unvalidated de-escalations live.

## 3. Proposed architecture (rules-primary, ML-advisory)

Promote the **full** evidence-based scorer (`train_classifier.py::assign_triage_label`,
today used only to *label training data*) to an inference-time function
`T_rule`, and choose:

```
T_final = max(T_rule, T_model)     # model may only ESCALATE above the rule
advisory_disagreement = (T_model < T_rule)   # recorded, NOT acted on
```

- **`T_rule` is the primary, auditable decision** — a clinician can read, sign
  off on, and a regulator can inspect it. It is deterministic and mirrors 1:1 in
  the JS offline evaluator (no parity risk).
- **The model can still add value in the safe direction** — if it sees risk the
  additive rule misses, `max()` honours the escalation.
- **The dangerous direction is eliminated by construction**: `T_final` can never
  be below `T_rule`, so the 130 rule-EMERGENCY de-escalations and all
  under-triage-below-rule go to **zero**.
- **The disagreement becomes a research signal, not a silent risk**: every
  `T_model < T_rule` case is flagged (surfaced to the doctor as "model second
  opinion was lower" and logged) so that, once real outcome data exists, you can
  evaluate whether the model's de-escalations would have been correct — the
  principled way to later *promote* the model on evidence.

This keeps the ML in the one role it can safely hold pre-validation, and makes
the clinician sign-off you need actually obtainable (they review a rule, not
weights).

## 4. Implementation sketch (when approved)

1. Extract `assign_triage_label`'s scorer into a shared, import-light module
   (e.g. `app/ml/rule_scorer.py`) used by **both** `train_classifier.py` and
   `classifier.py` — single source of truth, no drift.
2. In `predict_triage()`: compute `T_rule` and `T_model`; set
   `T_final = max(T_rule, T_model)`; add `advisory_model_tier`,
   `advisory_disagreement`, and a `decision_source` field
   (`"rule" | "model_escalation"`).
3. Mirror `rule_scorer` in `frontend/src/utils/` and extend the parity tests +
   regenerate golden vectors (the rule is deterministic → parity is
   straightforward).
4. Update `MODEL_CARD.md`, `CLINICAL_RISK_MANAGEMENT.md` (H1 residual drops),
   and the UI copy (show the rule as primary, the model as a second opinion).
5. Re-run the ablation: under-triage-below-rule must be 0 by construction.

## 5. Validation gate (before wiring into the triage path)

- Run `scripts/evaluate_on_real.py` on a real external dataset **before and
  after** the change; confirm EMERGENCY sensitivity does not regress and quantify
  the over-triage change (see §6).
- Ideally, clinician review of `rule_scorer` (this design makes that review
  tractable).
- Update the risk file and model card in the same change.

## 6. Tradeoff (state it honestly)

`max(T_rule, T_model)` **increases over-triage** — more patients escalated than
either component alone. Over-triage is the safe direction, but it has real costs
(clinician load, alarm fatigue — itself a hazard). The current guardrails
already add a ~7% over-triage margin; this would add somewhat more. The
`evaluate_on_real.py` harness measures exactly this, so the tradeoff is a
number, not a guess. The counter-argument for keeping ML-primary — that the
boosted trees capture interactions the additive rule misses — is real but
**unvalidated**; until real data confirms those interactions are correct, the
safe default is to let the model escalate but not de-escalate.

## 7. Recommendation

Adopt rules-primary. It removes the entire class of unvalidated under-triage,
preserves the model's safe-direction value, converts disagreements into a future
validation signal, and — critically for VitalNet's actual bottleneck — makes the
triage logic something a clinician can review and sign off on.
