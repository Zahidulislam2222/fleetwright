# Capacity model

This model separates measured inputs from assumptions. Replace every estimate with a benchmark
before offering a capacity commitment.

## Measured execution inputs

Historical developer-machine runs used 8, 16 and 32 Chromium contexts: roughly 70–103 MB unique
memory per context and 1.8 CPU cores at 32 contexts. Owned-board freight detection-to-confirmation
was approximately p50 365 ms / p95 540 ms. These figures depend on the workload and machine;
they are not measurements of heavier sites or of the new workflow runner at scale.

Separate isolated server tests subsequently sustained 50 contexts for 3,601.986 seconds and
70 for 3,602.632 seconds with zero fixture-action errors. They used 6/8 GiB memory caps and
2 CPU quotas on an 8-core host with 25,199,177,728 bytes of RAM. Maximum sampled cgroup charges
were 1,535,565,824 and 2,082,316,288 bytes, respectively. These are aggregate simple-fixture
process charges, not interchangeable with historical per-context unique-memory estimates.
See [the complete measurements](verification-2026-10-13.md), including retained failed attempts.

For a planning worker-node scenario, assume 100 MB/context and reserve 30% of RAM for the
OS, browser overhead, peaks and service processes. An 8 GB worker-only node then budgets about
56 contexts by memory. This arithmetic still needs representative page, login, trace, CPU and
network measurements before selecting a real node density. A shared database reduces that budget.

## One-million-session assumptions

The following are deliberately adjustable scenario inputs, not configured production limits:

| Input | Planning assumption | Derived load |
|---|---|---|
| Connected sessions | 1,000,000 | Sustained concurrent sockets |
| Read rate | One request/session/30 s | About 33,333 reads/s before caching/coalescing |
| Mutation rate | 1% of sessions, one/minute | About 167 writes/s; approvals and audit amplify transactions |
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

The existing verification used authorized infrastructure without provisioning another node. Its resource caps and measured
simple-page test windows do not establish the quoted cloud-node assumptions above.

## Help assistant token and cost model

Labels: **measured** comes from the [25 November release record](../releases/2026-11-25.md);
**configured** comes from `AssistantSettings` and `.env.example`; everything else is arithmetic.

| Input | Value | Label |
|---|---|---|
| Model and price | `anthropic/claude-haiku-5.5` via OpenRouter, $0.10 input / $0.50 output per million tokens (provider list, 25 Nov 2026) | Configured; prices change, recheck |
| Cost per question | About $0.0006 average ($0.0091 for 16 questions), at most $0.0010 | Measured, 16-case held-out evaluation only |
| Latency | p95 4.98 s over the same 16 questions | Measured, evaluation only, not a production SLI |
| Output per call | ≤ 600 tokens (≤ $0.0003) | Configured |
| Input per call | ≤ 24,000 prompt characters plus tool declarations, reserved at 3 characters per token: about 8,000 tokens (≈ $0.0008) | Configured, conservative estimate |
| Calls per question | ≤ 3 model calls, ≤ 4 tool calls per call | Configured |
| Worst-case reservation | ≈ $0.0011 per call, ≈ $0.0033 per question, settled down to the reported cost | Arithmetic |
| Daily budget | $0.16 on the current deployment (about $5/month); a provider-side capped key is planned | Configured (release record); `.env.example` default is $0.50 |

At the measured cost, today's $0.16 budget covers about 160–270 AI answers a day; after that, answers
fall back to documentation search until the next UTC day. Reservations briefly hold worst-case cost
while calls are in flight, so a burst can reach the budget earlier than the settled total suggests.

### Scenarios toward 1M+ users (arithmetic, not measured)

Assumptions: questions spread over the day with a 3× peak, about 5 s per question in flight (the
measured evaluation p95, used as a conservative mean) and the measured $0.0006–0.0010 per question.
The 200,000 row applies the baseline ratio (10% of daily users ask 2 questions) to 1M daily users.

| Questions/day | Peak questions/s | In flight at peak | Provider calls/s at peak (≤ 3 each) | Cost/day at measured rate | Worst-case reservation/day |
|---|---|---|---|---|---|
| 10,000 | 0.35 | ~2 | ≤ 1.0 | $6–10 | ~$33 |
| 100,000 | 3.5 | ~18 | ≤ 10 | $60–100 | ~$330 |
| 200,000 (1M daily users) | 6.9 | ~35 | ≤ 21 | $120–200 | ~$660 |
| 1,000,000 | 35 | ~174 | ≤ 104 | $600–1,000 | ~$3,300 |

Monthly cost is roughly 30× the daily figure (for example $3,600–6,000 for the 200,000 row). At the
current per-process concurrency of 4, the 200,000 row needs about 9 processes' worth of slots and the
1,000,000 row about 44, which is why the [future design](future-architecture.md#help-assistant-at-scale)
moves model calls to a bounded worker pool with budget shards, per-tenant quotas and cached
documentation-only answers. Provider request and token rate limits must be confirmed for the chosen
key and tier before any of these rows; cache hit rates are unknown until measured. Every row needs a
current price check and the owner's cost approval; none has been run.

## Database and queue budgets

Budget connections as sum(replicas × pool size) plus migration/monitoring/operational reserve,
below the database limit. Connection pooling and backpressure must limit that sum during rollout
and autoscaling. Measure transaction latency, lock waits, WAL growth, replication lag and RLS query
plans at realistic tenant skew. Partition append-heavy events/audit by retention and time, preserving
tenant predicates and integrity rules. Read replicas cannot satisfy fresh approval authority.

For each queue, estimate arrivals × outage duration × record size, then include replay and retention
headroom. Bound queue growth and admission explicitly. Alerts need oldest-item age, not only count.
Current stream caps can trim transport history. Raw freight detections are persisted before
delivery and retried until consumed, and unconsumed rows are excluded from retention pruning.
Legacy Redis-only backlog needs the documented upgrade drain. Gateway invalidations remain
ephemeral hints: lost hints require authoritative API refresh, not assumed event-history recovery.

## Measured control-plane baseline

The current network test used 16 API clients and 32 SSE clients, including two slow readers,
for 30.297 seconds: 1,199 API requests, 192 SSE connections, 160 reconnects, 12,420 data frames
and zero HTTP/network errors. API p95 was 762.90 ms and event-delivery p95 161.47 ms. Cold client
and database setup were measured separately; direct Hub overflow separately tested queue eviction.
This mixed local test overlapped other work and has no million-session extrapolation factor.

## Validation ladder

Measure 1k, 10k, 100k and 1M sessions with the same disclosed workload. At every step test skewed
tenants, authorization revocation, slow consumers, cache cold start, replica loss, reconnect storm
and one-zone failure. Record p50/p95/p99, errors, resource peaks and cost per active tenant/session.
The 50/70 simple-fixture hour windows passed. Next measure representative authorized browser
workflows and then multiple execution cells, without carrying fixture density into a service quote.
No paid environment is provisioned by this document.
