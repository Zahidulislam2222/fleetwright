# Coordinator

Fleetwright's authenticated control plane: FastAPI `/v1`, password/TOTP sessions, CSRF, roles,
workflow approvals/grants, audit, freight dispatch/recovery and operational tooling.

| Module | Responsibility |
|---|---|
| `api.py`, `auth.py`, `views.py` | Console sessions, roles, bounded views and atomic mutation/audit records |
| `workflow_api.py` | Owner approval and grant lifecycle; inspection, cancellation, evidence, health and metrics |
| `control.py` | Per-cell freight dispatch, outbox relay, lease sweeps, reconciliation and tenant movement |
| `migrate.py`, `migrations/` | Owner-role schema migrations and RLS; migrations 0002–0007 add workflow, crawler, pacing and durable-detection state |
| `seed.py` | Idempotent configured owner/workspace/destination initialization |
| `crawl_api.py`, `crawls.py`, `crawl_fetch.py`, `crawl_http.py` | Tenant-scoped cycles, fenced frontier, physically bounded HTTP/TLS fetch and private exports |
| `monitor.py`, `monitor_grant.py`, `recovery.py` | Bounded collection, renewable observation grants and authenticated encrypted archive copies |
| `backup.py` | Verified archives, scheduled loop and fresh non-destructive restore drill |

Run `uv run python -m fw_coordinator.api` and `uv run python -m fw_coordinator.control` as separate
services. Migrate before startup. Settings come from `fw_core.settings`; keep secrets outside source.
The API contract is [OpenAPI](../../contracts/openapi.yaml). See [integration reference](../../docs/integrations.md),
[workflow operations](../../docs/operations/reliable-browser.md) and [deployment](../../docs/operations/deployment.md).
Tests live alongside the service and run through `uv run python tools/dev/run_tests.py -q`.

## Process and data boundaries

Run the crawler independently with `uv run python -m fw_coordinator.crawls`. Monitoring uses
`uv run python -m fw_coordinator.monitor once` for a single cycle; `loop` and `report` are separate
subcommands for continuous collection and committed history. API and
crawler instances must share the configured private export directory. Data migrations run with
the owner database role; request handling uses restricted tenant transactions.

A restart does not reset approval consumption, claim fences, pending detections or uncertain
outcomes. Never restore an older backend across the durable-mailbox compatibility boundary.
Review [crawler operations](../../docs/operations/crawler.md), [monitoring](../../docs/operations/monitoring.md)
and [recovery](../../docs/operations/recovery.md) before changing retention or authority.

## Operational acceptance

API readiness, owner authentication and approval authority are separate checks. Validate password/
TOTP, CSRF, role boundaries, bounded audit/evidence reads and revocation over real HTTP. A healthy
API must also report worker readiness truthfully: starting/browserless freight slots stay stale.
Run control, crawler and approved-workflow execution as separate supervised processes.

Before release replacement, stop admission and drain all execution actors while PostgreSQL and the
API remain reachable; account holds and uncertain outcomes stay inspectable. Verify zero legacy
backlog, stop control, and take a validated archive before migration. Repeat owner/MCP/crawler/
export flows after activation. [Service ownership](../../docs/operations/service-ownership.md) and
[data lifecycle](../../docs/security/data-lifecycle.md) assign the corresponding responsibilities.
