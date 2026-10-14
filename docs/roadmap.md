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

## Current verification boundary

The current publication release is deployed from `cd64e6b`; business runtime is unchanged from the
14 October browser-recovery correction. Its final isolated complete suite passed 289 tests with six
accounted skips, native exit0 and 363 unchanged runtime/configuration/build-prerequisite hashes.
Actual driver/browser loss recovered under one existing supervisor restart, followed by strict drain.
Exact owner/MCP/crawler/HTTP/CSP flows, static rollback, all-actor clean quiescence, signed native-image/
artifact/host-source parity, fresh two-database restore and scheduler/monitor recovery passed.
The installed-model templates, 50/70-context hours and independent encrypted recovery remain dated
13 October evidence. See the [current release record](releases/2026-10-15.md); implementation evidence
alone is not publication.

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

## Future scale and reliability

1M+ simultaneous users describes control-plane sessions across tenants; it does not mean a million
browser actors. The 99% initial operating objective and 99.9% multi-zone objective need explicit
SLIs, windows, error budgets, paging ownership, recovery and representative failure/load evidence.
They are future targets, not measured monthly availability or contractual commitments. See
[scale architecture](scaling/README.md), [capacity](scaling/capacity-model.md) and [SLOs](scaling/slo.md).

## Retained limits

The current hosting topology has one failure domain. Fixture endurance is not authenticated freight
capacity. Missing destination receipts remain inconclusive; UNKNOWN actions cannot be blindly retried.
The local browser agent is not an OS sandbox for hostile pages. Static inline-script hashes are
implemented, while inline styles and incomplete cross-origin isolation remain disclosed limitations.
The development-only dependency advisory remains separate from production audits/native image scans.
Off-host data restoration does not establish a second running site or measured recovery objective.

Use [testing](testing.md), [security controls](security/controls.md), [legal scope](legal/README.md),
[maintenance](maintenance.md) and [operations](operations/runbooks.md) when planning a promotion.
