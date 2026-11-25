# fw_queue

Messaging on Redis.

| Module | Purpose |
|---|---|
| `keys.py` | Every Redis key in one place, with `{tenant}` hash tags so a cell can become a Redis Cluster; also the help assistant's daily spend, hourly question counters, daily counters and single-vote answer keys |
| `streams.py` | Streams with consumer groups, `XAUTOCLAIM` reclaim, dead-letter after N deliveries |
| `outbox.py` | Relay that publishes outbox rows, after checking the tenant still belongs to this cell |
| `client.py` | Redis clients for the core and each cell |

Tests: `uv run python -m pytest packages/fw_queue`.

Release operation and limits: [deployment](../../docs/operations/deployment.md) · [maintenance](../../docs/maintenance.md).

Current release: `20261125-assistant-rc5` ([25 November 2026 record](../../docs/releases/2026-11-25.md)).
That release added only the help assistant's keys; stream, outbox and delivery behaviour is
unchanged. The assistant's keys hold amounts and counters, never question text, and expire
on their own.

## Durability and recovery

PostgreSQL outbox/mailbox rows remain the durable authority. Publishing a detection to Redis does
not consume it: the filter/claim decision must commit first. Cell moves reset unconsumed delivery
under current tenant-directory authority, including unread and in-flight old-cell messages.

Monitor stream pending/dead-letter state and durable detection backlog separately from the
unpublished-outbox gauge. Before upgrading legacy Redis-only producers, use the all-cell drain
procedure; an older relay must not prune new mailbox topics. See [claim lifecycle](../../docs/architecture/claim-lifecycle.md),
[deployment compatibility](../../docs/operations/deployment.md#rollback-and-data-safety) and
[operational runbooks](../../docs/operations/runbooks.md).

## Transport pressure and release handoff

Observe pending count, oldest unconsumed age, delivery attempts, dead-letter growth and
PostgreSQL outbox/mailbox backlog together. Redis stream length alone does not identify whether
an action decision committed. Bound replay throughput so recovery cannot starve current traffic.

During a tenant/cell handoff, retain the authoritative directory and unconsumed detections until
the new consumer commits its decision. Test producer interruption and duplicate delivery at that
boundary. Current transport retention and future durable event cursors have different contracts;
see [scale validation](../../docs/scaling/validation-plan.md) and
[service ownership](../../docs/operations/service-ownership.md).
