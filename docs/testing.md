# Testing and evidence

Release verification on 2026-10-13 exercised **148 automated cases** against isolated
PostgreSQL/Redis/Mailpit and real Chromium. The final combined run had147passed and one
`TooManyConnectionsError` in the contention benchmark (461.34seconds); an accidental overlapping
test invocation was observed. After stopping the overlap, the unchanged benchmark passed
separately in205.19seconds. All final cases therefore have passing evidence across those runs;
this is not a claim that148passed together. The previous full147-case run passed in546.13seconds. This includes publication contracts,
complete backup settings and reserved workflow-account coexistence rules. The previous core
extension run passed132tests in467.58seconds; its evidence remains historical.

Use `python tools/dev/run_tests.py -q` to migrate and run against isolated local test databases.
Build the dashboard first for the approval UI browser test. Earlier verification split the
suite into `-m 'not slow'` and the existing 200-competitor/10,000-job test, run sequentially.
An earlier full run exceeded that test's 900-second convergence deadline; the unchanged isolated
rerun passed in 202.45 seconds. Its original deadline and correctness assertions were retained.

## How correctness is checked

The owned freight board keeps a **ground-truth log**: when each load was published and who booked it. Tests
compare Fleetwright's own records with that log, so the system is never marking its own homework.

## Suites

| Suite | Path | What it proves |
|---|---|---|
| Settings and configuration boundary | `packages/fw_core/tests/test_settings.py`, `test_config_boundary.py` | `.env.example` matches the settings model; a hardcoded URL or secret pattern in business code fails the build |
| Row-level security | `packages/fw_core/tests/test_rls.py` | Tenant isolation; no tenant set → zero rows even for the table owner; insert checks; worker role limits; audit log append-only; every tenant table forced and every index led by `tenant_id` |
| Claim state machine | `packages/fw_core/tests/test_claims.py` | Happy path with full history; duplicate detection; 20-way lease race; stale fence rejected; crash while leased → re-queued; crash while acting → `UNKNOWN` → reconciled; late actor; account mutex; queued expiry; property-based interleavings (Hypothesis) |
| Load test (slow) | `test_claims.py` | 200 competitors × 10,000 jobs: 9,895 confirmed/reconciled destination bookings, **0 duplicate action attempts**, ≥ 95% booked, all 211 injected ACTING crashes reconciled; strict destination model counts rejected duplicates too |
| Filters and schedules | `packages/fw_core/tests/test_filters.py` | Criteria, first-match order, overnight and time-zone windows, invalid windows rejected |
| Streams and outbox | `packages/fw_queue/tests/test_queue.py` | `{tenant}` hash tags; reclaim and dead-letter; relay publishes once; rows survive a Redis outage |
| Browser units | `packages/fw_browser/tests/test_browser_units.py` | Shipped config validates; profiles; sticky proxies that rotate after repeated blocks and prefer healthy exits; session refresh timing; evidence retention; one-time-code extraction |
| owned freight board | `apps/mockboard/tests/test_board.py` | Login → emailed code → session; first-booker-wins and double-booking detection; CSRF on booking; every adversity switch (rate limit, errors, slow, lost acknowledgement, layout change, rival bots, forced expiry, single session, captcha); feed reaches 100 loads per second; admin API protected; invalid settings → 422 |
| Worker runtime | `apps/worker/tests/test_runtime.py` | Real Chromium: sign-in, heartbeat, restart without a new code, drain; revoked session; captcha; evidence; credential/code redaction in tested logs and events; account hold lost |
| Live engine | `apps/worker/tests/test_engine.py` | Calm run books every matching load once; chaos run (lost acknowledgements, errors, slow responses, rival bots) has zero duplicates and reconciles every lost answer; click mode; tenant moved between cells while running |
| Control process | `apps/coordinator/tests/test_control.py` | One claim per job with filters and hot reload; tenant move hands over queued claims and the old cell stops publishing |
| Durable workflows and access | `apps/coordinator/tests/test_workflows.py`, `test_workflow_review.py`, `test_mcp.py` | Exact approvals, idempotency, fencing, cancellation, retained uncertainty, fair recovery, scoped SDK transport and immediate revocation |
| Workflow browser and approval UI | `test_workflow_browser.py`, `test_workflow_console.py` | Both owned workflows, interrupted response, actual worker process death after acceptance, matching receipts, owner review and evidence download |
| Backup restoration | `apps/coordinator/tests/test_backup.py` | Delayed initialization rejects temporary socket-only readiness; approved job, events, approval and audit restored into a fresh network-isolated database cluster |
| Deterministic action contracts | `packages/fw_core/tests/test_workflow_contract_fingerprint.py` | Eight independent process hash seeds produce the same contract fingerprint; regression failed before canonical serialization |
| General authentication | `test_workflow_auth_contract.py`, `apps/worker/tests/test_account_target_scope.py` | Non-freight targets need no freight endpoints; legacy slots leave service-only accounts available |
| Cached session recovery | `apps/coordinator/tests/test_workflow_session_recovery.py` | Expired/revoked sessions renew before acting; receipt-only recovery respects account contention, authentication failure, lease deadlines and replacement holders |
| Login readiness | `apps/coordinator/tests/test_login_readiness.py` | A delayed real session handshake cannot skip password authentication or advance early to MFA |
| Shared audit contract | `apps/coordinator/tests/test_workflow_audit_contract.py` | Owner and public audit HTTP reads remain valid after workflow events are written |

Actual Codex client submission, outcome inspection and evidence export passed for both owned
workflows using the existing ChatGPT login. This is separate from SDK transport testing.
Claude's model-driven run was deferred by the owner while its subscription is off. See the
[workflow runbook](operations/reliable-browser.md) for configuration and operating boundaries.

## Tests that were proven able to fail

A green test means nothing if it cannot go red. Some checks were mutation-tested on purpose:

- Unsorted contract-set serialization produced different fingerprints across explicit process hash seeds; canonical serialization made the regression pass.
- A delayed PostgreSQL initializer exposed false socket readiness; the bounded TCP readiness probe passed the restore regression.
- Expired/revoked destination state and delayed/stolen authentication reservations failed before the bounded, ownership-checked renewal correction.
- Submitting during a delayed login handshake failed before the readiness guard; mixed workflow audit history failed before its audit-only role was added to the wire contract.
- Removing `FORCE ROW LEVEL SECURITY` from one table makes the RLS suite fail.
- Writing a secret into a log line makes the log-leak test fail.
- An early version of the load test booked only 77 of 10,000 jobs and still passed; coverage
  assertions (≥ 95% booked) were added so a fleet that does nothing cannot pass.

## Console

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

Known limits of this evidence: one developer PC; the owned freight board, not a real site; the 50- and
70-context one-hour runs are still to do ([roadmap](roadmap.md)).

## Publication regression coverage

`test_publication_contract.py` checks maintained display wording, public links/required topics,
workflow runner/service release inputs, complete typed backup environment, normalized service paths,
container shutdown grace and reserved seed groups.
The missing backup fields produced a failing regression before the fix. Same-target reserved-account
acquisition is covered by `apps/worker/tests/test_account_target_scope.py`. Actual worker coexistence
is also a release-rehearsal gate. GitHub quality CI covers static/config/publication gates; the full
Docker/Chromium suite remains a separate release gate.
