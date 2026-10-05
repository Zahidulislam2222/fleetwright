# Local development

## Requirements

| Tool | Version | Why |
|---|---|---|
| [uv](https://docs.astral.sh/uv/) | current | Python 3.12 workspace and lock file |
| Docker with Compose | current | Postgres, Redis (core + two cells), Mailpit |
| Node.js | 24 | Console (`apps/dashboard`) only |

## First run

```bash
uv sync                                         # install every workspace package (Python 3.12)
uv run playwright install chromium              # browser used by workers and browser tests
uv run python tools/dev/make_env.py             # writes .env from .env.example with fresh secrets
docker compose -f infra/compose/local.yaml --env-file .env up -d --wait
uv run python -m fw_coordinator.migrate         # schema, database roles, row-level security
```

`make_env.py` refuses to overwrite an existing `.env` and never prints secret values. All service
ports are bound to `127.0.0.1`.

## Running the services by hand

Each command reads `.env` from the working directory (the repository root).

```bash
# the fictitious load board (port from FWDEV_BOARD_PORT, 8100 by default)
uv run uvicorn --factory mockboard.app:create_app --host 127.0.0.1 --port 8100

# control loops for one cell: dispatcher, outbox relay, reconciler (cell from FW_CONTROL__CELL)
uv run python -m fw_coordinator.control

# a worker process: one Chromium with FW_WORKER__CONTEXTS slots (cell from FW_WORKER__CELL)
uv run python -m fw_worker

# the console (design prototype on mock data)
cd apps/dashboard && npm ci && npm run dev
```

Mailpit's web UI (emailed one-time codes) listens on the port set by `FWDEV_MAILPIT_PORT` in
`.env`.

**Today, a full end-to-end run with a tenant, accounts and filters is driven by the test suite**
(`apps/worker/tests/test_engine.py`), which creates its own tenant and board accounts. A seed
command and the console API that make this a click-through demo are in progress
([roadmap](../roadmap.md)).

## Tests

```bash
uv run pytest                          # everything, including the ~6 minute 200×10,000 load test
uv run pytest -m "not slow"            # skip the load test
uv run pytest apps/worker              # real Chromium against a real board
uv run pytest packages/fw_core/tests/test_rls.py
```

Test markers: `integration` (needs the Compose stack), `browser` (launches Chromium), `slow`
(load or chaos). See [testing and evidence](../testing.md).

## Quality gates

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy                             # strict, on every service and package
cd apps/dashboard && npm run lint && npm run typecheck && npm run build
```

A local hook also runs gitleaks and bandit on every edited file; commits run gitleaks, bandit and
semgrep. Findings are fixed, never suppressed.

## Resetting

```bash
docker compose -f infra/compose/local.yaml --env-file .env down -v   # deletes local data volumes
```
