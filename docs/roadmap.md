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
passed 132 tests on 2026-10-13; actual Codex ran both workflows. Claude's actual client run is
deferred while its subscription is inactive. Publication/deployment status belongs in the
[changelog](../CHANGELOG.md); local test results alone are not release evidence.

## Prioritized milestones

| Priority | Deliverable | Acceptance / exit evidence |
|---|---|---|
| 1 | Reliable release operations | Exact committed artifact, migration/rehearsal, healthy workflow worker, scheduled verified archives, live HTTP/browser check, local/live hash parity |
| 2 | Operational baseline | External uptime probes, authenticated metrics collector, tested notifications, off-host encrypted backups, recovery from independent copy, retention/key recovery runbooks |
| 3 | Workflow expansion | New authorized destination contracts with account/precondition/receipt rules, ambiguous-outcome policy and adversarial browser tests; no arbitrary selector tool |
| 4 | Client assurance | Repeat actual Codex acceptance on releases; actual Claude run when subscription is available; no paid fallback without explicit approval |
| 5 | Security assurance | OWASP ASVS assessment with evidence, dynamic tests, CSP hardening, artifact access/retention tests, release SBOM, container/dependency scans and signed provenance |
| 6 | Fleet scale | 50 then 70-context hour-long runs, measured CPU/RAM/latency, account/destination pacing, tenant fairness and safe drain/move |
| 7 | Multi-zone control plane | Redundant API/gateways, database standby/PITR, pooled connections, static spare capacity, zone-failure exercise and measured 99.9% objective |
| 8 | 100k then 1M+ simultaneous users | Disclosed sustained mixed workload, bounded fan-out/refetch, reconnect/slow-client tests, resource/cost curves and failure exercises |
| 9 | Crawler | Authorized domains, robots/TDM policy, SSRF/egress guard, per-domain budgets, extraction allowlist, dead-letter and quality alerts |
| 10 | Standalone browser agent | Real local application, configured model/provider, injection defenses and exact-action approvals; replace local interaction data only after behavioral proof |

## Current limitations and tracked work

- The deployment is one host; no measured monthly uptime or contracted 1M-user capacity.
- General workflow runners enumerate tenants; cell assignment and large-tenant fairness need scale work.
- Legacy freight dispatch does not yet enforce all configured account-group/rate pacing rules.
- Detections in flight during a tenant move may be dropped; queued claims have handover coverage.
- Replanning freight slots restarts the worker's slots; targeted drain remains future work.
- SSE-driven refetch load and slow-client behavior need representative scale testing.
- Source health/metrics need an installed collector, external probes and notifications.
- Archives need an independent encrypted copy and full-host/key recovery drill before disaster objectives are accepted.
- CSP retains inline scripts/styles for the current static application; stronger policy is planned.
- Full npm audit retains an unpatched development-only `braces` advisory; production dependencies audit clean.
- A destination with inconclusive receipts remains `UNKNOWN` and needs operator review.

See [scaling](scaling/README.md), [SLOs](scaling/slo.md), [security](security/controls.md),
[maintenance](maintenance.md) and [workflow operations](operations/reliable-browser.md).
