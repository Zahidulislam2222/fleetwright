# Testing and verification evidence

The 14 October runtime regression passed **289 tests with six expected skips in 831.04 seconds**:
295 collected cases, zero failures/errors and 435 source/tool hashes unchanged throughout.
This frozen run used `59c1cc0`; release source `41f5f16` adds only the central unique web-image tag.
Its 14 configuration and two CSP regressions passed; all 224 backend archive file bytes are identical.
Actual driver/browser-loss recovery, bounded stalled-protocol/SIGTERM and readiness regressions passed.
Four POSIX privacy checks and a POSIX release-symlink check passed separately; the installed-model
opt-in was exercised through three actual local-model/browser receipts.

An earlier recording exposed unsaved local-agent edits being lost after blur/polling. The strengthened
native test failed before the correction and passed afterward, including exact edited title/body
in the final destination receipt. The full affected agent/configuration suite then passed **25 tests
with five expected skips**. Platform-specific POSIX checks passed separately on Linux, and actual
installed-model evidence covers all three templates.

## Current assurance

| Gate | Recorded result and scope |
|---|---|
| Python | Ruff passed; 236 files passed formatting; strict types passed on 87 source files; nine workspace wheel/sdist builds passed, including repeated affected-package builds |
| Dashboard | ESLint, generated route types, TypeScript, static 18-page build and configured contrast checks passed |
| Source security | Gitleaks, Bandit and Semgrep passed without suppressions; retained dependency findings are documented separately |
| Native images | Final application and web images: zero HIGH/CRITICAL findings with native SBOM/identity binding |
| Exact local release | Both MCP workflows, grant revocation, owner UI, crawler/export, public authorization, SPA navigation and responsive checks passed |
| Static CSP | Fifteen real routes observed after navigation; no recorded script-policy violations/page errors in the accepted run |
| Deployed behavior | Public MCP workflows/receipts/revocation, owner console/crawler export and HTTP/audit/SSE passed; all 15 public routes hydrated with zero recorded CSP/page errors over full ten-second observations |
| Historical 13 October rc4 lifecycle | Freight four slots/zero held accounts/exit 0; controlled 12-second workflow drain; crawler exit 0/non-OOM and exact restart; all used the configured 60-second grace |
| Durable restart / rollback | Separate crawler processes resumed after natural lease expiry with higher fencing and identical four-record export; static rollback preserved a pending mailbox record and backend identities |
| Browser endurance | 50 contexts: 3601.986s / 25,800 fixture clicks; 70 contexts: 3602.632s / 32,760 fixture clicks; zero errors |
| Historical independent recovery | Final rc4 independent encrypted archive restored into two fresh local databases: 24+8 public tables / 32,941+83,766 rows; every source COPY-row count matched |
| Current deployed backup | Post-activity archive restored into two fresh verification databases with 11 jobs/11 approvals/55 events/35 grants matched; one scheduler process-death recovery in 66.76 seconds produced a fresh archive |
| Current supervision | Actual local rc3 driver/browser loss each recovered with one container restart in 7.703/8.031 seconds; four ready slots, strict exit0 drain/zero holds and unchanged other containers. Live monitor recovered in 33.37 seconds with renewed observe-only access/four healthy probes |
| Passive dynamic scan | Exact rc4: 78.450 seconds, zero HIGH / one MEDIUM / one LOW / six informational alerts; raw exit 2, retained inline-style CSP and COEP warnings |

These are scoped results. Image findings depend on the recorded database/time and exact identity.
Fixture contexts are not authenticated freight workers; source gates, signed artifacts and live
deployment are separate proofs. See [current release evidence](releases/2026-10-14.md) and [historical evidence](releases/2026-10-13.md) and
[capacity observations](scaling/verification-2026-10-13.md).

## Run reproducibly

Use `uv run python tools/dev/run_tests.py -q` after preparing the local data/destination services.
The harness serializes runs, migrates isolated local databases and propagates settings to child
workers. Do not overlap database-resetting suites. Build the dashboard before approval-console
browser tests. The installed-model test is explicit opt-in; its absence in CI is not model proof.

### Historical baseline

The earlier reliable-browser release covered 148 cases across a 147-passing regression run and a
separate unchanged contention benchmark (205.19s). The combined run had a connection-capacity
failure; it was never described as 148 passing together. Earlier latency/memory measurements below
remain historical and retain their hardware/workload boundary.

The earlier completion run passed 260 cases with six skips before the final lifecycle regressions.
A later 270-case attempt failed during application/destination startup. The unchanged failed-node
selection subsequently passed, followed by the complete 280-case passing run above. The precise
cause of the earlier startup failures was not established; their records remain preserved.

