# ADR 0012 — Persist raw detections before cell delivery

Status: accepted; extends ADR 003 for the raw detection boundary.

The previous transactional outbox covered queued claims. A raw detection still existed only in
Redis before that decision. Moving a tenant could leave unread messages behind, and an already
read message could be acknowledged by the old cell without creating a claim. Fencing alone cannot
recover an intent that was never persisted.

Watchers now insert a tenant/job-unique detection row in PostgreSQL before transport delivery.
The relay publishes the maintained protocol to the tenant's current cell and retries unconsumed
rows after the configured idle interval. Dispatch loads the authoritative database payload and
locks current assignment, records the filter/claim decision and marks consumption in one transaction.
Repeated Redis delivery cannot create another claim. Pruning preserves unconsumed detection rows.

A tenant move holds directory authority while reassigning queued claims and resetting pending raw
detection delivery. A stale actor checks its configured cell before leasing. Previously authorized
in-flight actions may finish and retain their receipt/reconciliation semantics. No destination
action occurs in the watcher, relay or mailbox transaction.

The extra database boundary has a cost; measure detection-to-action latency and queue age with
representative backlogs. Durable handover tests cover unread streams, in-flight payload authority,
publish/commit crashes, retries, isolation and atomic move failure.

This changes backend compatibility. Migration cannot recover old Redis-only messages retroactively;
the release must account for legacy streams and dead letters before replacing the old dispatcher.
The older rc5 backend rejects the new topic and can prune pending data. Keep the compatible backend
for static-only rollback, or use a reviewed forward fix; full backend downgrade requires a separately
verified mailbox-preserving procedure. See [deployment](../operations/deployment.md).
