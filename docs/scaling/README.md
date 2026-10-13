# Scaling to 1M+ connected console users

The long-term product target is **at least 1,000,000 simultaneous connected console users**, across
many tenants, with separately budgeted automated browser capacity. This is a future architecture
and validation plan. The present deployment is a single server. Isolated verification sustained
50 and 70 Chromium contexts for separate uninterrupted hours, using a small owned fixture;
a separate 30-second control-plane test exercised 16 API and 32 SSE clients. These measurements
do not establish one-million-user capacity or representative destination throughput. See
[the measured evidence and limitations](verification-2026-10-13.md).

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
| Operational baseline | Verified archive/restore and monitoring tooling; independently operated availability checks and notifications | Full-host/key recovery, tested alert delivery and rolling 30-day SLI evidence; initial 99% operating objective |
| One region, multiple zones | Redundant API/gateways, database standby/PITR, isolated Redis cells, pooled connections, rolling releases | Zone-loss exercise under representative workload, no tenant crossover, 99.9% rolling objective |
| Many execution cells | Existing bounded cell-scoped tenant turns, account pacing/ownership and durable handover; expand deployment isolation | 50/70 fixture hours passed; next require representative approved workflows, tenant skew and cell-loss/rebalance under load |
| 1k to 100k connected users | Gateway sharding/fan-out, event coalescing, bounded refetch, reconnect jitter, read caches/replicas | Separate 1k, 10k and 100k sustained mixed-load tests, tenant skew and measured resource/cost curves |
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

Current approved-workflow runners enumerate bounded tenant pages within their assigned cell and
take bounded turns. Account group eligibility, DB-clock pacing and durable handover are enforced.
Extend these controls with weighted tenant admission, deployment-level failure isolation and
representative fairness measurements. Scale by oldest eligible queue age and resource pressure,
within approved infrastructure and destination limits. Never create a retry storm around `UNKNOWN`
work. Redis delivery is transport; PostgreSQL retains action and raw-detection authority.

Use zone-independent spare capacity so losing a zone does not depend on immediately provisioning
new capacity. Multi-region execution requires a single authoritative owner for an action and a
recovery protocol; geographic duplication alone does not establish safety.
This follows the spare-capacity principle in
[AWS static stability](https://docs.aws.amazon.com/whitepapers/latest/aws-fault-isolation-boundaries/static-stability.html).

Every milestone publishes concurrency, active tenants, request/event rates, payload sizes,
duration, hardware, resource limits, failure scenarios and percentile/error results. Cost estimates
require current provider quotes and owner approval before resources are provisioned.

## Architecture and decision records

The [future service design](future-architecture.md) defines the proposed routing, authorization,
data, fan-out and execution boundaries. [Capacity arithmetic](capacity-model.md) exposes the
assumptions behind resource and cost scenarios. [Availability and recovery](slo.md) defines the
promotion objectives; [adding a cell](adding-a-cell.md) covers the current migration procedure.
The [product roadmap](../roadmap.md) owns delivery sequencing.

No cloud resources are created by these documents or the offline Terraform tests. Multi-zone
spare capacity, managed data services, regional traffic and evidence storage require a separately
reviewed operational budget; free-tier limits are not a capacity guarantee.
