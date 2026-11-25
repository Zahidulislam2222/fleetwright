# Baseline workload: 500–1,000 normal users

This page models the first realistic audience — a few hundred to a thousand people using the
public console and demo — next to the long-range [1M+ path](README.md). Every number below is
labelled **measured** (with its source) or **assumption/extrapolated**. Nothing here is a capacity
commitment; the single shared server remains one failure domain.

## Definitions and assumptions

| Quantity | Assumption | Basis |
|---|---|---|
| Registered console users | 1,000 (operators, reviewers, demo guests) | Assumption |
| Daily active users | 150–300 | Assumption (15–30% of registered) |
| Peak concurrent console sessions | 50–100 normally | Assumption |
| Burst (shared link, proposal review) | 1,000 concurrent for 10 minutes | Assumption |
| Reads per session | Up to 1 refresh / 15 s (worst case: stream down), plus page loads | Console `pollMs` = 15,000; with the stream up, refetches follow events |
| Live-update connections | 1 per open console tab | Design |
| Mutations | < 1% of sessions, about 1 per minute (filters, demo controls) | Assumption |
| Assistant use | 10% of daily users ask 2 questions | Assumption |
| Payloads | List pages capped at 200 items; assistant answer ≤ 600 output tokens | Configuration |

Derived load (extrapolated, worst case): about 7 reads/s and 100 open streams at a normal peak;
about 67 reads/s and 1,000 open streams during a burst; about 60 assistant questions a day.

## What has been measured

- Control plane on a developer machine, overlapping other local work (measured, 13 Oct 2026):
  16 API clients and 32 live-update clients for 30 s gave 1,199 requests, 192 stream connections,
  zero HTTP errors; API latency p50/p95/p99 223/763/1,637 ms. Not isolated capacity and not an SLO.
  See [verification](verification-2026-10-13.md).
- Browser fleet (measured): 50 and 70 contexts sustained for an hour on an isolated server test.
- Configured ceilings (configuration, not measurements): gateway `max_clients` 2,000 per instance;
  the public edge allows 1,500 total live streams; page size ≤ 200.

## Assessment

| Path | Normal peak (100 sessions) | Burst (1,000 sessions) |
|---|---|---|
| API reads | ~7 reads/s: below the measured local rate (~40 requests/s) (extrapolated) | ~67 reads/s: above anything measured; **unmeasured** on the shared server |
| Live updates | 100 streams: far below configured ceilings | 1,000 streams: below the 1,500 edge cap but **unmeasured** |
| Database | Bounded queries, RLS, pooled connections | Pool waits possible; watch pool and slow-query metrics |
| Assistant | ~60 questions/day ≈ $0.12/day at measured-price assumptions | Per-address limit + $0.50/day budget; excess answers fall back to documentation search |
| Static console | CDN-cacheable export | CDN absorbs page loads |

Bottlenecks to watch first: live-update fan-out on the single gateway, database connection pool
across API and control loops, and CPU contention from other applications on the shared server.

## Placement and cost

The demo runs on an existing shared server that is already paid for, so the marginal hosting cost
is $0. Cloud free allowances (AWS/GCP/Azure, not re-verified on 25 Nov 2026) are sized for one small
always-on VM or request-based serverless functions; Fleetwright's ten long-running containers
(including a Chromium worker needing ~1.5 GiB) do not fit them, and moving would add cost without a
reliability gain for this audience. Recommendation: keep the shared server for the demo, serve static
assets through the CDN, and keep the AWS reference (`infra/terraform`, plan only) for a client that
needs multi-zone availability. Paid assistant spend is capped by the provider key (≤ $5/month) and
the in-app daily budget.

## Validation still required (Deferred)

| Check | Why | Owner / timing |
|---|---|---|
| Burst test: 1,000 streams + 67 reads/s against an isolated copy, not the shared production server | Converts the burst row from extrapolated to measured without risking other applications | Owner approval; before advertising the demo widely |
| Assistant latency and cost over a real week | Replaces the per-question cost assumption with measured spend | Operator; first week after release, from the owner-only daily counters |
