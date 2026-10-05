# Testing and evidence

Fleetwright's claims are backed by tests that run against real infrastructure: Postgres, Redis,
Mailpit, a real Chromium and a real (mock) board. **66 automated tests pass** on the current
release, including a load test of 200 competitors × 10,000 jobs.

## How correctness is checked

The mock board keeps a **ground-truth log**: when each load was published and who booked it. Tests
compare Fleetwright's own records with that log, so the system is never marking its own homework.

## Suites

| Suite | Path | What it proves |
|---|---|---|
| Settings and configuration boundary | `packages/fw_core/tests/test_settings.py`, `test_config_boundary.py` | `.env.example` matches the settings model; a hardcoded URL or secret pattern in business code fails the build |
| Row-level security | `packages/fw_core/tests/test_rls.py` | Tenant isolation; no tenant set → zero rows even for the table owner; insert checks; worker role limits; audit log append-only; every tenant table forced and every index led by `tenant_id` |
| Claim state machine | `packages/fw_core/tests/test_claims.py` | Happy path with full history; duplicate detection; 20-way lease race; stale fence rejected; crash while leased → re-queued; crash while acting → `UNKNOWN` → reconciled; late actor; account mutex; queued expiry; property-based interleavings (Hypothesis) |
| Load test (slow) | `test_claims.py` | 200 competitors × 10,000 jobs with production timings: 9,897 confirmed = 9,897 bookings on the board, **0 duplicates**, ≥ 95% booked, every crash during `ACTING` reconciled |
| Filters and schedules | `packages/fw_core/tests/test_filters.py` | Criteria, first-match order, overnight and time-zone windows, invalid windows rejected |
| Streams and outbox | `packages/fw_queue/tests/test_queue.py` | `{tenant}` hash tags; reclaim and dead-letter; relay publishes once; rows survive a Redis outage |
| Browser units | `packages/fw_browser/tests/test_browser_units.py` | Shipped config validates; profiles; sticky proxies that rotate after repeated blocks and prefer healthy exits; session refresh timing; evidence retention; one-time-code extraction |
| Mock board | `apps/mockboard/tests/test_board.py` | Login → emailed code → session; first-booker-wins and double-booking detection; CSRF on booking; every adversity switch (rate limit, errors, slow, lost acknowledgement, layout change, rival bots, forced expiry, single session, captcha); feed reaches 100 loads per second; admin API protected; invalid settings → 422 |
| Worker runtime | `apps/worker/tests/test_runtime.py` | Real Chromium: sign-in, heartbeat, restart without a new code, drain; revoked session; captcha; evidence; **no secrets in logs or events**; account hold lost |
| Live engine | `apps/worker/tests/test_engine.py` | Calm run books every matching load once; chaos run (lost acknowledgements, errors, slow responses, rival bots) has zero duplicates and reconciles every lost answer; click mode; tenant moved between cells while running |
| Control process | `apps/coordinator/tests/test_control.py` | One claim per job with filters and hot reload; tenant move hands over queued claims and the old cell stops publishing |

## Tests that were proven able to fail

A green test means nothing if it cannot go red. Some checks were mutation-tested on purpose:

- Removing `FORCE ROW LEVEL SECURITY` from one table makes the RLS suite fail.
- Writing a secret into a log line makes the log-leak test fail.
- An early version of the load test booked only 77 of 10,000 jobs and still passed; coverage
  assertions (≥ 95% booked) were added so a fleet that does nothing cannot pass.

## Console (design prototype)

Lint, type check and production build; WCAG contrast check on every colour pair; browser checks of
every screen at several widths in light and dark themes; accessibility regression tests for focus,
dialogs, reduced motion and overflow; Content-Security-Policy violations checked in development and
production builds.

## Measurements

| Measurement | Result | Where |
|---|---|---|
| Detection → confirmed booking | p50 ≈ 365 ms, p95 ≈ 540 ms | Engine tests, per-stage latency from Postgres timestamps |
| Memory per browser context | ≈ 70–103 MB (USS) | Capacity run at 8, 16, 32 contexts |
| CPU at 32 contexts | ≈ 1.8 cores | Same run |

Known limits of this evidence: one developer PC; the mock board, not a real site; the 50- and
70-context one-hour runs are still to do ([roadmap](roadmap.md)).
