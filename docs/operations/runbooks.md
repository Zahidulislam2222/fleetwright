# Operational runbooks

Use [deployment](deployment.md) for immutable release, drift/parity and rollback steps. Keep an
incident owner, timestamps, release/commit and private evidence for every operational change.

## Uncertain workflow outcome

Inspect the job timeline, fence, account and receipt evidence. An expired `ACTING` lease becomes
`UNKNOWN`; allow read-only reconciliation to check the destination. Do not click again, change the
action identity or create another proposal to bypass uncertainty. If evidence remains inconclusive,
retain unknown state and arrange authorized operator review. Cancellation records intent; it does
not claim the external action was undone. See [workflow recovery](reliable-browser.md#human-review-and-outcome).

## Revoke access

An owner revokes the workflow grant or approval using its authenticated CSRF-protected endpoint.
Revoke compromised console sessions/account access as appropriate. Verify the next MCP call and
pre-action authorization are denied; verify idle update streams close within their configured
check interval. Already accepted actions and delivered evidence cannot be recalled.

## Backup and restore

Check backup service state and age, then verify archive hashes and manifests. A failed new archive
must not remove the last good one. `python -m fw_coordinator.backup drill <backup-folder>` restores
into uniquely named fresh databases, never overwriting an existing database. Protect these copies
and record their disposition. For a new cluster, provision roles from the repository with current
private passwords; archives do not carry cluster roles.

For disaster recovery, use an independently protected copy, restore config and vault keys, validate
RLS/approvals/events/audit/outbox, then recover services and reconcile interrupted actions. Measure
elapsed time and data loss against [recovery objectives](../scaling/slo.md). Local archive success
alone does not prove host-loss recovery. Do not switch production DSNs without an approved recovery
plan and integrity evidence.

## Rotate a secret

Generate privately; update the approved secret store/environment and private recovery record.
Restart affected services, verify the new value, revoke the old value and invalidate affected
sessions/grants. For a vault master key, use a new key ID, reseal records with verified tooling and
retain old decryption access until all records and retained backups are accounted for. Automated
KMS rotation is future work; do not discard a key needed to restore encrypted data.

## Cell outage

Pause affected dispatch, inspect PostgreSQL claims/outbox and Redis health, then restore the cell
or perform the supported tenant handover. New raw detections are persisted before delivery;
current-cell routing and the decision/consume transaction preserve unread and in-flight detections
across a move. Queued claims are re-dispatched atomically. Previously admitted actions may finish;
reconcile their destination outcomes. The workflow scheduler also checks current cell authority
before admission. Legacy pre-upgrade Redis-only backlog needs the explicit upgrade drain described
in [deployment](deployment.md#rollback-and-data-safety). Verify isolation and queue recovery before
resuming. The old rc5 backend is incompatible with new mailbox topics; use the documented
static-only rollback or a reviewed forward fix.

## Incident response

1. Declare impact, affected tenants/workflows and one accountable incident owner.
2. Contain: pause execution, revoke compromised authority and protect evidence/backups.
3. Investigate bounded job/claim history, audit intent/outcome and private destination artifacts.
4. Recover from verified source/config; reconcile uncertain actions before reopening execution.
5. Notify affected parties and meet applicable security/privacy reporting duties with legal review.
6. Record root cause, escaped gate, corrective action and evidence; review material incidents.

## Vulnerability handling

Receive reports privately through [SECURITY.md](../../SECURITY.md), reproduce, assess exploitability
and choose containment/fix priorities. Check CRA applicability and official reporting guidance for
the specific actively exploited vulnerability or severe incident; their final-report clocks differ.
Coordinate release/disclosure with the reporter. Keep private data out of public advisories.

## Planned restart or upgrade

1. Freeze/review the replacement source and exact release; validate schema/queue compatibility.
2. Gracefully stop every browser/execution worker: freight, approved workflows and crawler when
   present. Verify successful exit, no OOM kill, released holds and retained uncertain outcomes.
3. Keep old control available until every configured legacy detection stream has zero unread lag,
   zero pending entries and no unexplained dead-letter work. Preserve evidence; abort if not drained.
4. Stop control, take and validate a fresh pre-migration archive, then apply reviewed migrations.
5. Verify trusted artifact/image identities, recreate dependencies/services in the reviewed order,
   and check roles, receipts, queues, HTTP/TLS, service supervision and complete hash parity.

A container's default stop timeout is not the application drain policy. Render/check grace for
each worker service separately. Never force-kill actors merely to complete a deploy faster.

## Crawler or local-agent failure

For a crawler alert, inspect the cycle's terminal state, extraction errors and quality counts.
Review the authorized definition and destination before retrying; do not consume a partial cycle
as a complete removal snapshot. Preserve the last good export and validate retention.

For a local-agent interruption, preserve SQLite and profile data, inspect UNKNOWN tasks and use
read-only receipt reconciliation. Do not approve a new identity to bypass uncertainty. If edits
were made, verify the fresh proposal and final receipt contain the exact reviewed title/body.
See [crawler](crawler.md) and [local agent](local-agent.md).

## Monitor or archive warning

Check the collector's latest committed sample, process state, renewal/revocation and notification
sink. Inspect durable detection backlog separately from unpublished outbox gauges. For stale/bad
archives, retain the last good encrypted copy, correct collection/transfer failures and prove a new
isolated restore before declaring recovery coverage restored. See [monitoring](monitoring.md) and
[recovery](recovery.md).
