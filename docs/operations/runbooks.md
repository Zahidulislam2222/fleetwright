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

## Help assistant

Inside the application the assistant answers even when the AI cannot (the edge rate limit and a
Redis outage for signed-in sessions still return errors): the response has `mode: "search"` and a `reason`
(`disabled`, `rate_limited`, `busy`, `budget_exhausted`, `search_only`, `nothing_found`). Check today's
counters as the public workspace owner with `GET /v1/assistant` (`today`: questions, AI and search
answers, errors, `cost_micro`, votes) and the API logs ("assistant answered", "assistant model call
failed"). None of these steps affect claims, workers, workflows or crawls.

### Daily budget exhausted

Symptom: answers come back with `reason: "budget_exhausted"` until 00:00 UTC.

1. Compare `today.cost_micro` with `FW_ASSISTANT__DAILY_BUDGET_USD` and `today.questions` with the
   usual daily count. A sudden jump in questions from one place suggests scripted use.
2. If it is abuse, lower `FW_ASSISTANT__PUBLIC_PER_HOUR` (anonymous, per address range) or
   `FW_ASSISTANT__USER_PER_HOUR`; the edge rate limits also apply.
3. If it is real demand, raise the daily budget only after the owner's explicit cost approval. Once the
   planned dedicated provider key exists, keep the budget below its monthly cap and never raise that cap
   to work around the budget.
4. Documentation search keeps working meanwhile; no action is required for the console itself.

### Provider down, slow or rejecting calls

Symptom: `reason: "search_only"`, rising `today.errors`, "assistant model call failed" warnings
with a failure category (timeout, unreachable, HTTP status, not understood).

1. Check the provider's public status page and the provider key's remaining limit in the provider
   account. An HTTP 401, 402 or 403 from the provider typically points to a revoked key or exhausted credit.
2. Confirm the API can still reach the provider over the `egress` network and that `backend` stays internal.
3. Leave the assistant on: each question still gets documentation passages within the deadline. There is
   no automatic second provider; adding one needs its own review and cost approval.
4. A timed-out call keeps its budget reservation (the provider may still bill it), so heavy timeouts
   can exhaust the day's budget early. Record the outage window for the [assistant objective](../scaling/slo.md#help-assistant-objectives).

### Redis unavailable

Anonymous visitors still get documentation-search answers when the assistant's rate or budget store
fails; counters and feedback are best effort. Signed-in requests fail before reaching the assistant,
because sessions are stored in Redis, so restoring Redis is the priority. Follow the cell-outage steps above for Redis itself.

### Disable switch

Use it for a suspected prompt-injection or data-exposure problem, a provider incident or a cost concern.

1. Set `FW_ASSISTANT__ENABLED=false` in the private environment through the normal reviewed
   deployment change, then restart only the API service. Settings are read at start-up.
2. Verify: `GET /v1/assistant` returns `"enabled": false` and an ask returns `mode: "search"` with
   `reason: "disabled"`. The console and every other service keep running.
3. For a suspected key leak, also revoke the key at the provider and rotate it as in
   [Rotate a secret](#rotate-a-secret). For a suspected leak of tenant data, follow
   [incident response](#incident-response).
4. Re-enable only after the cause is fixed and, for prompt, model, tool or knowledge changes, after the
   held-out evaluation passes again (paid run, with cost approval).

## Monitor or archive warning

Check the collector's latest committed sample, process state, renewal/revocation and notification
sink. Inspect durable detection backlog separately from unpublished outbox gauges. For stale/bad
archives, retain the last good encrypted copy, correct collection/transfer failures and prove a new
isolated restore before declaring recovery coverage restored. See [monitoring](monitoring.md) and
[recovery](recovery.md).
