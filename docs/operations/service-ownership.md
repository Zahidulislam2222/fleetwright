# Service ownership and operational acceptance

Assign a deployment operator, release approver and incident/recovery owner before enabling
customer work. One person may hold several roles; each responsibility still needs an explicit
handoff and private access-recovery record. This matrix describes implemented process boundaries.

| Component | Responsibility and dependencies | Readiness and recovery evidence |
|---|---|---|
| Static console/edge | Immutable assets, same-origin routing, security headers and request limits | Route hydration/CSP, responsive navigation, public denial, served-file/image hashes |
| Coordinator API | Authentication, roles, approvals, grants, audit and bounded data views; PostgreSQL/Redis | Health plus real owner password/TOTP, CSRF, role/revocation and export flows |
| Live-update gateway | Authorized tenant subscriptions and bounded invalidation delivery | Event delivery, idle revocation, slow-consumer and reconnect behavior |
| Control | Dispatch, durable mailbox/outbox decisions, sweeps and receipt reconciliation | Eligible queue/backlog age, database ownership and retained UNKNOWN outcomes |
| Freight worker | Warm isolated browser slots, detection/action and account leases | Actual browser readiness and booking; child-loss recovery; stopped rows/zero holds on drain |
| Approved-workflow worker | Exact approved action, fenced job/account ownership and receipt recovery | Both contract flows, approval denial cases, bounded stop and terminal/uncertain history |
| Crawler | Durable frontier, pinned same-origin fetches, quality guards and exports | QUEUED/RUNNING/COMPLETE, exact records, lease fencing, cancellation and physical request cleanup |
| Owned destinations | Account identity, accepted actions and independent receipt records | Exact account/payload receipt, adversarial acknowledgement/session/layout checks |
| PostgreSQL | Tenant isolation and authoritative transitions, identities and encrypted records | Restricted roles/RLS, connection budget, migrations and fresh database restoration |
| Redis cells/core | Transport, sessions and invalidation fan-out | Connectivity, backlog/pending/dead letters, bounded memory and durable replay |
| Backup scheduler | Private verified archives, retention and restoration tooling | Fresh manifest/hash/permissions, current source/config, supervised restart/new archive |
| Monitor | Renewable observation authority, bounded probes and durable local alert sink | Fresh healthy checks, renewal/revocation, supervised restart and incident history |
| Local agent/MCP client | Device-owned local state or private scoped client authority | Exact proposal/approval/receipt, stop/revocation, local inventory and retained state |

## Release handoff

1. Record accepted scope, current source, live pointer and protected-input hashes. Reconcile drift
   locally before changing production. Keep raw evidence and access details private.
2. Commit reviewed local inputs and build a new immutable release. Verify source/configuration,
   behavior, types, lint, builds, native image findings/SBOMs and the independent trust anchor.
3. Rehearse real operator, MCP, browser/crawler and authorization flows. Bind each observation to
   the exact archive/image. Check all required attestations before signing the final inventory.
4. Drain freight, workflow and crawler actors while their data/authority dependencies are reachable.
   Require successful non-OOM exits, released account holds and no active jobs. Keep control running
   until every legacy stream is accounted for, then stop it and validate a quiescent archive.
5. Apply reviewed migration/seed and start the candidate. Verify public TLS/HTTP, live receipts,
   browser readiness, exports, role boundaries, exact image identities and full manifest parity.
6. Verify backup/monitor process directories, protected inputs, fresh archives/probes and recovery.
   Publish the owner revision only after acceptance; verify actual commit-specific CI and probes.

Record temporary static overrides separately from the compatible backend release. Preserve data
volumes, pending detections and uncertain accepted work. A restart or static rollback does not
reverse an action already accepted by a destination.

## Routine checks and escalation

Check useful outcomes alongside process liveness. A Python process or HTTP200 can remain alive
while browser work is unavailable. Correlate ready slots, new destination receipts, oldest eligible
job/detection age, account holds, login/session failures and recovery attempts. Use the declared
traffic window so an idle destination is distinguishable from stalled execution.

For an incident, record first observation, affected tenant/function, last accepted release,
authority/data integrity, immediate containment and the next safe recovery step. Preserve the
original failed gate. Assign escalation and user communication to the deployment operator; local
JSON/journal alerts require an agreed recipient and delivery channel before a support commitment.

Access must cover current source/artifacts, protected settings, independent encryption/signing
keys, backup media, DNS/hosting and the approved restoration procedure. Keep those values in
private recovery records. Rehearse recovery under the same tenant/approval/receipt constraints.

See [deployment](deployment.md), [runbooks](runbooks.md), [monitoring](monitoring.md),
[recovery](recovery.md), [data lifecycle](../security/data-lifecycle.md) and
[service objectives](../scaling/slo.md).
