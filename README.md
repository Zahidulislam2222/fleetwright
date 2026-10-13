# Fleetwright — Reliable Browser Operations

Fleetwright coordinates authorized browser workflows with durable execution, exact-action human
approval, scoped MCP access, recovery and verifiable evidence. Claude and Codex can supervise jobs;
Playwright workers execute approved actions. An interrupted action stays `UNKNOWN` until a matching
destination receipt resolves it. Destinations without sufficient evidence require operator review.

**[Open Fleetwright](https://fleetwright.zahidul-islam.com)** ·
**[Documentation](docs/README.md)** · **[MCP setup](docs/operations/reliable-browser.md)**

Latest deployment: [13 October 2026 release evidence](docs/releases/2026-10-13.md).

## What is included

- Two complete owned workflows: freight booking and maintenance-request creation.
- PostgreSQL fencing tokens, database-clock leases, tenant isolation and transactional audit.
- Human approval bound to tenant, account, inputs and the complete versioned workflow contract.
- Revocable MCP grants separating observation from execution; six bounded tools for supervision.
- Owner console review, cancellation, failure investigation and paginated evidence export.
- Warm browser sessions, encrypted account vault, receipt reconciliation and interrupted-worker recovery.
- Authenticated workflow health/metrics, verified database archives and non-destructive restore tooling.
- Durable catalogue crawling with pinned HTTP egress, JSON/CSS extraction, quality alerts and private JSONL export.
- Standalone SQLite/Ollama browser app with exact approvals, receipts, bounded tabs and three owned task templates.
- Renewable observation-only monitoring, free independent public probes and encrypted off-host recovery tooling.

The public workspace offers read-only inspection and a limited shared login for capped freight
runs. Owner credentials and approvals are private. The destinations are owned verification systems;
no commercial freight marketplace or third-party website is operated by this repository.
The separate `/agent` page links to the app running on your own computer. See the
[local agent guide](docs/operations/local-agent.md); the hosted console does not control your local browser.

## Verified behavior and limits

| Verification | Result and boundary |
|---|---|
| Combined backend suite, 2026-10-13 | 147 tests passed in the final run; the contention benchmark passed separately in 205.19 seconds |
| Database contention | 200 competitors, 10,000 jobs, zero duplicate action attempts; 9,895 confirmed/reconciled bookings |
| Interrupted action | Real Chromium worker killed after destination acceptance; receipt reconciliation without another click |
| Authorization | Changed, expired and replayed approval rejected; tenant isolation and grant revocation tested |
| Client integration | Actual Codex submission, inspection and evidence export for both workflows; Claude client run deferred while its subscription is inactive |
| Historical browser capacity | 8/16/32 contexts measured on one developer machine; roughly 70–103 MB per context |
| Historical freight latency | Detection to confirmation p50 about 365 ms, p95 about 540 ms on the owned board |

These results establish behavior within the tested workloads. The current deployment is one server;
the [1M+ simultaneous-user design](docs/scaling/README.md) and [99% / 99.9% availability objectives](docs/scaling/slo.md)
have explicit future validation gates. There is no arbitrary-website exactly-once guarantee.
The full npm audit retains an unpatched development-only `braces` advisory; the production audit
is clean. See [maintenance](docs/maintenance.md) and [verification](docs/testing.md).

## Run locally

Requirements: Python 3.12, uv, Docker Compose and Node.js 24. Use the locked workspace:

```bash
uv sync --frozen
uv run playwright install chromium
uv run python tools/dev/make_env.py
docker compose -f infra/compose/local.yaml --env-file .env up -d --wait
uv run python -m fw_coordinator.migrate
```

Continue with [local development](docs/operations/local-development.md) for service startup,
private accounts and the dashboard. For MCP, issue a scoped owner grant, run
`uv run python -m fw_mcp.server` from the workspace and supervise
`uv run python -m fw_worker.workflows` separately. Never place tokens in client configuration or prompts.

## Repository map

| Path | Responsibility |
|---|---|
| `apps/coordinator` | Authenticated API, approvals, dispatch/recovery, migrations and backups |
| `apps/worker` | Freight fleet and separately supervised approved-workflow runner |
| `apps/dashboard` | Public site and authenticated operator console |
| `apps/gateway` | Authorized server-sent updates with idle revocation checks |
| `apps/mockboard` | Owned freight exchange and maintenance portal |
| `packages/fw_core` | Settings, contracts, claims, workflows and database boundaries |
| `packages/fw_browser` | Browser authentication and owned destination adapters |
| `packages/fw_queue` | Tenant-scoped queues and transactional outbox |
| `packages/fw_mcp` | Official FastMCP stdio integration |
| `packages/fw_agent` | Standalone local SQLite/Ollama browser application |
| `config`, `contracts`, `deploy` | Validated product data, OpenAPI and immutable release templates |

## Verification and contribution

Run `uv run python tools/dev/run_tests.py -q` against the isolated development stack. Python gates
are Ruff, mypy and package builds; frontend gates are ESLint, TypeScript and the production build.
Gitleaks, Bandit and Semgrep scan public source. See [testing](docs/testing.md),
[contributing](CONTRIBUTING.md), [security reporting](SECURITY.md) and the [roadmap](docs/roadmap.md).

The repository's [license](LICENSE) permits source inspection and local evaluation. Commercial or
production use requires written permission. Deployment operators must review [acceptable use](docs/legal/acceptable-use.md),
[privacy](docs/legal/privacy.md) and destination authorization before onboarding a workflow.
