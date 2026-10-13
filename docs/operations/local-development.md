# Local installation and development

The full fleet requires Python 3.12, uv, Docker Compose, Node.js 24 and Playwright Chromium.
The standalone local agent has a separate SQLite-only runtime described below. Use the committed
lockfiles and separate local credentials; production accounts and keys do not belong in development.

## Prepare data services

Run from the repository root:

```bash
uv sync --frozen
uv run playwright install chromium
uv run python tools/dev/make_env.py
docker compose -f infra/compose/local.yaml --env-file .env up -d --wait
uv run python -m fw_coordinator.migrate
```

The generator refuses to overwrite an existing environment and does not print generated secrets.
For an existing checkout, review new variables and use `make_env.py --sync` to add missing settings
while preserving current values. Review [.env.example](../../.env.example) and
[configuration ownership](configuration.md) before startup.

## Start the owned destination, then seed

In a separate terminal, start the destination before running the seed: seeding calls its protected
administration API to provision destination accounts and presets.

```bash
uv run uvicorn --factory mockboard.app:create_app --host 127.0.0.1 --port 8100
```

This is the safe local bind example. If its configured client port changes, adapt the bind command
to match. With the destination available, run:

```bash
uv run python -m fw_coordinator.seed
```

The seed creates configured private owner/TOTP access, a restricted shared workspace user, account
groups, filters and schedules. Actual credentials stay in the ignored environment/recovery inventory.

## Start independent service processes

Use separate terminals from the repository root:

```bash
uv run python -m fw_coordinator.api
uv run python -m fw_gateway
uv run python -m fw_coordinator.control
uv run python -m fw_worker
uv run python -m fw_worker.workflows
uv run python -m fw_coordinator.crawls
```

The API/gateway bind addresses come from typed settings. The control process handles freight
dispatch/reconciliation; the freight worker, approved-workflow runner and catalogue crawler have
separate process lifecycles. Keep workflow-reserved account groups excluded from long-lived freight
slots. API/crawler processes share the configured private export directory.

From `apps/dashboard`, run `npm ci` and `npm run dev`. Its development proxy forwards same-origin
`/v1` traffic to the configured API/gateway. API absence selects explicitly labelled offline
reference data. Local Mailpit supports owned destination email-code testing; it is not an outbound
customer mail service.

## Local agent and MCP

Start the local model service with an already installed model, configure `FW_AGENT__*`, then run
`uv run python -m fw_agent`. PostgreSQL, Redis and Docker are not required for this standalone
runtime. See [local-agent installation and boundaries](local-agent.md).

For MCP, an owner first issues a scoped grant. Run `uv run python -m fw_mcp.server` in the workspace;
keep the separately supervised workflow worker available. Follow [client setup](reliable-browser.md)
and never put access tokens into prompts or committed client configuration.

## Verify and stop

```bash
uv run python tools/dev/run_tests.py -q
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

The test harness serializes database/browser suites and refuses non-local test databases. It applies
migrations and propagates isolated settings to child workers. Build the dashboard before console
browser tests. In `apps/dashboard`, run `npx next typegen` before a clean standalone type check,
then `npm run lint`, `npm run typecheck`, `npm run build` and `npm run check:contrast`.
See [testing](../testing.md) and the [Next.js CLI reference](https://nextjs.org/docs/app/api-reference/cli/next#next-typegen-options).

For planned shutdown, gracefully stop every browser worker before data services. Preserve volumes;
`docker compose down` without volume deletion stops the local data stack. Removing volumes is a
separate destructive operation. Interrupted actions retain UNKNOWN state and require receipt review.
