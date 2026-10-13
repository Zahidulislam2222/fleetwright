# fw_queue

Messaging on Redis.

| Module | Purpose |
|---|---|
| `keys.py` | Every Redis key in one place, with `{tenant}` hash tags so a cell can become a Redis Cluster |
| `streams.py` | Streams with consumer groups, `XAUTOCLAIM` reclaim, dead-letter after N deliveries |
| `outbox.py` | Relay that publishes outbox rows, after checking the tenant still belongs to this cell |
| `client.py` | Redis clients for the core and each cell |

Tests: `uv run pytest packages/fw_queue`.

Release operation and limits: [deployment](../../docs/operations/deployment.md) · [maintenance](../../docs/maintenance.md).

## Durability and recovery

PostgreSQL outbox/mailbox rows remain the durable authority. Publishing a detection to Redis does
not consume it: the filter/claim decision must commit first. Cell moves reset unconsumed delivery
under current tenant-directory authority, including unread and in-flight old-cell messages.

Monitor stream pending/dead-letter state and durable detection backlog separately from the
unpublished-outbox gauge. Before upgrading legacy Redis-only producers, use the all-cell drain
procedure; an older relay must not prune new mailbox topics. See [claim lifecycle](../../docs/architecture/claim-lifecycle.md),
[deployment compatibility](../../docs/operations/deployment.md#rollback-and-data-safety) and
[operational runbooks](../../docs/operations/runbooks.md).
