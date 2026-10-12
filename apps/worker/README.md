# Worker (`apps/worker`)

A worker process runs **one Chromium with many isolated contexts** ("slots"). Each slot has a role:

- **watcher**: keeps the target's feed page open and listens to its JSON responses; every new
  load becomes a detection on the cell's `detected` stream.
- **claimer**: keeps a warm, logged-in page; takes `act` messages, leases the claim (fencing
  token), moves it to `ACTING` only while the lease is current, books by HTTP (session cookies) or
  by a real click, and records the outcome. A lost answer becomes `UNKNOWN` for the reconciler.

## Modules

| Module | Purpose |
|---|---|
| `runtime.py` | `Fleet` (process-wide: browser, vault, settings, heartbeat, clock-offset measurement, re-planning when the cell's tenants change, memory/CPU meter) and `Slot` (one context: sign-in, session restore and refresh, captcha, evidence, keep-alive) |
| `behaviours.py` | The watcher and claimer behaviours; bounded response reading |
| `accounts.py` | Account holder lease: one worker per account, renewed every heartbeat |
| `otp_manual.py` | One-time codes typed in by an operator |
| `__main__.py` | Entry point; evidence pruning |
| `workflows.py` | Separately supervised approved-workflow runner: fenced account/job holds, authorization recheck, bounded browser action and read-only reconciliation |

## Run

```bash
uv run playwright install chromium
uv run python -m fw_worker          # FW_WORKER__CELL, FW_WORKER__CONTEXTS, FW_WORKER__WATCHERS ...
uv run pytest apps/worker           # real Chromium against a real board
```

The process is stateless. Kill it at any time: leases expire on the database clock and are swept;
sessions are restored from the vault on restart without a new one-time code.

Capacity measured: about 70-103 MB per context, about 1.8 cores at 32 contexts
([capacity model](../../docs/scaling/capacity-model.md)).

Run approved general workflows with `uv run python -m fw_worker.workflows`. These jobs use the
shared account vault and durable PostgreSQL workflow state. UNKNOWN jobs are reconciled using
receipts and never clicked again. Legacy freight slots acquire only freight-capable accounts.
Both owned workflows and an OS-killed worker after destination acceptance have local browser
proof. See the [workflow runbook](../../docs/operations/reliable-browser.md).

Release operation and limits: [deployment](../../docs/operations/deployment.md) · [maintenance](../../docs/maintenance.md).
