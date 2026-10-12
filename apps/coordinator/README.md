# Coordinator

Fleetwright's authenticated control plane: FastAPI `/v1`, password/TOTP sessions, CSRF, roles,
workflow approvals/grants, audit, freight dispatch/recovery and operational tooling.

| Module | Responsibility |
|---|---|
| `api.py`, `auth.py`, `views.py` | Console sessions, roles, bounded views and atomic mutation/audit records |
| `workflow_api.py` | Owner approval and grant lifecycle; inspection, cancellation, evidence, health and metrics |
| `control.py` | Per-cell freight dispatch, outbox relay, lease sweeps, reconciliation and tenant movement |
| `migrate.py`, `migrations/` | Owner-role schema migrations and RLS; workflow migrations 0002–0004 are additive |
| `seed.py` | Idempotent configured owner/workspace/destination initialization |
| `backup.py` | Verified archives, scheduled loop and fresh non-destructive restore drill |

Run `uv run python -m fw_coordinator.api` and `uv run python -m fw_coordinator.control` as separate
services. Migrate before startup. Settings come from `fw_core.settings`; keep secrets outside source.
The API contract is [OpenAPI](../../contracts/openapi.yaml). See [integration reference](../../docs/integrations.md),
[workflow operations](../../docs/operations/reliable-browser.md) and [deployment](../../docs/operations/deployment.md).
Tests live alongside the service and run through `uv run python tools/dev/run_tests.py -q`.
