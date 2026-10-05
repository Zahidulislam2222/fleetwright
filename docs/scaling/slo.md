# Availability, SLOs and error budgets

## What the percentages mean

| Availability per 30 days | Allowed downtime | Failed requests allowed per 10M |
|---|---|---|
| 99% | 7.2 hours | 100,000 |
| 99.5% | 3.6 hours | 50,000 |
| **99.9% (Fleetwright cloud target)** | **43.2 minutes** | **10,000** |
| 99.95% | 21.6 minutes | 5,000 |
| 99.99% | 4.3 minutes | 1,000 |

Each extra nine divides the budget by ten and multiplies the engineering cost.

## Current state (honest)

The public site runs on **one shared server**. There is no redundancy and no uptime monitoring yet,
so **no availability figure is claimed**. The targets below apply to the cloud reference
architecture ([scaling](README.md), stage 2 onward).

## Service level indicators and objectives (targets)

| SLI | How it is measured | SLO (target) |
|---|---|---|
| API availability | Share of valid `/v1` requests answered without a 5xx, at the load balancer | 99.9% per 30 days |
| Console availability | Share of successful requests for the static console from the CDN | 99.9% per 30 days |
| Live-update freshness | Time from a claim state change to the event reaching a connected console, p95 | < 2 s |
| Dispatch latency | Detection (`seen_at`) → claim queued, p95 | < 250 ms |
| Booking latency | Detection → confirmed booking, p95 (target-site time included) | < 1 s on the mock board (measured today: ≈ 540 ms) |
| Session health | Share of accounts with a valid session when a matching job appears | 99% |

**Correctness is not an SLO.** Zero duplicate bookings is an invariant enforced by the database.
A single duplicate is an incident, never "within budget".

## Error budget policy (target)

- Burn-rate alerts: fast burn (2% of the monthly budget in 1 hour) pages the on-call engineer;
  slow burn (10% in 3 days) opens a ticket.
- When the budget is spent: feature releases stop, reliability work takes priority until the
  rolling 30-day figure is back above the target.
- Every incident that spends more than 25% of the budget gets a written post-incident review.

## Recovery objectives (targets)

| Objective | Target | How |
|---|---|---|
| RPO (data loss) | ≤ 5 minutes | Point-in-time recovery on managed Postgres; Redis holds no data that cannot be rebuilt from Postgres |
| RTO (time to recover) | ≤ 1 hour for a region-level failure of one service; minutes for an instance | Multi-AZ failover, stateless services restarted by the orchestrator |
| Restore drill | Quarterly | Restore to a fresh database and run the integrity checks |

## How the design supports 99.9%

- Stateless services behind a load balancer; any instance can be replaced.
- Multi-AZ managed Postgres and Redis; workers spread across zones.
- Rolling deploys with health checks; database migrations are backward compatible for one release.
- Graceful degradation: if Redis for one cell fails, that cell stops dispatching but loses no claims
  (they are in Postgres and the outbox relay re-publishes); other cells are unaffected.
- Worker crashes are routine: leases expire on the database clock and are swept.