## How correctness is checked

The owned freight board keeps a **ground-truth log**: when each load was published and who booked it. Tests
compare Fleetwright's own records with that log, so an internal success flag alone cannot establish the external outcome.

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

Lint, type check and production build; configured WCAG contrast-pair checks; browser checks of
every screen at several widths in light and dark themes; accessibility regression tests for focus,
dialogs, reduced motion and overflow; Content-Security-Policy violations checked in development and
production builds.

## Measurements

| Measurement | Result | Where |
|---|---|---|
| Detection → confirmed booking | p50 ≈ 365 ms, p95 ≈ 540 ms | Engine tests, per-stage latency from Postgres timestamps |
| Memory per browser context | ≈ 70–103 MB (USS) | Capacity run at 8, 16, 32 contexts |
| CPU at 32 contexts | ≈ 1.8 cores | Same run |

Historical latency/context-density measurements used one developer PC and owned destinations.
The later 50/70-context fixture hours above passed under their recorded limits; representative
authenticated customer throughput remains future work ([roadmap](roadmap.md)).

## Completion regression coverage

The durable crawler suite exercises real HTTP, numeric DNS pinning, trusted-CA TLS hostname
verification, redirect refusal, valid-JSON truncation, physical slow-response termination,
per-request pacing, crash fences, quality guards, cancellation, tenant/export boundaries and
retention. The standalone agent suite exercises exact-action authority, unknown-outcome receipts,
loopback API boundaries, prompt injection, lifetime WebSocket denial and private state. Its actual
local Ollama/Chromium run is a separate proof; POSIX-only permissions run on Linux.

Operational tests cover bounded collection, observe-only renewal/revocation, failure/recovery
persistence, retention cursor reuse and encrypted archive validation. Release-artifact tests reject
tampering, missing/extra files, unsafe paths, symlinks and wrong trust anchors. The published settings
schema is checked against typed model definitions without loading runtime environment values.

Raw-detection handover tests use real Redis and isolated databases to prove unread old-cell replay,
authoritative in-flight payloads, relay/dispatch crash boundaries, retry, tenant isolation and atomic
move rollback. Account policy tests include delayed browser preparation and completion cooldown;
workflow scheduling and retired-generation drain retain bounded fair turns and stopped states.
These tests supplement the unchanged contention workload rather than replacing it.

Lifecycle regressions also cover a removed retired tenant during fleet drain, failure reporting
after cleanup and Linux crawler SIGTERM cancellation. The physical crawler control changed a
forced exit 137 into exit 0 with fetch-child termination/reaping, socket closure and engine cleanup.
Exact rc4 rehearsal independently verified successful stops and restoration using the final image.

## Publication regression coverage

`test_publication_contract.py` checks maintained display wording, public links/required topics,
workflow runner/service release inputs, complete typed backup environment, normalized service paths,
container shutdown grace and reserved seed groups.
The missing backup fields produced a failing regression before the fix. Same-target reserved-account
acquisition is covered by `apps/worker/tests/test_account_target_scope.py`. Actual worker coexistence
is also a release-rehearsal gate. GitHub quality CI covers static/config/publication gates; the full
Docker/Chromium suite remains a separate release gate.

## New durable boundaries and escaped-defect checks

- Crawler: `test_crawler.py` and `test_crawler_adversity.py` cover HTTP/TLS scope, truncated data,
  physical process termination before retry, pacing, crash fences, quality and export isolation.
- Detection mailbox: `test_detection_handover.py` covers unread/in-flight delivery, authoritative
  payloads, transaction rollback and current-cell replay.
- Account policy: `test_workflow_pacing.py` includes delayed preparation and completion cooldown.
- Agent: approval authority, prompt injection, API safeguards, receipts, cancellation, POSIX privacy
  and real dedicated/CDP WebSocket denial. An independent unguarded Chromium control must reach the
  rejecting sink before guarded zero-contact assertions can pass.
- UI: exact edited title/body must survive blur, manual refresh and periodic polling, then appear in
  the fresh proposal and destination receipt; a CONFIRMED label alone is insufficient.
- Operations: `test_monitor_recovery.py` covers observe-only renewal, safe telemetry, notification
  persistence, retention and authenticated archive validation. Release-signature tests reject
  changed/missing/extra/unsafe files and wrong trust anchors.

Retain failing-before evidence and report omitted gates explicitly. The production regression
suite is committed CI tooling; private manual capture/recovery scripts and their raw artifacts remain
local. See [maintenance](maintenance.md) for independent review and defect handling.
