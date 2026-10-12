# Availability, service objectives and recovery

Fleetwright has a **99% minimum future operating objective** and a **99.9% multi-zone target**.
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

## Proposed indicators

| Service | Good event / measurement | Objective after validation |
|---|---|---|
| Console | Independent regional probe renders essential assets and navigation | At least 99%; 99.9% multi-zone/CDN target |
| API | Valid authorized request completes without internal failure or overload rejection within its route deadline | 99.9% over rolling 30 days |
| Live updates | Authorized client receives committed change within 2 s | 99% of sampled deliveries, target |
| Job admission | Permitted proposal persisted with stable identity within 2 s | 99.9%, target |
| Queued execution | Approved ready job begins within agreed workflow queue deadline | Per-contract objective, measured separately from destination time |
| Owned freight latency | Detection to confirmed booking | p95 under 1 s, target; historical p95 approximately 540 ms |

Count unexpected 429/5xx and timeouts as failures for eligible in-budget traffic. Exclude invalid
credentials/malformed requests and agreed quota excess using documented classifications. Record
destination outages separately, but retain them in the end-to-end workflow indicator. Planned
maintenance consumes the public objective unless a contract explicitly specifies otherwise.

Correctness incidents—wrong approval, tenant crossover or duplicate external action—have no
acceptable error budget. Freeze affected execution, preserve evidence and investigate.

## Measurement and response plan

Collect independent synthetic probes, request latency/error histograms, queue/outbox age, workflow
unknown counts, session health, database saturation, backup age and restore evidence. Keep metrics
free of payloads/tokens and avoid tenant/job identifiers as unbounded metric labels. Configure
authenticated collection and an accountable notification destination; test alert delivery.

Use multi-window burn-rate alerts: for a 99.9% objective, 14.4× burn across 1 h and 5 min consumes
about 2% of the 30-day budget in an hour; 6× across 6 h and 30 min consumes about 5% in six hours.
Lower sustained burn opens an investigation. Exhausted budget pauses feature releases while
reliability work proceeds. Review major budget-consuming incidents and publish their user impact.
This policy follows [Google SRE's SLO guidance](https://sre.google/workbook/implementing-slos/).

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
