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

The deployed frontend/backend release is `20261015-publication-rc1`, built from source `cd64e6b`.
Exact rehearsal, native server image checks, independent artifact review, public workflows,
operator UI and HTTP checks passed. All 146 deployed manifest entries and eight application/web
service-role image identities matched the signed release. Verification is maintained in the
[release record](docs/releases/2026-10-15.md).

| Evidence | Verified result and scope |
|---|---|
| Full backend regression | 289 passed / 6 accounted skips in 714.96 seconds; native exit0, zero failures/errors and 363 runtime/configuration/build-prerequisite hashes unchanged |
| Browser/model flows | Current public MCP workflows confirmed with matching receipts; three installed-model local-agent templates retain their 13 October proof |
| Exact release UI | Native owner login, fleet confirmation, crawler completion/export, public authorization denial, SPA navigation and responsive layouts passed with zero observed CSP violations/page errors |
| Browser endurance | Separate 50- and 70-context owned-fixture runs exceeded one hour with zero errors; these are fixture endurance results |
| Contention | 200 coordination competitors and 10,000 jobs with zero duplicate action attempts; competitors are not 200 browsers |
| Image assurance | Final native application and web image scans reported zero HIGH/CRITICAL findings at the recorded scan |
| Browser recovery | Exact local driver and browser loss each caused one supervisor restart; four ready slots returned within 10.3 seconds; strict drain released all holds and exited 0 |
| Recovery | Current post-activity archive restored into two new verification databases; backup/monitor supervisor recovery passed. Independent encrypted recovery remains the separately dated 13 October proof |

Release source `cd64e6b` updates public documentation and the central distinct web-image tag;
business runtime behavior is unchanged from the 14 October browser-supervision correction.
The final complete suite ran after local builds/rehearsal finished, with its generated dashboard
prerequisite frozen alongside runtime/configuration. Driver-loss supervision and readiness prevent
a browserless process appearing healthy. Earlier failed verification attempts remain in the release record.

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

## Product delivery and operating ownership

Public documentation is maintained across the complete workspace. Start with the
[documentation index](docs/README.md), then use [service ownership](docs/operations/service-ownership.md)
to map each process to its startup, authority, health and recovery responsibilities.
[Data lifecycle](docs/security/data-lifecycle.md) covers records, evidence, exports and archives;
[commercial readiness](docs/legal/commercial-readiness.md) defines destination permission,
licensing, privacy, support and release acceptance before customer onboarding.

The future design targets **1M+ simultaneous authorized console users**, with a **99% initial
operating objective** and **99.9% multi-zone objective**. The
[validation plan](docs/scaling/validation-plan.md) specifies tiered workload, resource, failure,
recovery and error-budget gates. Execution cells retain separate destination/account budgets.
Current measurements stay in dated release records. Source, signed artifacts, runtime behavior,
operational recovery and public publication are verified as separate delivery gates.
