# Availability, service objectives and recovery

Fleetwright has a **99% initial operating objective** and a **99.9% future multi-zone objective**.
The current single-server release has no published measured monthly availability or contractual
SLA. Internal health/metrics endpoints do not substitute for independent uptime measurement.

| Availability over 30 days | Time-based error budget | Failed valid requests per 10M |
|---|---|---|
| 99% | 7.2 hours | 100,000 |
| 99.5% | 3.6 hours | 50,000 |
| 99.9% | 43.2 minutes | 10,000 |
| 99.95% | 21.6 minutes | 5,000 |
| 99.99% | 4.32 minutes | 1,000 |

Time-based and request-based availability are different indicators; do not interchange their
results. Publish both the measurement window and numerator/denominator.

## Proposed indicators and promotion

| Service | Good event / measurement | Initial objective / future multi-zone objective |
|---|---|---|
| Console | Independent regional probe renders essential assets and navigation within the agreed deadline | 99% / 99.9% |
| API | Valid authorized request completes without internal failure or overload rejection within its route deadline | 99% / 99.9%, rolling 30 days |
| Live updates | Authorized client receives committed change within 2 s | 99% of sampled deliveries, target |
| Job admission | Permitted proposal persisted with stable identity within 2 s | 99% / 99.9%, targets |
| Queued execution | Approved ready job begins within agreed workflow queue deadline | Per-contract objective, measured separately from destination time |
| Owned freight latency | Detection to confirmed booking | p95 under 1 s, target; historical p95 approximately 540 ms |
| Help assistant response | Valid in-quota question gets an answer (AI or documentation fallback) without a 5xx within the 25 s whole-answer deadline | 99% / 99.9%, rolling 30 days, objective |
| Help assistant AI answers | Eligible question (assistant on, within rate limits and budget) answered by the AI rather than the fallback | 95% over 30 days, objective |
| Help assistant latency | AI answer p95 / documentation fallback p95 | ≤ 15 s / ≤ 2 s, objectives; evaluation-only p95 was 4.98 s |

Count unexpected 429/5xx and timeouts as failures for eligible in-budget traffic. Exclude invalid
credentials/malformed requests and agreed quota excess using documented classifications. Record
destination outages separately, but retain them in the end-to-end workflow indicator. Planned
maintenance consumes the public objective unless a contract explicitly specifies otherwise.

Correctness incidents—wrong approval, tenant crossover or duplicate external action—have no
acceptable error budget. Freeze affected execution, preserve evidence and investigate.

Latency thresholds here are proposed service definitions, not current guarantees. The network
fixture and 50/70-browser hour windows do not supply a rolling 30-day availability denominator.
Promote 99.9% only after representative multi-zone failure/load exercises and independent
measurement establish that the service and operating team can support the objective.

## Help assistant objectives

The assistant's objectives above are written targets, not measurements. The only measured latency
is the 16-question held-out evaluation in the [25 November release record](../releases/2026-11-25.md)
(p95 4.98 s), which is not a production SLI. The 15 s AI p95 objective matches the evaluation
threshold in `config/assistant-eval.yaml`.

- The response objective is the one users rely on: the console always gets an answer, because every
  limit and failure falls back to documentation search. A 5xx or a gateway timeout is a failure;
  a fallback is a success for this indicator.
- The AI-answer objective excludes fallbacks the deployment chose (assistant switched off, hourly
  limit reached, daily budget used up), and counts provider errors, timeouts, Redis failures and
  "busy" fallbacks as misses. Report the excluded fallbacks separately so budget sizing stays visible.
- Correctness of answers is checked by the held-out evaluation, not by this availability objective.
  A tenant-data leak or a claimed action the assistant cannot take is a correctness incident with no
  error budget.

Today these indicators can be read only from the owner-only daily counters and API logs; no assistant
probe or alert exists in the monitor collector yet (see [monitoring](../operations/monitoring.md#help-assistant)).

## Measurement and response plan

The [tier validation plan](validation-plan.md) defines the mixed workload and failure exercises.
[Service ownership](../operations/service-ownership.md) assigns who watches the indicators,
pauses risky releases when the budget is exhausted and coordinates recovery. Maintain the same
eligible-event denominator across normal operation, overload and failure exercises.

Collect independent synthetic probes, request latency/error histograms, queue/outbox age, workflow
unknown counts, session health, database saturation, backup age and restore evidence. Keep metrics
free of payloads/tokens and avoid tenant/job identifiers as unbounded metric labels. Configure
authenticated collection and an accountable notification destination; test alert delivery.

Define burn rate as `eligible error ratio / (1 - SLO)` for each indicator. Use its applicable
initial or multi-zone objective; the same error percentage burns different budgets at 99% and
99.9%. Use multi-window alerts: for a 99.9% objective, 14.4× burn across 1 h and 5 min consumes
about 2% of the 30-day budget in an hour; 6× across 6 h and 30 min consumes about 5% in six hours.
Lower sustained burn opens an investigation. Exhausted budget pauses feature releases while
reliability work proceeds. Review major budget-consuming incidents and publish their user impact.
Both paired windows must breach before paging. Define minimum samples and independent probes for
low-volume periods. Inspect critical routes and tenant classes separately from the aggregate;
record missing/dropped telemetry as unknown coverage, not successful events.

This proposed policy uses [Google SRE's SLO approach](https://sre.google/workbook/implementing-slos/)
and [multi-window alerting guidance](https://sre.google/workbook/alerting-on-slos/). Alert rules,
receivers, escalation ownership and delivery tests must be operational before claiming the policy
is deployed. A threshold document is not an alert-delivery test.

## Recovery objectives

| Deployment | RPO target | RTO target | Required evidence |
|---|---|---|---|
| Single-host baseline | At most 24 h with successful daily archives | At most 4 h, future operating target | Independent archive copy plus full-host recovery drill |
| Multi-zone region | At most 5 min | At most 1 h | PITR, standby failover and application/session/key recovery |
| Regional recovery | Defined per residency/contract | Defined per contract | Cross-region recovery and writer-authority exercise |

Local scheduled archives protect against some database failures; they do not survive loss of the
host without an independently protected copy. Restoration must include roles, application config,
encryption keys and destination session revalidation. Expired leases/unknown actions require
reconciliation after recovery. A rollback cannot undo an accepted destination action.
