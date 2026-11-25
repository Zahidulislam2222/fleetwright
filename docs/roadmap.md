# Roadmap and promotion criteria

Milestones advance on evidence, not promised dates. Substantive changes require written criteria,
automated gates, real-flow verification, independent review and an exact compatible release.

## Implemented capabilities

Fleetwright includes fenced freight claims, warm sessions, filters/schedules, tenant-to-cell routing,
database-clock account pacing, durable raw detections and receipt reconciliation. The console
supports password/TOTP, roles, CSRF, private owner approvals, masked public access, audit and live
updates. General workflows have versioned contracts, scoped/revocable MCP and bounded evidence.

Catalogue crawling has durable progress, bounded pinned HTTP/TLS fetches, quality guards, retention
and private JSONL export. The standalone agent uses SQLite and an installed local model with three
maintained record-saving templates, exact approvals, private state and uncertainty recovery.
Monitoring, renewable observe-only credentials, encrypted off-host recovery and signed exact
artifact tooling are implemented. The AWS reference has offline provider-substituted validation;
no AWS infrastructure has been provisioned by that evidence.

The console help assistant answers from approved public documentation and read-only, tenant-scoped
console data, discloses and marks AI answers, bounds spend before every paid call and falls back to
documentation search. Only the API joins a separate egress network for the model provider
([ADR 0016](adr/0016-assistant-provider-egress.md)).

## Current verification boundary

The current release is `20261125-publication-rc1` (source `d8b1d19`), which publishes this documentation
on the assistant release `20261125-assistant-rc5` (source `26ebe46`), both deployed on 25 November 2026; see the
[current release record](releases/2026-11-25.md). It added the help assistant and patched images;
claims, workers, workflows and crawls are unchanged. Quality, source-security and GitHub CI gates
passed; the assistant passed 18 API tests, 8 unit tests, a real-browser drawer test and a 16/16
held-out live evaluation. The full regression suite did not complete in one clean run on the shared
build machine (one fixture start-up timeout, one load-sensitive test); every test has a passing run
on the assistant source. A drawer layout defect reached production for about one hour before its fix.

Historical: the 15 October publication release (`cd64e6b`) passed 289 tests with six accounted skips,
actual driver/browser-loss recovery and exact owner/MCP/crawler/HTTP/CSP flows, static rollback,
signed parity, fresh two-database restore and scheduler/monitor recovery
([record](releases/2026-10-15.md)). Installed-model templates, 50/70-context hours and independent
encrypted recovery remain dated 13 October evidence. Implementation evidence alone is not publication.

## Expansion milestones

Every tier uses the [validation plan](scaling/validation-plan.md), an assigned
[service/recovery owner](operations/service-ownership.md) and the
[customer-readiness decision](legal/commercial-readiness.md). Legal/data scope, budgets and failure
acceptance are reviewed with the technical milestone. The next public release records completed
deployment/publication gates separately from this forward engineering sequence.

| Priority | Deliverable | Required promotion evidence |
|---|---|---|
| 1 | Periodic operational revalidation | Repeat exact all-worker drain, immutable image/signature parity, live authorization/receipts, supervised backup/monitor and independent fresh encrypted restore after relevant changes |
| 2 | Authorized destination expansion | Maintained account/precondition/action/receipt contract, lawful data scope, rate policy and adversarial real-browser tests |
| 3 | Client assurance | Actual Codex acceptance on releases; Claude run when the owner's account is available, with no automatic paid fallback |
| 4 | Representative fleet scale | Authenticated sustained workload, session renewal, tenant skew, account pacing, destination receipts and drain/move measurements |
| 5 | Security and recovery assurance | Broader ASVS evidence, lower-severity finding review, retention/access tests and timed full-host/key/application recovery |
| 6 | Multi-zone control plane | Redundant API/gateways, database standby/PITR, pooled connections, static spare capacity and zone-failure exercise |
| 7 | 100k then 1M+ simultaneous control-plane users | Sustained mixed workloads, bounded fan-out/refetch, reconnect/slow-client tests, failure exercises and resource/cost curves |
| 8 | Additional crawler delivery formats | Reviewed field/data contracts, destination authorization, durable delivery/retry policy and operational-cost agreement |
| 9 | Additional local-agent integrations | Strict form/receipt contracts and exact human approval beyond the three owned workflows |

## Help assistant next steps

