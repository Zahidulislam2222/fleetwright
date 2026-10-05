# Coordinator (`apps/coordinator`)

The control plane's server side.

## Today

| Module | Purpose |
|---|---|
| `migrate.py` + `migrations/` | Schema, database roles and row-level security. Run with `uv run python -m fw_coordinator.migrate` (uses the owner role) |
| `control.py` | One **control process per cell**: dispatcher (filters, schedules, fast-path duplicate drop, claim + outbox in one transaction), outbox relay (with a cell-ownership check), reconciler (lease sweeps; resolves `UNKNOWN` claims by asking the target with the account's sealed session), and `move_tenant` for moving a tenant between cells |

```bash
uv run python -m fw_coordinator.control     # cell from FW_CONTROL__CELL
uv run pytest apps/coordinator
```

## In progress

The `/v1` REST API for the console: sign-in with password and TOTP, roles, CSRF protection, an
anonymous read-only demo view, filters and schedules management, manual one-time-code entry and
capped demo controls. See the [roadmap](../../docs/roadmap.md).
