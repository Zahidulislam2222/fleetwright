# Architecture overview

Fleetwright is a control plane for a fleet of real browsers. This page explains the parts, how data
moves between them, and where each guarantee comes from. Decisions and their reasons are recorded in
the [ADRs](../adr/README.md); the claim state machine has its own page:
[claim lifecycle](claim-lifecycle.md).

## Context

```
 operators (browser) ──HTTPS──▶ console (Next.js, static) ──/v1──▶ API + live-update gateway  [in progress]
                                                                        │
                                       ┌────────────────────────────────┴──────────┐
                                       ▼                                           ▼
                                  Postgres  ◀──── control process per cell ────▶ cell Redis
                                       ▲                                           ▲
                                       └──────────── worker processes ─────────────┘
                                                          │ real Chromium
                                                          ▼
                                        mock load board / an authorised target site
```

## Containers and responsibilities

| Part | Code | Responsibility | State it owns |
|---|---|---|---|
| Postgres | `apps/coordinator/.../migrations` | Source of truth: tenants, accounts, sessions (sealed), filters, schedules, jobs, claims, claim history, outbox, audit log, workers | Everything durable |
| Core Redis | `fw_queue.keys` | Control-plane keys: console sessions, login rate limits, demo state | Short-lived only |
| Cell Redis (one per cell) | `fw_queue.streams` | Streams `detected`, `act`, dead-letter; fast-path duplicate keys; filter reload channel | Short-lived only; loss is recoverable from Postgres |
| Control process (one per cell) | `fw_coordinator.control` | Dispatcher (filters and schedules), outbox relay, reconciler, lease sweeps | None (stateless) |
| Worker process | `fw_worker` | One Chromium, many isolated contexts ("slots"), each with a role: watcher or claimer | None (stateless; sessions live sealed in Postgres) |
| Mock load board | `apps/mockboard` | The fictitious target: login, emailed one-time code, captcha, feed, first-booker-wins booking, adversity switches, ground-truth log | Its own database |
| Console | `apps/dashboard` | Operator UI. Today a static design prototype on mock data; being wired to the API | None |
| API and gateway | `apps/coordinator`, `apps/gateway` | `/v1` REST API with MFA login and roles; server-sent events for live updates | **In progress** |

## How a job is booked

1. **Detect.** A watcher slot keeps the board's own feed page open and listens to the JSON
   responses it fetches (`page.on("response")`), instead of parsing HTML. Each new load becomes a
   detection with a `seen_at` time and is added to the tenant's `detected` stream.
2. **Dispatch.** The cell's dispatcher reads the stream, drops fast-path duplicates (`SET NX` keyed
   by job), checks the tenant's active filters and schedule windows, and creates the claim. The
   claim row and its outbox message are written **in one transaction**, then published to the `act`
   stream right away.
3. **Lease.** A claimer slot with a warm, logged-in page takes the message and leases the claim. The
   lease gets a fresh **fencing token** from a database sequence. One account can hold only one
   active lease (partial unique index).
4. **Act.** The claimer moves the claim to `ACTING` only while its exact lease is current and
   unexpired by the **database clock**, then books: either an HTTP request through the session's
   cookies or a real click on the booking button.
5. **Finish.** The answer becomes `CONFIRMED` or `FAILED`. If the answer is lost (timeout, a 500
   after the booking went through, a crash), the claim becomes `UNKNOWN`.
6. **Reconcile.** The reconciler never retries an `UNKNOWN` claim. It opens the account's sealed
   session, asks the board what the account has booked, and resolves the claim from that answer.

Every step writes a `claim_events` row and a timestamp, which is how per-stage latency is measured.

## Where each guarantee comes from

| Guarantee | Mechanism | Not relied on |
|---|---|---|
| One claim per job | Unique constraint `(tenant_id, target_job_key)` | Redis locks (fast path only) |
| A stale worker cannot act | Fencing token checked in the `UPDATE … WHERE fence = :f` | Worker clocks, worker memory |
| No blind retry after a crash during the action | `ACTING` past expiry → `UNKNOWN` → reconcile against the target | Retries |
| Database and stream never diverge | Transactional outbox + relay | Publishing after commit |
| Tenants cannot see each other | Postgres row-level security, `ENABLE` + `FORCE` on every tenant table | Application `WHERE` clauses alone |
| Secrets at rest | Envelope encryption (AES-256-GCM per record, data key wrapped by a master key, row-bound associated data) | Disk encryption alone |
| A message is never lost when a consumer dies | Redis consumer groups, `XAUTOCLAIM`, dead-letter stream after N deliveries | At-most-once delivery |

## Cells

A **cell** is one Redis plus the workers and control process that serve it. Each tenant belongs to
exactly one cell (`tenant_cells`). Adding capacity means adding a cell and moving tenants — a data
change, not a code change. Redis keys carry a `{tenant}` hash tag so a cell can later be a Redis
Cluster without renaming anything. Moving a tenant between cells during a live run is tested: the
old cell stops publishing for that tenant (an ownership check under `FOR SHARE`), the new cell picks
up queued claims, and no job is booked twice. See [scaling](../scaling/README.md).

## Workers

- One Chromium process per worker, one isolated browser context per slot. Contexts are far cheaper
  than browsers: about 100 MB each in the capacity run.
- Accounts are leased to a slot with a holder lease renewed on every heartbeat, so two workers
  never drive the same account.
- Sessions are restored from the vault (Playwright `storage_state`, sealed per account) and
  refreshed before they expire. One-time codes arrive by email (Mailpit adapter locally) or are
  typed in by an operator.
- Failures leave evidence: a Playwright trace chunk and a screenshot, with a retention period.
- Secrets, cookies and one-time codes are never logged (a test scans the logs).
- A worker can be killed at any time. Its leases expire and are swept by the database rules.

## Data model (main tables)

`tenants`, `cells`, `tenant_cells`, `users`, `user_directory`, `accounts`, `account_sessions`,
`filters`, `schedules`, `target_jobs`, `claims`, `claim_events`, `workers`, `outbox`, `audit_log`.
Every tenant table has `tenant_id` as the leading column of its primary key and indexes, and is
protected by row-level security. Directory tables (`tenants`, `cells`, `tenant_cells`,
`user_directory`) hold no tenant content and are read through a narrow system role.

Database roles: an owner role for migrations, an application role for the API and control
processes, a worker role with column-level grants only, and a separate role for the mock board.

## Technology

Python 3.12 (uv workspace), FastAPI, Pydantic v2 settings, SQLAlchemy 2 (async) + Alembic,
PostgreSQL 18, Redis 8 Streams, Playwright (Chromium), Next.js 16 + React 19 for the console,
Docker Compose for local and single-server runs. Versions are pinned and were checked against their
registries when added.