| Priority | Deliverable | Required promotion evidence |
|---|---|---|
| A1 | Dedicated capped provider key per deployment | Each deployment (and later each customer tenant) has its own key and provider-side monthly limit; the in-app daily budget stays below it; key rotation and revocation tested |
| A2 | Evaluation in CI | Free offline checks with a stand-in provider on every change; the paid held-out evaluation runs on an approved schedule or on prompt/model/knowledge changes, with its cost cap and thresholds from `config/assistant-eval.yaml` |
| A3 | Assistant monitoring | Assistant counters exposed to the monitor collector; alerts on budget exhaustion, provider error rate and fallback share; measured cost and latency over a real week |
| A4 | Streaming answers | Incremental output with a stop control, the same deadline/budget accounting and screen-reader-friendly status messages |
| A5 | Egress restriction | An egress proxy limited to the provider host before the API gains any other outbound feature |
| A6 | Scale controls | Budget sharding, per-tenant quotas, cached documentation-only answers and bounded queueing, as in [future architecture](scaling/future-architecture.md#help-assistant-at-scale) |
| A7 | Second provider (option) | Separate privacy/price review, its own evaluation pass and an explicit cost approval; never an automatic paid fallback |

## Future scale and reliability

1M+ simultaneous users describes control-plane sessions across tenants; it does not mean a million
browser actors. The 99% initial operating objective and 99.9% multi-zone objective need explicit
SLIs, windows, error budgets, paging ownership, recovery and representative failure/load evidence.
They are future targets, not measured monthly availability or contractual commitments. See
[scale architecture](scaling/README.md), [capacity](scaling/capacity-model.md) and [SLOs](scaling/slo.md).

Promotion is staged. Each stage must pass every gate below at its declared workload, using the
[validation plan](scaling/validation-plan.md); none of these stages has been run yet. Load, failure,
recovery and error-budget gates come from that plan; the soak lengths are proposed additions recorded
there as proposals, not yet accepted gates.

| Stage | Load | Soak (proposed) | Failure | Recovery | Error budget |
|---|---|---|---|---|---|
| Current single server (99% initial objective) | Burst of 1,000 sessions and ~67 reads/s on an isolated copy ([baseline](scaling/baseline-workload.md)) | 24 h at normal peak with no unbounded memory, queue or connection growth | Gateway, API, Redis and provider outage each degrade to documented behavior | Full-host restore within 4 h RTO / 24 h RPO targets | 30 days of independent probes with ≤ 7.2 h unavailability |
| 1k sessions | 1,000 connected sessions at the declared mix, p95 API latency within route deadlines | 1 h steady state, then 24 h soak | Slow readers, token revocation, cache cold start | Rolling replacement without lost authoritative work | Burn-rate alerts delivered to an owned receiver |
| 10k sessions | 10,000 sessions, skewed tenants, assistant at its quota | 1 h steady + 24 h soak | Reconnect burst, exhausted pool, provider outage | Cell move and drain under load | 30-day report at 99% |
| 100k sessions (multi-zone) | 100,000 sessions, sharded fan-out | 1 h steady + 72 h soak | Replica/cache loss, one-zone evacuation under load | PITR and standby failover within 5 min RPO / 1 h RTO targets | 30-day report at 99.9% before offering it |
| 1M+ sessions | 1,000,000+ sessions with the same declared mix and assistant demand | At least 1 h uninterrupted + 72 h soak at a reduced share | Gateway node, zone and provider loss in the same run | Archive/key/config restore and writer-authority exercise | Rolling 30-day 99.9% with no correctness incident |

A stage advances only when its gates pass and the run records workload, topology, percentiles,
resource peaks and cost. Paid environments need the owner's cost approval before any run.

## Retained limits

The current hosting topology has one failure domain. Fixture endurance is not authenticated freight
capacity. Missing destination receipts remain inconclusive; UNKNOWN actions cannot be blindly retried.
The local browser agent is not an OS sandbox for hostile pages. Static inline-script hashes are
implemented, while inline styles and incomplete cross-origin isolation remain disclosed limitations.
The development-only dependency advisory remains separate from production audits/native image scans.
Off-host data restoration does not establish a second running site or measured recovery objective.
Help-assistant answers can be wrong; its budget is deployment-wide and has no per-tenant quota yet,
and there is no assistant alert in the monitor collector yet. One workflow job has been UNKNOWN since
27 October 2026 and its reconciliation is retried on every loop; it is tracked separately.

Use [testing](testing.md), [security controls](security/controls.md), [legal scope](legal/README.md),
[maintenance](maintenance.md) and [operations](operations/runbooks.md) when planning a promotion.
