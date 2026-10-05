# Fleetwright

**A control plane for fleets of real browsers.** Fleetwright runs many logged-in Playwright browser
sessions, watches a job feed, and books each matching job **exactly once**, even when workers
crash, networks drop or two machines race for the same job.

- **Live site:** <https://fleetwright.zahidul-islam.com> (landing page and console design prototype)
- **Status:** active development. See [Project status](#project-status) for exactly what works today
  and what is still a design target.
- **Demo target:** a fictitious load board built in this repository (`apps/mockboard`). Fleetwright
  is never pointed at a real third-party site in this project. See [Legal and acceptable use](docs/legal/README.md).

---

## What problem it solves

Teams that automate a web workflow with many accounts usually start with independent scripts. That
works for one or two browsers and breaks at fifty:

- two scripts book the same job, or neither does;
- a crash in the middle of a booking leaves nobody knowing whether it went through;
- sessions expire, one-time codes arrive by email, and someone has to log in by hand;
- nobody can say how fast the fleet reacts, because nothing is measured.

Fleetwright moves the hard parts into one coordinated system: a database-enforced claim state
machine, a session vault, a dispatcher with hot-reloaded filters and schedules, a reconciler for
uncertain outcomes, and per-stage latency measurement.

## Measured results

All numbers below were measured on one developer PC (12 CPU threads, 24 GB RAM) against the mock
board. They are not projections. Scale targets are separate and are labelled as targets in
[docs/scaling](docs/scaling/README.md).

| What | Result | How it was measured |
|---|---|---|
| Duplicate bookings under contention | **0** across 10,000 jobs with 200 concurrent competitors; 9,897 claims confirmed = 9,897 bookings on the board | `packages/fw_core/tests/test_claims.py` (slow test), checked against the board's own ground-truth log |
| Crash in the middle of a booking | Every job ends confirmed, failed or reconciled; no lease stays stuck past its TTL | Crash and chaos tests in `test_claims.py` and `apps/worker/tests/test_engine.py` |
| Detection to confirmed booking (end to end) | p50 ≈ 365 ms, p95 ≈ 540 ms | Per-stage timestamps in Postgres, `fw_core/latency.py` |
| Memory per browser context | ≈ 70–103 MB (USS); planning figure 100 MB | Fleet capacity run at 8, 16 and 32 contexts |
| CPU at 32 contexts | ≈ 1.8 cores | Same run |
| Tenant isolation | Tenant A cannot read or write tenant B rows, even as the table owner | `packages/fw_core/tests/test_rls.py` (mutation-checked) |
| Automated tests | 66 passing (unit, integration, real Chromium, 200×10,000 load) | `uv run pytest` |

## Project status

| Area | State |
|---|---|
| Mock load board (login, emailed one-time code, captcha, live feed, first-booker-wins, adversity switches) | **Built and tested** |
| Data model, Postgres row-level security, claim state machine with fencing tokens, outbox | **Built and tested** |
| Worker runtime (browser contexts, session vault, OTP, proxy and captcha adapters, failure evidence) | **Built and tested** |
| Live engine (watcher, dispatcher, actor, reconciler, filters, schedules, cells, latency) | **Built and tested** |
| Console UI | **Design prototype** with mock data (live at the URL above) |
| Console API, login with MFA, roles, live updates | **In progress** (not in this release) |
| Crawler worker, local AI agent | Planned ([roadmap](docs/roadmap.md)) |
| Monitoring stack, AWS reference, compliance pack | Planned ([roadmap](docs/roadmap.md)) |

## Architecture in one picture

```
            mock load board (or an authorised target)
               ▲  feed responses          ▲ booking requests
               │                          │
   ┌───────────┴──────────┐   ┌───────────┴──────────┐
   │ watcher slots        │   │ claimer slots        │   worker processes:
   │ (read the feed API)  │   │ (warm, logged in)    │   one Chromium, many contexts
   └───────────┬──────────┘   └───────────▲──────────┘
               │ detected                 │ act
               ▼                          │
   ┌─────────────────────── cell Redis (Streams) ───────────────────────┐
   └───────────┬──────────────────────────▲─────────────────────────────┘
               ▼                          │
   ┌──────────────────────┐   ┌───────────┴──────────┐
   │ dispatcher           │   │ outbox relay         │   control process per cell
   │ filters + schedules  │   │ reconciler           │
   └───────────┬──────────┘   └───────────▲──────────┘
               ▼                          │
   ┌──────────────── Postgres: the source of truth (RLS per tenant) ────┐
   │ claims · fencing tokens · claim_events · outbox · audit_log        │
   └────────────────────────────────────────────────────────────────────┘
```

Read more: [architecture overview](docs/architecture/overview.md) ·
[claim lifecycle](docs/architecture/claim-lifecycle.md) · [decisions (ADRs)](docs/adr/README.md).

## Repository layout

| Path | What it is |
|---|---|
| [`apps/mockboard`](apps/mockboard/README.md) | The fictitious demo load board (FastAPI) the fleet is tested against |
| [`apps/coordinator`](apps/coordinator/README.md) | Migrations and the per-cell control process (dispatcher, relay, reconciler) |
| [`apps/worker`](apps/worker/README.md) | Browser worker runtime: watcher and claimer slots |
| [`apps/gateway`](apps/gateway/README.md) | Live-update gateway (placeholder; in progress) |
| [`apps/dashboard`](apps/dashboard/README.md) | Next.js landing page and console |
| [`packages/fw_core`](packages/fw_core/README.md) | Settings, database, claim state machine, crypto, vault, filters, latency |
| [`packages/fw_queue`](packages/fw_queue/README.md) | Redis Streams, key layout, outbox relay |
| [`packages/fw_browser`](packages/fw_browser/README.md) | Login, captcha, proxy, browser profiles, failure evidence |
| [`config`](config/README.md) | Validated YAML product data (targets, browser profiles, proxies, demo catalogue) |
| [`infra/compose`](infra/compose/local.yaml) | Local stack: Postgres, three Redis instances, Mailpit |
| [`docs`](docs/README.md) | Architecture, ADRs, scaling, security, legal, operations, roadmap |

## Quick start (local)

Requirements: Python 3.12 via [uv](https://docs.astral.sh/uv/), Docker, Node.js 24 (dashboard only).

```bash
uv sync                                         # install the workspace
uv run playwright install chromium              # browser for workers and tests
uv run python tools/dev/make_env.py             # create .env with fresh random secrets
docker compose -f infra/compose/local.yaml --env-file .env up -d --wait
uv run python -m fw_coordinator.migrate         # schema, roles and row-level security
uv run pytest                                   # full suite (includes a ~6 min load test)
```

Run the pieces by hand: see [docs/operations/local-development.md](docs/operations/local-development.md).

## Documentation

| Topic | Document |
|---|---|
| How it works | [Architecture](docs/architecture/overview.md), [claim lifecycle](docs/architecture/claim-lifecycle.md) |
| Why it is built this way | [Architecture decision records](docs/adr/README.md) |
| Scale to 1M+ sessions and 99.9% availability | [Scaling](docs/scaling/README.md), [capacity model](docs/scaling/capacity-model.md), [SLOs](docs/scaling/slo.md) |
| Security | [Security policy](SECURITY.md), [threat model](docs/security/threat-model.md), [controls](docs/security/controls.md) |
| Law and acceptable use (US and EU) | [Legal overview](docs/legal/README.md), [privacy](docs/legal/privacy.md), [acceptable use](docs/legal/acceptable-use.md) |
| Running it | [Local development](docs/operations/local-development.md), [configuration](docs/operations/configuration.md), [runbooks](docs/operations/runbooks.md) |
| Proof | [Testing and evidence](docs/testing.md) |
| What comes next | [Roadmap](docs/roadmap.md), [changelog](CHANGELOG.md) |

## License

Copyright © 2026 Zahidul Islam. All rights reserved. The source is published so that clients and
reviewers can evaluate it; it is not open source. See [LICENSE](LICENSE).
