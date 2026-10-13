# Fleetwright — Reliable Browser Operations

Fleetwright coordinates authorized browser work through durable ownership, exact-action approval
and destination evidence. It combines a warm browser fleet, scoped MCP supervision, catalogue
crawling and a separate local model-assisted browser application.

**[Open Fleetwright](https://fleetwright.zahidul-islam.com)** ·
**[Documentation](docs/README.md)** · **[Installation](docs/operations/local-development.md)** ·
**[API and MCP](docs/integrations.md)**

## Capabilities

| Capability | Included behavior |
|---|---|
| Coordinated browser fleet | Watcher/actor separation, warm sessions, fenced claims, database-clock account pacing, filters, schedules and execution cells |
| Approved workflows | Freight booking and maintenance requests; owner approval binds tenant, account, inputs and the full versioned contract |
| MCP supervision | Six bounded stdio tools with separate observe/execute grants, expiry and immediate revocation checks |
| Catalogue crawler | Durable frontier, same-origin definitions, pinned HTTP/TLS egress, JSON/CSS extraction, quality alarms, retention and private JSONL export |
| Local browser agent | SQLite and installed Ollama model, three maintained form workflows, exact approvals, receipts, cancellation and isolated optional CDP |
| Operations | Authenticated metrics, renewable observe-only collection, independent public probes, verified archives and encrypted off-host recovery |
| Release assurance | Immutable source/artifact inventory, final-image SBOM/scans, offline signatures, rehearsal, compatibility-aware rollback and hash parity |

The console separates private owner authority from public read-only access and capped shared
workspace controls. Its freight exchange and maintenance portal are owned destinations with
independent receipt records. A new customer destination requires explicit authorization, a reviewed
contract and its own behavioral evidence. The hosted agent page links to an application on your
computer; it does not control your browser remotely.

## Evidence and current boundary

The most recent exact local rehearsal is `20261013-free-local-rc2`, built from source `847bcd40`.
Final completion integration includes all-worker shutdown-grace checks and updated documentation.
Deployment status and final verification are maintained in the
[release record](docs/releases/2026-10-13.md).

| Evidence | Verified result and scope |
|---|---|
| Full backend regression | 260 passed / 6 expected skips; subsequent local-agent UI correction separately passed 25 tests / 5 expected skips |
| Actual browser/model flows | Both approved MCP workflows and three installed-model local-agent templates confirmed with matching receipts |
| Exact release UI | Native owner login, fleet confirmation, crawler completion/export, public authorization denial, SPA navigation and responsive layouts passed with zero observed CSP violations/page errors |
| Browser endurance | Separate 50- and 70-context owned-fixture runs exceeded one hour with zero errors; these are fixture endurance results |
| Contention | 200 coordination competitors and 10,000 jobs with zero duplicate action attempts; competitors are not 200 browsers |
| Image assurance | Final native application and web image scans reported zero HIGH/CRITICAL findings at the recorded scan |
| Recovery | Encrypted independent archive restored into fresh local databases with table row parity |

Historical owned-board latency was approximately 365 ms p50 / 540 ms p95 from detection to
confirmation. Workload, hardware and limits belong with every measurement:
[testing](docs/testing.md) and [capacity evidence](docs/scaling/verification-2026-10-13.md).
The deployment has a single-host failure domain. [1M+ simultaneous control-plane users](docs/scaling/README.md)
and [99% / 99.9% availability objectives](docs/scaling/slo.md) are future design and validation
targets. Arbitrary-site exactly-once execution and measured monthly availability are not established.

## Install and run

Use Python 3.12, uv, Docker Compose and Node.js 24 for the full workspace:

```bash
uv sync --frozen
uv run playwright install chromium
uv run python tools/dev/make_env.py
docker compose -f infra/compose/local.yaml --env-file .env up -d --wait
uv run python -m fw_coordinator.migrate
```

Continue with [local development](docs/operations/local-development.md) to start the owned destination,
seed accounts, then start the API, gateway, control loop and workers. Run the dashboard from
`apps/dashboard`. Use separate local
credentials and preserve existing data volumes.

For the standalone agent, follow the [local-agent guide](docs/operations/local-agent.md).
It needs SQLite, Playwright Chromium and an installed local Ollama model; PostgreSQL, Redis,
Docker and paid model APIs are not runtime requirements.

## Integration and operating contract

Environment-specific settings have one typed boundary:
[`fw_core.settings`](packages/fw_core/src/fw_core/settings.py), documented in
[configuration](docs/operations/configuration.md) and [`.env.example`](.env.example).
Maintained destination contracts, prompts and product data live in `config/`; secrets stay private.

MCP clients submit proposals and inspect evidence. They cannot grant themselves authority or approve
their own work. Owners review exact proposals in the console. A changed, expired, revoked or consumed
approval cannot authorize an action. Interrupted actions remain `UNKNOWN` until matching receipts
resolve them; redeployment, cancellation and a missing response do not undo a destination action.

Before onboarding, review [product scope](docs/product.md), [acceptable use](docs/legal/acceptable-use.md),
[privacy](docs/legal/privacy.md), [security controls](docs/security/controls.md) and the [license](LICENSE).
Operational support, commercial terms and service-level commitments require a separate agreement.

## Repository and maintenance

| Directory | Owner responsibility |
|---|---|
| `apps/coordinator` | API/authentication, approvals, dispatch/recovery, crawler, migrations and operational CLIs |
| `apps/worker` | Freight fleet and separately supervised approved-workflow runner |
| `apps/dashboard`, `apps/gateway` | Operator interface and authorized server-sent updates |
| `apps/mockboard` | Owned destination applications and independent receipts |
| `packages/fw_core`, `packages/fw_queue`, `packages/fw_browser` | Durable authority, messaging and browser adapters |
| `packages/fw_mcp`, `packages/fw_agent` | Scoped MCP supervision and standalone local app |
| `config`, `contracts`, `deploy` | Validated data, generated schemas and immutable release inputs |
| `tools/security`, `infra/terraform` | Local assurance tooling and unprovisioned AWS reference |

Use [testing](docs/testing.md), [maintenance](docs/maintenance.md) and [runbooks](docs/operations/runbooks.md)
for release gates and incident handling. Contribution guidance is in [CONTRIBUTING.md](CONTRIBUTING.md);
report sensitive findings privately through [SECURITY.md](SECURITY.md). Future work and promotion
criteria are in the [roadmap](docs/roadmap.md). Dependency and scanner findings remain disclosed
rather than suppressed.
