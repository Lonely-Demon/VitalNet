# VitalNet — Service Level Objectives

**Status: target objectives, not yet measured against live production
traffic.** VitalNet has no live deployment with real patient volume as of
this document. These are the SLOs a rural-clinic clinical decision-support
tool should be held to, and the SLIs/instrumentation needed to check them
— written now so the moment real traffic exists, there's something to
measure against, rather than inventing targets after the fact to match
whatever the numbers happened to be. Revise the targets once real traffic
data exists; don't quietly leave stale aspirational numbers here.

## Why this document exists

An SLO without a real incident/error-budget process behind it is just a
number on a page — this document is honest about that gap (see "What
this isn't," below). What it *is* good for now: a concrete definition of
"working correctly" for this specific clinical-triage system, so a future
on-call engineer or ops team has a starting point instead of guessing.

## Service Level Indicators (SLIs)

Sourced from `GET /api/metrics` (`app/core/metrics.py`, Prometheus
format, admin-only) plus `GET /api/health`:

| SLI | Metric | Source |
|---|---|---|
| Availability | `up{job="vitalnet-backend"}` (via your Prometheus scrape) or `/api/health` returning `200` | Scrape target health / health endpoint |
| Request latency | `vitalnet_http_request_duration_seconds` (histogram, labeled by `method`/`route`) | Metrics middleware, every request |
| Error rate | `vitalnet_http_requests_total{status=~"5.."}` / `vitalnet_http_requests_total` | Metrics middleware |
| Rate-limit rejection rate | `vitalnet_http_requests_total{status="429"}` | Metrics middleware |
| Triage classification volume/mix | `vitalnet_triage_classifications_total{triage_level=...}` | `cases.py::submit_case`, only on genuinely-new submissions |

## Service Level Objectives (targets)

### Availability

| Target | Window |
|---|---|
| 99.5% | Rolling 30 days |

Rationale for 99.5% rather than a stricter 99.9%+: this is a single-region
deployment on Railway/Vercel-class infrastructure (`README.md`'s
Deployment section), not a multi-region active-active system — 99.5%
(~3.6 hours/month) is an honest target for that architecture, not an
aspirational one. Raising it requires the infrastructure investment
first (multi-instance + `RATE_LIMIT_STORAGE_URI` shared store,
`docs/DECISIONS.md` §4/§8's horizontal-scaling notes), not just a document
edit.

### Latency

| Endpoint class | p50 | p90 | p99 |
|---|---|---|---|
| `POST /api/cases` (submit + triage + LLM briefing) | < 2.5s | < 6s | < 12s |
| Read endpoints (`GET /api/cases`, `/api/analytics/*`) | < 300ms | < 800ms | < 2s |
| `GET /api/health` | < 100ms | < 300ms | < 1s |

The submit-case target is wide because `app/services/llm.py`'s 4-tier LLM
fallback (Groq 70B → Groq 8B → Gemini Flash → Gemini Flash-Lite) can take
several seconds on a downgrade — and because the triage classification
itself (the clinically load-bearing part) is LLM-independent and returns
in milliseconds; a slow LLM briefing degrades UX, not safety
(`docs/CLINICAL_GOVERNANCE.md`'s guardrail #2).

### Error rate

| Target | Window |
|---|---|
| < 0.5% of requests return 5xx | Rolling 7 days |

429s (rate-limited) are tracked separately and are **not** counted as
errors for this SLO — a 429 is the rate limiter working as designed
(`docs/DECISIONS.md` §8), not a service failure. A sustained spike in 429s
is still worth investigating (either legitimate load growth needing a
higher limit, or an abuse pattern) — see `docs/INCIDENT_RESPONSE.md`.

### Triage availability — the one SLO that's actually load-bearing clinically

**Target: the triage pipeline must return a classification for every
well-formed submission, 100% of the time, online or offline.**

This is not a statistical target with an error budget — it's a hard
design invariant already built and tested for, not something this
document is introducing:
- Online: `predict_triage()`'s three layers (deterministic safety net →
  trained model → NEWS2 floor, `MODEL_CARD.md`) mean a triage is produced
  even for inputs the model was never trained on.
- Offline: the JS tree evaluator + the same safety-net/NEWS2 logic
  mirrored in `triageClassifier.js` (Option 6, `docs/DECISIONS.md` §2)
  gives the same guarantee with no network dependency.
- `tests/test_classifier_safety.py` asserts this in CI on every commit —
  the SLO for this one is "the test suite," not a production dashboard.

## Error budget

At 99.5% monthly availability, the budget is ~3.6 hours/month of
acceptable downtime. There is currently no automated error-budget
tracking or burn-rate alerting — this section states the arithmetic, not
a working alerting pipeline (see "What this isn't").

## Example queries (PromQL)

Once scraped into a real Prometheus instance:

```promql
# p99 latency for case submission
histogram_quantile(0.99, sum(rate(vitalnet_http_request_duration_seconds_bucket{route="/api/cases"}[5m])) by (le))

# 5xx error rate, all routes
sum(rate(vitalnet_http_requests_total{status=~"5.."}[5m])) / sum(rate(vitalnet_http_requests_total[5m]))

# EMERGENCY-classification rate (a sudden shift here is worth a look — see docs/CLINICAL_GOVERNANCE.md's drift monitoring)
sum(rate(vitalnet_triage_classifications_total{triage_level="EMERGENCY"}[1h]))
```

### Scrape configuration

`/api/metrics` is admin-gated like every other admin surface
(`test_admin_authz.py`). Prometheus supports a static bearer token for a
scrape job:

```yaml
scrape_configs:
  - job_name: vitalnet-backend
    metrics_path: /api/metrics
    scheme: https
    bearer_token: "<a long-lived JWT for an admin service account>"
    static_configs:
      - targets: ["your-backend.up.railway.app"]
```

Provisioning that service account and rotating its token is an
operational task for the deployment, not something this repository can
do on its own.

## What this isn't

- **Not a validated production track record** — there is no live traffic
  to have validated these numbers against yet. Treat every number above
  as "the target we'd defend," not "the number we've measured."
- **Not an alerting pipeline** — no Alertmanager rules, no PagerDuty/on-call
  integration exist in this repository. The PromQL queries above are a
  starting point for writing real alert rules once there's a real
  Prometheus/Alertmanager deployment to write them into.
- **Not a substitute for `docs/DISASTER_RECOVERY.md` or
  `docs/INCIDENT_RESPONSE.md`** — this document defines "what good looks
  like"; those two define what to do when it isn't.
