# Scaling Fleetwright

This page explains how Fleetwright grows from one developer PC to a multi-tenant service with
**1M+ concurrent connected sessions** and **99.9% monthly availability**, and what has to be built
at each step.

> **Read this first.** Labels used on every number in the scaling docs:
> - **Measured**: produced by a test in this repository on real hardware.
> - **Estimate**: engineering judgement, not measured here.
> - **Target**: a design goal the code is built to support, not proven capacity.
>
> Nothing in this folder claims that Fleetwright serves 1M users today. It does not. The current
> public site is a single server with no redundancy.

## Two different "scales"

| Plane | What grows | Target | Main limit |
|---|---|---|---|
| **Control plane**: API, console, live-update gateway | Operators and viewers connected at the same time, across many tenants | **1M concurrent connected sessions** (target) | Open connections and fan-out of events |
| **Worker plane**: browsers that watch and act | Browser contexts | **50 → 10,000+ contexts** by adding cells (target) | RAM: ≈ 100 MB per context (measured) |

A million automated browsers is a different problem: at ≈ 100 MB each that is about 100 TB of RAM.
The design does not aim for that, and no document here suggests it does.

## Seams that are already in the code

These cost little to build early and are expensive to add later. Each one exists and is tested now.

| Seam | Where | Why it matters at scale |
|---|---|---|
| `tenant_id` first in every key and index, row-level security | Migrations, `test_rls.py` | Multi-tenant SaaS without a rewrite; later sharding or partitioning by tenant |
| Stateless services; all state in Postgres or Redis | Control process, workers | Horizontal scaling; any instance can be killed |
| Cells with tenant-to-cell routing | `tenant_cells`, `fw_coordinator.control.move_tenant` | Add capacity and isolate failures by adding cells |
| Redis keys with `{tenant}` hash tags | `fw_queue.keys` | A cell can become a Redis Cluster without renaming keys |
| Outbox, idempotent consumers, fencing tokens | `fw_core.claims`, `fw_queue.outbox` | Retries and redelivery are safe in a distributed system |
| Bounded everything: pagination, statement timeouts, stream length caps, HTTP body limits | Settings, queries | No unbounded queries or memory growth under load |
| One typed configuration boundary | `fw_core.settings` | Local → single server → AWS by configuration only |

## The path, stage by stage

| Stage | Shape | Capacity | Availability | Trigger to move on |
|---|---|---|---|---|
| **0. Today** | One PC or one shared server, Docker Compose | Measured up to 32 contexts on a PC | No target; single point of failure | First paying client |
| **1. Single production server** | Dedicated server, Compose, backups, monitoring | ≈ 75 contexts per 8 GB node (estimate from measured RAM) | ≈ 99% possible with good operations (estimate) | More than one node of workers, or an availability commitment |
| **2. Cloud, one region, multi-AZ** | Managed Postgres (Multi-AZ), managed Redis per cell, container services with autoscaling, load balancer + WAF, object storage | Hundreds of contexts; thousands of console sessions | **99.9% target** | More than ~500 contexts, or tenants needing isolation |
| **3. Many cells** | N cells per region, tenants spread across cells, gateway fleet | 10,000+ contexts (target) | 99.9% per cell; a failed cell affects only its tenants | Over ~100k live console connections, or global customers |
| **4. 1M connected sessions** | Gateway fleet behind a load balancer, fan-out by tenant channel, CDN for the console, read replicas and connection pooling for Postgres, partitioning of the largest tables | 1M concurrent sessions (target) | 99.9% (target); 99.95% needs multi-region | Customers in several continents or contractual 99.95%+ |

### What is deliberately not built yet

| Not built | Why not now | What would trigger it |
|---|---|---|
| Kubernetes | Compose and managed container services cover stages 0–3 | Many cells per region with custom scheduling needs |
| Kafka or NATS | Redis Streams per cell are enough while each cell is bounded | Cross-cell event replay or retention beyond hours |
| Multi-region active-active | Doubles cost and complexity | A 99.95%+ commitment or data-residency requirements |
| Sharded Postgres | One primary with replicas covers the claim rate of many cells (estimate) | Claim writes approaching the primary's limit in a load test |

## Scale check (applied to every change)

1. No state that must survive a restart lives only in process memory.
2. Every query is bounded and backed by an index that starts with `tenant_id`.
3. Every record, message and log line carries `tenant_id`.
4. Every external call has a timeout and a retry policy.
5. Every setting goes through `fw_core.settings`.
6. Every new component has a documented scale-out path here.

## More

- [Capacity model](capacity-model.md): measured inputs and the arithmetic behind each tier.
- [SLOs and error budgets](slo.md): what 99% and 99.9% mean and how they would be measured.
- [ADR-005 Cells](../adr/0005-cells.md) · [ADR-009 Scale targets](../adr/0009-scale-targets.md)
