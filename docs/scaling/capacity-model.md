# Capacity model

This model separates measured inputs from assumptions. Replace every estimate with a benchmark
before offering a capacity commitment.

## Measured execution inputs

Historical developer-machine runs used 8, 16 and 32 Chromium contexts: roughly 70–103 MB unique
memory per context and 1.8 CPU cores at 32 contexts. Owned-board freight detection-to-confirmation
was approximately p50 365 ms / p95 540 ms. These figures depend on the workload and machine;
they are not measurements of heavier sites or of the new workflow runner at scale.

For planning, use 100 MB/context, reserve at least 30% of node RAM for the OS, browser overhead,
peaks and service processes, and validate CPU separately. An 8 GB worker-only node would then
budget about 56 contexts by memory; **50 contexts remains an unmeasured next test**, not a proven
density. Do not share that budget with a database without recalculating it.

## One-million-session assumptions

The following are deliberately adjustable scenario inputs, not configured production limits:

| Input | Planning assumption | Derived load |
|---|---|---|
| Connected sessions | 1,000,000 | Sustained concurrent sockets |
| Read rate | One request/session/30 s | About 33,333 reads/s before caching/coalescing |
| Mutation rate | 1% of sessions, one/minute | About 167 writes/s, with bursts tested separately |
| Delivered updates | One/session/10 s, 1 KiB payload | About 100,000 deliveries/s and 102.4 MB/s payload bandwidth |
| Gateway socket allocation | 64 KiB/session, estimate | About 61 GiB fleet memory before process/queue overhead |
| Reconnect event | 10% reconnect within 10 s | 10,000 handshakes/s plus resynchronization demand |
| Gateway density | 20,000 sockets/instance, unmeasured | 50 active instances before failover/headroom |

Protocol/TLS overhead, replication and client-triggered refetch add load. If every update triggers
five reads, the update scenario can create 500,000 reads/s: coalescing and bounded snapshots are
acceptance requirements. CDN serving removes much static asset load, not API traffic or user sockets.

For three equally loaded zones surviving one-zone loss at no more than 70% instance capacity,
normal aggregate utilization must be at most about 46.7%. The 50-instance idealized density would
therefore suggest at least 108 provisioned equivalents, rounded up with deployment/maintenance
headroom. This is arithmetic, not an infrastructure quote or a claim that 108 instances suffice.

## Extrapolated tier budgets

All rows below are planning arithmetic, not measured capacity or an offer. The session calculation
uses the preceding unmeasured 20,000 sockets per gateway and 46.7% normal utilization, rounded up,
with at least three instances to span three zones. It excludes API/database/WAF/CDN capacity.
Let **G** be a verified monthly gateway-instance quote and **B** the monthly price of the supporting
services at that tier; gateway/reference cost is `instances × G + B`. Enter current region-specific
quotes before a commercial estimate or any provisioning. No paid resources were created.

| Concurrent sessions | Gateway equivalents, extrapolated | Monthly formula, extrapolated |
|---|---|---|
| 1,000 | 3 | `3G + B₁ₖ` |
| 10,000 | 3 | `3G + B₁₀ₖ` |
| 100,000 | 11 | `11G + B₁₀₀ₖ` |
| 1,000,000 | 108 | `108G + B₁ₘ` |

The browser scenario assumes an independently benchmarked worker-only node can sustain 50
representative contexts. That assumption still needs the exact real-site workload even after a
simple owned-page density run. Let **W** be its current monthly node quote. Reserve and test
replacement/failure headroom separately; these rows describe active nodes only.

| Browser contexts | Active nodes at assumed 50/node | Monthly worker formula, extrapolated |
|---|---|---|
| 50 | 1 | `W` |
| 500 | 10 | `10W` |
| 5,000 | 100 | `100W` |
| 10,000 | 200 | `200W` |

The existing demonstration adds no newly provisioned node cost. Its resource caps and measured
simple-page test windows do not establish the quoted cloud-node assumptions above.

## Database and queue budgets

Budget connections as sum(replicas × pool size) plus migration/monitoring/operational reserve,
below the database limit. Connection pooling and backpressure must limit that sum during rollout
and autoscaling. Measure transaction latency, lock waits, WAL growth, replication lag and RLS query
plans at realistic tenant skew. Partition append-heavy events/audit by retention and time, preserving
tenant predicates and integrity rules. Read replicas cannot satisfy fresh approval authority.

For each queue, estimate arrivals × outage duration × record size, then include replay and retention
headroom. Bound queue growth and admission explicitly. Alerts need oldest-item age, not only count.
Current stream caps can trim history; recovery semantics must be verified rather than assuming
every detection can always be reconstructed.

## Validation ladder

Measure 1k, 10k, 100k and 1M sessions with the same disclosed workload. At every step test skewed
tenants, authorization revocation, slow consumers, cache cold start, replica loss, reconnect storm
and one-zone failure. Record p50/p95/p99, errors, resource peaks and cost per active tenant/session.
Measure browser density separately at 50/70 contexts for an hour and then across cells.
No paid environment is provisioned by this document.
