# Scale and availability validation plan

This plan promotes the future architecture through **1k, 10k, 100k and 1M+ simultaneous authorized
console sessions**. Browser execution has a separate cell/account/destination budget. Combine the
[architecture](future-architecture.md), [capacity inputs](capacity-model.md) and
[99%/99.9% objectives](slo.md) with the workload and gates below.

## Declare the workload before a run

| Dimension | Record in the run specification |
|---|---|
| Population | Authorized tenants, sessions per tenant, idle/active ratio, geography and session lifetime |
| API | Read/write/approval/export mix, request sizes, pagination, think time and eligible-response definition |
| Live updates | Committed invalidation rate, fan-out distribution, bytes/event and refetch amplification |
| Data | History sizes, tenant skew, query/index plans, pool budgets, retention and read-replica lag allowance |
| Execution | Eligible approved workflows, account groups/cooldowns, receipts, queue arrival rate and destination limits |
| Topology | Exact source/images, replicas/zones, CPU/memory/socket/bandwidth caps and operational reserve |
| Reliability | SLI deadlines/window, allowed error budget, incident/stop conditions and recovery objectives |
| Cost/access | Approved infrastructure/provider scope, exact current budget and test authority |

Reuse the same declared mix across tiers so changes can be compared. Registered accounts, incoming
requests and open sockets are separate measurements. Count active operations and delivery alongside
connections. Use operator-controlled data and authorized actions with no private customer payloads.

## Promotion ladder

| Tier | Engineering focus | Exit evidence |
|---|---|---|
| Existing single host | Correctness, ready browsers, bounded admission, private network, signed release and recovery | Real HTTP/UI/MCP/crawler/receipts, graceful drain, parity and restore; dated workload/resource record |
| 1k connected | Gateway density, API pools, per-tenant limits and bounded refetch | Sustained mixed traffic, slow readers/revocation, cold-cache behavior and resource headroom |
| 10k connected | Subscription sharding, cache isolation, independent execution and connection budgets | Skewed tenants, reconnect burst, exhausted-pool protection and no authority crossover |
| 100k connected | Distributed fan-out, history partitioning, read routing and multi-zone capacity | Representative data, replica/cache failures, rolling release and zone evacuation under load |
| 1M+ connected | Validated gateway fleet, static delivery, multi-zone writer/read plane and isolated cells | At least one uninterrupted representative hour plus failure/recovery phases, with percentile/resource/cost evidence |
| Operating reliability | Independently collected user/API/update outcomes and owned incident response | Rolling 30-day SLI/error-budget report for the agreed 99% or later 99.9% objective |

Each concurrency tier includes at least an uninterrupted steady-state hour at its declared mix.
The month-long reliability observation is a separate gate. Record the generator's own CPU/network
limits so a saturated generator cannot be mistaken for service capacity.

## Run phases and stop conditions

1. **Prepare:** verify source/image identity, isolation, data, clocks, generator capacity and monitoring.
   Confirm private keys, backup integrity and the prior compatible release/static recovery path.
2. **Ramp:** increase authorized sessions gradually; measure TLS/authentication, connection admission,
   cache misses, hashing and pool use. Preserve quotas and bounded overload responses.
3. **Steady state:** sustain the declared population/mix for at least an hour. Record successful and
   eligible failed outcomes, p50/p95/p99, delivered updates, queue age and resource peaks.
4. **Skew and backpressure:** add a large active tenant, slow readers, expensive allowed queries,
   token/session expiry and cold caches. Verify isolation, revocation and small-tenant responsiveness.
5. **Failure:** lose a gateway/API replica, data replica/cache and one zone under the same traffic.
   Bound reconnect/resync; preserve database writer authority and enough already-running capacity.
6. **Recovery/release:** exercise rolling replacement, all-actor drain, cell move and archive/key/config
   restoration. Reconcile destination receipts without repeating uncertain accepted actions.
7. **Review:** compare with the declared budget, retain failed attempts and publish scrubbed evidence.
   Promote the tier only after every required gate passes and ownership/support scope is accepted.

Stop new admission for tenant isolation failure, changed/revoked action execution, duplicate action,
lost authoritative work, uncontrolled resource/backlog growth or unavailable recovery authority.
Preserve state and diagnose the first failure; increasing timeouts or removing cases requires a
new reviewed workload specification rather than relabelling the failed run.

## Resource and failure-mode budgets

Calculate database demand as the sum of every replica's finite pools plus migration/monitor/rollout
reserve. Check it against the database limit during replacement. Gateways release transactions
between authorization checks; sessions do not each hold a database connection. Keep approval,
revocation and action fences on the authoritative writer.

Budget sockets, queue memory and outbound bandwidth for delivery and reconnect/resync, including
protocol/TLS overhead. Observe oldest eligible work and bounded recovery throughput. Coalesce
invalidation/refetch traffic and protect private caches by tenant and role.

For three equally sized zones, loss of one multiplies remaining utilization by 1.5. The capacity
model's assumed 70% failure ceiling therefore requires normal utilization at or below about 46.7%,
before maintenance reserve. Validate each resource separately. Spare capacity must already exist
when a provisioning control plane is impaired; see
[AWS static stability](https://aws.amazon.com/builders-library/static-stability-using-availability-zones/).

## Evidence and operational acceptance

Keep run identity, timestamps, exact source/images/config, declared workload, topology, raw private
reports, assertion failures and sanitized summary together. Publish accepted and rejected outcomes,
hardware/caps, steady/failure durations, percentiles, error denominators, queue/resource peaks and
current cost assumptions. Identify which recovery steps were tested and which remain planned.

An SLO needs an owned indicator, measurement window, eligible-event definition and error-budget
response policy. Use independent probes and representative user outcomes, with sustained
observations across releases. Follow [Google's SLO methodology](https://sre.google/workbook/implementing-slos/)
and [operating ownership](../operations/service-ownership.md).

The existing server and local verification remain the current operating scope. Any later capacity
run that provisions resources or consumes paid provider APIs requires a current cost review and
the owner's explicit approval before activation.
