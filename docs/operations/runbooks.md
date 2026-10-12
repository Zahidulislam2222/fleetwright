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
or perform the supported tenant handover. Queued claims have handover coverage; in-flight detections
can be lost. Acknowledge that boundary and reconcile destination outcomes. Verify isolation and
queue recovery before resuming. General workflow cell assignment remains planned.

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
