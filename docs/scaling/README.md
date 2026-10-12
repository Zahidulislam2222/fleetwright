# Scaling to 1M+ simultaneous users

The long-term product target is **at least 1,000,000 simultaneous connected console users**, across
many tenants, with separately budgeted automated browser capacity. This is a future architecture
and validation plan. The present deployment is a single server and browser capacity has been
measured only through 32 contexts on a developer machine.

## Workload contract

“Simultaneous” means authenticated/authorized sessions actively connected during a sustained test,
not registered accounts or a one-minute arrival count. The target test includes API reads/writes,
event fan-out, reconnects, tenant skew, slow clients, revoked users and an availability-zone failure.
One million browser contexts is a different workload; 100 MB per context would alone require
about 100 TB of memory. It is not the one-million-user control-plane target.

| Plane | Target workload | Main constraints |
|---|---|---|
| Static console | 1M+ simultaneous sessions | CDN cache misses, assets and regional delivery |
| API/authorization | Session, list, approval and investigation requests | Pool budget, query plans, per-tenant fairness and auth storage |
| Update gateway | 1M+ live connections | File descriptors, socket memory, event fan-out, bandwidth and reconnect storms |
| Execution | Independently scaled browser cells | Context memory/CPU, account exclusivity and destination permission/rate limits |
| Evidence | Bounded investigation and export | Retention, object storage, access control and retrieval cost |

## Delivery stages and exit gates

| Stage | Required implementation | Proof before promotion |
|---|---|---|
| Current single host | Hardened Compose, private data network, fenced jobs, immutable releases, backup tooling | Functional/adverse-condition suites and release rehearsal; no availability claim |
| Operational baseline | Scheduled verified archives, external availability checks, metrics collector, notifications, off-host encrypted copy | Restore from independent storage, alert delivery and rolling 30-day SLI evidence; minimum 99% operating objective |
| One region, multiple zones | Redundant API/gateways, database standby/PITR, isolated Redis cells, pooled connections, rolling releases | Zone-loss exercise under representative workload, no tenant crossover, 99.9% rolling objective |
| Many execution cells | Cell-scoped workflow scheduling, per-tenant queues/quotas, admission control, account ownership and safe moves | 50 then 70-context hour-long runs; growing cell count without coordination regressions |
| 100k connected users | Gateway sharding/fan-out, event coalescing, bounded refetch, reconnect jitter, read caches/replicas | Sustained mixed load and tenant-skew test with measured cost/resource curves |
| 1M+ connected users | Multi-zone gateway fleet, CDN, partitioned history, pooled database/read replicas, independent cells | At least 1M concurrent sessions sustained for an hour, representative actions/events, node/zone failures and measured SLOs |
| Regional recovery | Tested standby region, explicit writer authority and data residency | Recovery from regional loss with measured RPO/RTO; no automatic split-brain writes |

## Required engineering

Keep authoritative transitions in PostgreSQL. Pool application connections independently from
open HTTP connections; a million sessions must not imply a million database connections. Start
with measured query/index improvements and partition large histories before adopting sharding.
Sharding needs a tenant directory, migration protocol and explicit cross-shard limits.

Shard gateway subscriptions by tenant/channel, batch or coalesce invalidations and bound client
queues. Disconnect slow consumers with a recoverable cursor; provide resynchronization when the
cursor has expired. Spread reconnects with randomized backoff and throttle snapshot requests.
The current gateway and refetch behavior need load evidence before this design is promoted.

Assign approved-workflow runners to cells instead of enumerating the entire tenant population.
Add per-tenant admission limits, fair dispatch, destination/account budgets, queue age metrics and
safe drain/rebalance. Scale by queue age and resource pressure, within approved infrastructure
and destination limits. Never create a retry storm around `UNKNOWN` work.

Use zone-independent spare capacity so losing a zone does not depend on immediately provisioning
new capacity. Multi-region execution requires a single authoritative owner for an action and a
recovery protocol; geographic duplication alone does not establish safety.
See [AWS static stability](https://aws.amazon.com/builders-library/static-stability-using-availability-zones/).

Every milestone publishes concurrency, active tenants, request/event rates, payload sizes,
duration, hardware, resource limits, failure scenarios and percentile/error results. Cost estimates
require current provider quotes and owner approval before resources are provisioned.

See [capacity arithmetic](capacity-model.md), [availability and recovery](slo.md) and [roadmap](../roadmap.md).
