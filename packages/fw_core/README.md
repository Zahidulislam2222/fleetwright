# fw_core

Shared core used by every service.

| Module | Purpose |
|---|---|
| `settings.py` | The single typed configuration boundary (Pydantic settings, `FW_` variables) |
| `db.py` | Async engines and tenant / system transactions (`SET LOCAL app.tenant_id` for row-level security) |
| `claims.py` | The claim state machine: unique claim per job, fencing tokens, database-clock leases, sweeps, reconciliation |
| `workflow_contracts.py` | Validated versioned contracts and deterministic fingerprints from `config/workflows.yaml` |
| `workflows.py` | Durable jobs, tenant-scoped grants, exact approvals, fencing, safe cancellation, fair recovery and bounded evidence |
| `workflow_health.py` | Tenant-scoped workflow health, alerts and metrics |
| `crypto.py` | Envelope encryption (AES-256-GCM per record, wrapped data keys, row-bound associated data) |
| `vault.py` | Sealed target credentials and browser sessions; refresh timing |
| `targets.py` | Validated target-site definitions from `config/targets.yaml` |
| `filters.py` | Filters and time-zone-aware schedule windows (including overnight windows) |
| `latency.py` | Per-stage p50/p95/p99 from claim timestamps |
| `logs.py`, `timeutil.py`, `data.py` | Structured logging, time helpers, YAML data loading |

Tests: `uv run pytest packages/fw_core` (row-level security, claims including the 200 x 10,000 load
test, filters, settings, configuration boundary).

General workflows keep uncertain outcomes UNKNOWN until matching destination evidence resolves
them. They never blindly repeat an uncertain action. See the
[workflow runbook](../../docs/operations/reliable-browser.md) for local verification and limits.

Release operation and limits: [deployment](../../docs/operations/deployment.md) · [maintenance](../../docs/maintenance.md).
