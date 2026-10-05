# Capacity model

How many machines each scale tier needs, worked out from measured inputs. Every number is labelled
**measured**, **estimate** or **target**. Estimates must be replaced by measurements before any
capacity is promised to a client.

## Measured inputs (developer PC, 2026-10-05)

| Input | Value | Source |
|---|---|---|
| Memory per browser context | 70–103 MB unique set size; **100 MB** used for planning | Fleet capacity run at 8 / 16 / 32 contexts, Chromium child processes included |
| CPU at 32 contexts | ≈ 1.8 cores (≈ 0.06 cores per context) | Same run, idle feed polling |
| Detection → confirmed booking | p50 ≈ 365 ms, p95 ≈ 540 ms | Per-stage timestamps in Postgres |
| Claims under contention | 10,000 jobs, 200 concurrent competitors, 0 duplicates | Slow test in `test_claims.py` |

The CPU figure is for watching a feed and acting on bookings. Pages with heavy scripts or video
use more; measure per target before sizing.

## Worker plane

Planning rule (estimate): **≈ 75 contexts per 8 GB node**, leaving about 0.5 GB for the operating
system and the worker process itself; CPU is not the limit at that density (≈ 4.5 cores).

| Tier | Contexts | Nodes of 8 GB (estimate) | Cells (estimate, ≈ 500 contexts per cell) | Status |
|---|---|---|---|---|
| Pilot | 50 | 1 | 1 | Within measured range per node |
| Small | 500 | ≈ 7 | 1 | Extrapolated |
| Large | 5,000 | ≈ 67 | ≈ 10 | Extrapolated |
| Very large | 10,000 | ≈ 134 | ≈ 20 | Extrapolated |

Cell size of ≈ 500 contexts is an estimate: one Redis instance handles far more stream traffic than
500 contexts generate, so the real limit is expected to be the blast radius you accept for one cell
failure, not Redis throughput. It will be set by a load test.

## Control plane

| Tier (concurrent console sessions) | Gateway instances (estimate, ≈ 20,000 SSE connections each) | API instances (estimate) | Postgres | Status |
|---|---|---|---|---|
| 1,000 | 1 (2 for redundancy) | 2 | Primary + standby | Target |
| 10,000 | 2 | 2–4 | Primary + standby | Target |
| 100,000 | ≈ 5–10 | 4–8 | + read replicas, connection pooler | Target |
| 1,000,000 | ≈ 50–100 | 10–20 | + replicas per region, partitioned `claims` / `claim_events` / `audit_log` | Target |

Why this is plausible (estimates, to be load-tested):
- Live updates use server-sent events. Each gateway subscribes once per tenant channel in Redis
  and fans out to its own clients, so Redis load grows with tenants, not with viewers.
- The console is a static export: served from a CDN, it adds no server load per viewer.
- Reads dominate. Lists are cursor-paginated and bounded; heavy views (latency, overview) can be
  served from replicas or short caches.

## What has not been measured yet

| Unknown | How it will be measured | Roadmap |
|---|---|---|
| Claims per second one Postgres primary sustains | Load test of the claim path with many cells | Hardening phase |
| SSE connections per gateway instance | k6 against the gateway, p95 fan-out latency | Console phase |
| A 50- and 70-context fleet for one hour | Fleet run on a dedicated machine | Hardening phase |
| Memory on real target sites | Per-target capacity run | Per client |

## Cost

No cost figures are published here. Prices change, and any paid infrastructure is approved by the
owner with an exact quote before it is created.
