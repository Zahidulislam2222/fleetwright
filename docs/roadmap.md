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

The full backend suite passed 260 tests with six expected skips; the later local-agent UI correction
passed its own 25-case suite and actual three-template installed-model recording. Separate 50/70
browser-context fixture runs exceeded one hour with zero errors. Exact completion rc2 rehearsal
passed real owner/MCP/browser/crawler/CSP flows and final native image scans reported zero
HIGH/CRITICAL findings. Final integration and deployment status belong in the
[release record](releases/2026-10-13.md); implementation evidence alone is not publication.

## Expansion milestones

| Priority | Deliverable | Required promotion evidence |
|---|---|---|
| 1 | Repeatable operational baseline | Exact all-worker drain, immutable image/signature parity, live authorization/receipts, supervised backup/monitor, independent fresh encrypted restore |
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
