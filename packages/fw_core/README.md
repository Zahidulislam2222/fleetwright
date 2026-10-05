# fw_core

Shared core used by every service.

| Module | Purpose |
|---|---|
| `settings.py` | The single typed configuration boundary (Pydantic settings, `FW_` variables) |
| `db.py` | Async engines and tenant / system transactions (`SET LOCAL app.tenant_id` for row-level security) |
| `claims.py` | The claim state machine: unique claim per job, fencing tokens, database-clock leases, sweeps, reconciliation |
| `crypto.py` | Envelope encryption (AES-256-GCM per record, wrapped data keys, row-bound associated data) |
| `vault.py` | Sealed target credentials and browser sessions; refresh timing |
| `targets.py` | Validated target-site definitions from `config/targets.yaml` |
| `filters.py` | Filters and time-zone-aware schedule windows (including overnight windows) |
| `latency.py` | Per-stage p50/p95/p99 from claim timestamps |
| `logs.py`, `timeutil.py`, `data.py` | Structured logging, time helpers, YAML data loading |

Tests: `uv run pytest packages/fw_core` (row-level security, claims including the 200 x 10,000 load
test, filters, settings, configuration boundary).
