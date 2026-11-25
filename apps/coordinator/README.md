# Coordinator

Fleetwright's authenticated control plane: FastAPI `/v1`, password/TOTP sessions, CSRF, roles,
workflow approvals/grants, audit, freight dispatch/recovery, the console help assistant and
operational tooling.

Current release: `20261125-assistant-rc5` (source `26ebe46`), recorded in the
[25 November 2026 release record](../../docs/releases/2026-11-25.md).

| Module | Responsibility |
|---|---|
| `api.py`, `auth.py`, `views.py` | Console sessions, roles, bounded views and atomic mutation/audit records |
| `demo.py` | Workspace controls behind `/v1/demo`: capped runs, feed rate and owned fault presets from `config/demo.yaml`, enforced server-side (file and route names are historical) |
| `assistant.py`, `assistant_api.py`, `assistant_knowledge.py` | Console help assistant: `/v1/assistant` endpoints, keyword retrieval over approved docs, read-only tools, limits and documentation-search fallback |
| `workflow_api.py` | Owner approval and grant lifecycle; inspection, cancellation, evidence, health and metrics |
| `control.py` | Per-cell freight dispatch, outbox relay, lease sweeps, reconciliation and tenant movement |
| `migrate.py`, `migrations/` | Owner-role schema migrations and RLS; migrations 0002–0007 add workflow, crawler, pacing and durable-detection state |
| `seed.py` | Idempotent configured owner/workspace/destination initialization |
| `crawl_api.py`, `crawls.py`, `crawl_fetch.py`, `crawl_http.py` | Tenant-scoped cycles, fenced frontier, physically bounded HTTP/TLS fetch and private exports |
| `monitor.py`, `monitor_grant.py`, `recovery.py` | Bounded collection, renewable observation grants and authenticated encrypted archive copies |
| `backup.py` | Verified archives, scheduled loop and fresh non-destructive restore drill |

## Run and test

Run `uv run python -m fw_coordinator.api` and `uv run python -m fw_coordinator.control` as separate
services. Migrate before startup. Settings come from `fw_core.settings`; keep secrets outside source.
The API contract is [OpenAPI](../../contracts/openapi.yaml). See [integration reference](../../docs/integrations.md),
[workflow operations](../../docs/operations/reliable-browser.md) and [deployment](../../docs/operations/deployment.md).
Tests live alongside the service and run through `uv run python tools/dev/run_tests.py -q`.

## Help assistant (`/v1/assistant`)

An AI that answers questions about Fleetwright from approved public documentation and from
read-only console data the asker can already see. It has no write tools. Design and egress
decision: [ADR 0016](../../docs/adr/0016-assistant-provider-egress.md); user view:
[console guide](../../docs/console-guide.md#the-help-assistant).

| Endpoint | Behavior |
|---|---|
| `GET /v1/assistant` | Disclosure, human contact route, suggested questions and limits. The owner of the public workspace also sees today's deployment-wide counters (no question text exists to show) |
| `POST /v1/assistant/ask` | A question plus bounded history; returns a plain-text answer marked `ai_generated`, with sources, or documentation passages in search mode |
| `POST /v1/assistant/feedback` | One helpful/not-helpful vote per answer id, accepted for a limited time |

- **Access and CSRF.** Signed-in callers send their CSRF token on both POSTs, like every other
  mutation. Guest access to the public workspace (the `public` role) carries no session for a forged
  request to borrow.
- **Roles and tenants.** Eight read-only tools (overview, workers, claims, latency, filters,
  schedules, accounts, public workspace status) call the same views as the console's read
  endpoints, as the asker, inside the asker's tenant transaction with row-level security. No audit
  or user-list tools are exposed. The workspace-status tool answers only for the public workspace.
- **Limits.** Hourly question limits per signed-in user and per guest address range, a per-process
  concurrency limit, and a deployment-wide daily budget reserved atomically in Redis at the
  worst-case price before each provider call and settled to the reported cost afterwards. One
  whole-answer deadline stays below the edge proxy's read timeout. Question, history, prompt,
  tool-result and output sizes are bounded by `FW_ASSISTANT__*` settings.
- **Documentation-search fallback.** When the AI is off, rate limited, busy, over its daily budget
  or too slow, or when the provider fails (or Redis fails for an anonymous visitor; signed-in sessions themselves need Redis), the asker gets the most relevant
  documentation passages instead. The console never depends on the AI being up; the edge proxy's own
  rate limit can still answer 429.
- **Privacy.** Fleetwright does not store question text; logs and counters hold metadata only.
- **Egress.** Only the API container joins the separate `egress` network, and it calls only the
  configured provider endpoint. It never fetches visitor-supplied URLs.

Tests: `test_assistant.py` (API, limits, failures and CSRF with a stand-in provider),
`test_assistant_unit.py` and `test_assistant_browser.py` (real-browser drawer layout). The live
evaluation in `test_assistant_live_eval.py` makes paid model calls and runs only with explicit
opt-in; its cases and thresholds are in [assistant-eval.yaml](../../config/assistant-eval.yaml).
Results for the current release are in the [release record](../../docs/releases/2026-11-25.md).

## Process and data boundaries

Run the crawler independently with `uv run python -m fw_coordinator.crawls`. Monitoring uses
`uv run python -m fw_coordinator.monitor once` for a single cycle; `loop` and `report` are separate
subcommands for continuous collection and committed history. API and
crawler instances must share the configured private export directory. Data migrations run with
the owner database role; request handling uses restricted tenant transactions.

A restart does not reset approval consumption, claim fences, pending detections or uncertain
outcomes. Never restore an older backend across the durable-mailbox compatibility boundary.
Review [crawler operations](../../docs/operations/crawler.md), [monitoring](../../docs/operations/monitoring.md)
and [recovery](../../docs/operations/recovery.md) before changing retention or authority.

## Operational acceptance

API readiness, owner authentication and approval authority are separate checks. Validate password/
TOTP, CSRF, role boundaries, bounded audit/evidence reads and revocation over real HTTP. A healthy
API must also report worker readiness truthfully: starting/browserless freight slots stay stale.
Run control, crawler and approved-workflow execution as separate supervised processes.

Before release replacement, stop admission and drain all execution actors while PostgreSQL and the
API remain reachable; account holds and uncertain outcomes stay inspectable. Verify zero legacy
backlog, stop control, and take a validated archive before migration. Repeat owner/MCP/crawler/
export flows, and an assistant question, after activation. [Service ownership](../../docs/operations/service-ownership.md) and
[data lifecycle](../../docs/security/data-lifecycle.md) assign the corresponding responsibilities.
