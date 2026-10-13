# Roadmap

Milestones advance on evidence rather than promised dates. Each requires written criteria,
automated gates, real-flow verification and independent review.

## Implemented and locally verified

The freight engine includes fenced claims, warm sessions, filters/schedules, cells, transactional
outbox, reconciliation and latency traces. The console includes password/TOTP, roles, CSRF,
masked public access, capped shared controls, audit and live updates.

Reliable Browser Operations adds versioned general workflow contracts, durable fenced jobs,
exact-action approval, scoped/revocable MCP, bounded investigation/export, two owned browser
workflows, authenticated health/metrics and verified backup/restore tools. The combined suite
passed all 148 cases across the final regression and isolated benchmark runs on 2026-10-13; actual Codex ran both workflows. Claude's actual client run is
deferred while its subscription is inactive. Publication/deployment status belongs in the
[changelog](../CHANGELOG.md); local test results alone are not release evidence.

## Prioritized milestones

The completion implementation adds a durable catalogue crawler, the standalone SQLite/Ollama
browser app, renewable authenticated monitoring, independent encrypted off-host recovery,
action-boundary account pacing, bounded cell-scoped workflow turns, signed-artifact tooling and
a configurable AWS reference tested without cloud provisioning. See the [crawler](operations/crawler.md),
[local agent](operations/local-agent.md), [monitoring](operations/monitoring.md),
[recovery](operations/recovery.md) and [assurance evidence](scaling/verification-2026-10-13.md).
These source additions require their own exact release evidence; the previously deployed rc5
release remains the deployment reference until the completion release is verified.

The [13 October release](releases/2026-10-13.md) verifies the first milestone below; preserve
these release gates for every replacement. The next expansion priority is operational baseline.

| Priority | Deliverable | Acceptance / exit evidence |
|---|---|---|
| 1 | Reliable release operations | Exact committed artifact, migration/rehearsal, healthy workflow worker, scheduled verified archives, live HTTP/browser check, local/live hash parity |
| 2 | Install and verify operational baseline | Collector/renewal/supervisor and independent scheduled-probe checks on the exact completion release; local encrypted off-host restore already exercised |
| 3 | Workflow expansion | New authorized destination contracts with account/precondition/receipt rules, ambiguous-outcome policy and adversarial browser tests; no arbitrary selector tool |
| 4 | Client assurance | Repeat actual Codex acceptance on releases; actual Claude run when subscription is available; no paid fallback without explicit approval |
| 5 | Security assurance | OWASP ASVS assessment with evidence, dynamic tests, CSP hardening, artifact access/retention tests, release SBOM, container/dependency scans and signed provenance |
| 6 | Fleet scale | 50 then 70-context hour-long runs, measured CPU/RAM/latency, account/destination pacing, tenant fairness and safe drain/move |
| 7 | Multi-zone control plane | Redundant API/gateways, database standby/PITR, pooled connections, static spare capacity, zone-failure exercise and measured 99.9% objective |
| 8 | 100k then 1M+ simultaneous users | Disclosed sustained mixed workload, bounded fan-out/refetch, reconnect/slow-client tests, resource/cost curves and failure exercises |
| 9 | Additional crawler destinations | Maintained authorized origin/extraction contracts, network egress review, per-domain budgets and adversarial evidence before onboarding |
| 10 | Additional local-agent destinations | Strict form/receipt contracts beyond the three verified owned templates; preserve exact human approval and transport restrictions |

## Current limitations and tracked work

- The deployment is one host; no measured monthly uptime or contracted 1M-user capacity.
- Workflow runners now use bounded cell-scoped round-robin turns; large-tenant skew still needs representative deployment measurements.
- Freight and workflow actions enforce account-group eligibility and database-clock cooldown at admission/action/completion; destination-side remote timing remains a receipt/reconciliation boundary.
- Detections in flight during a tenant move may be dropped; queued claims have handover coverage.
- Replanning freight slots restarts the worker's slots; targeted drain remains future work.
- Bounded local API/SSE reconnect and slow-client tests exist; production-scale refetch/skew still requires measurements. Console updates coalesce through maintained configuration.
- Source health/metrics collector, renewal and independent public-probe workflow need final installation/publication evidence.
- Independent encrypted archives were restored into fresh local databases with table row parity; a full-host/key/application recovery drill remains separate.
- New static release generation binds inline scripts to build hashes. Runtime inline styles remain an explicit exception; real release navigation must pass before publishing the stronger policy.
- Full npm audit retains an unpatched development-only `braces` advisory; production dependencies audit clean.
- A destination with inconclusive receipts remains `UNKNOWN` and needs operator review.

See [scaling](scaling/README.md), [SLOs](scaling/slo.md), [security](security/controls.md),
[maintenance](maintenance.md) and [workflow operations](operations/reliable-browser.md).
