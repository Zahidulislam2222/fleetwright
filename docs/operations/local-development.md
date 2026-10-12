# Local development

Requirements: Python 3.12, uv, Docker Compose, Node.js 24 and Playwright Chromium. Ports and
secrets are configured through the root environment template. Do not reuse production credentials.

```bash
uv sync --frozen
uv run playwright install chromium
uv run python tools/dev/make_env.py
docker compose -f infra/compose/local.yaml --env-file .env up -d --wait
uv run python -m fw_coordinator.migrate
uv run python -m fw_coordinator.seed
```

The environment generator refuses an existing file and does not print secrets. The seed uses
configured private owner identity/TOTP and destination settings. Keep those values private.

Start these processes from the repository root in separate terminals:

```bash
uv run uvicorn --factory mockboard.app:create_app --host 127.0.0.1 --port 8100
uv run python -m fw_coordinator.api
uv run python -m fw_gateway
uv run python -m fw_coordinator.control
uv run python -m fw_worker
uv run python -m fw_worker.workflows
```

The board bind port above must match `FWDEV_BOARD_PORT` / the client URL if changed. API and gateway
bind values come from typed settings. Local Mailpit handles destination email codes; it is not a
production outbound mail service. The approved-workflow runner is distinct from the freight fleet.

From `apps/dashboard`, run `npm ci` then `npm run dev`. The development proxy forwards `/v1` to the
configured local API/gateway. The console detects live sessions; an absent API selects explicit
offline reference mode. The `/agent` interface remains local planned interaction data. Configure
real MCP clients using [the workflow runbook](reliable-browser.md).

## Verification

```bash
uv run python tools/dev/run_tests.py -q
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

The harness creates isolated test databases, serializes suite runs and propagates test settings to
child workers. It refuses non-local databases. Browser console tests require a built dashboard.
Frontend gates: `npm run lint`, `npm run typecheck`, `npm run build` and `npm run check:contrast`.
See [testing](../testing.md). Stop the local Compose project with `down` while retaining volumes;
volume deletion is a separate destructive operation, never a routine cleanup or deployment step.
