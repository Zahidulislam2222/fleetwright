# fw_core

Shared core used by every service.

| Module | Purpose |
|---|---|
| `settings.py` | The single typed configuration boundary (Pydantic settings, `FW_` variables), including `AssistantSettings` and `BoardSettings` |
| `db.py` | Async engines and tenant / system transactions (`SET LOCAL app.tenant_id` for row-level security) |
| `detections.py` | PostgreSQL raw-detection mailbox, redelivery and atomic tenant/cell handover |
| `claims.py` | The claim state machine: unique claim per job, fencing tokens, database-clock leases, sweeps, reconciliation |
| `workflow_contracts.py` | Validated versioned contracts and deterministic fingerprints from `config/workflows.yaml` |
| `workflows.py` | Durable jobs, tenant-scoped grants, exact approvals, fencing, safe cancellation, fair recovery and bounded evidence |
| `workflow_health.py` | Tenant-scoped workflow health, alerts and metrics |
| `crypto.py` | Envelope encryption (AES-256-GCM per record, wrapped data keys, row-bound associated data) |
| `vault.py` | Sealed target credentials and browser sessions; refresh timing |
| `targets.py` | Validated target-site definitions from `config/targets.yaml` |
| `filters.py` | Filters and time-zone-aware schedule windows (including overnight windows) |
| `latency.py` | Per-stage p50/p95/p99 from claim timestamps |
| `logs.py`, `timeutil.py`, `data.py` | Structured logging, time helpers, YAML data loading |

Tests: `uv run python -m pytest packages/fw_core` (row-level security, claims including the 200 x 10,000 load
test, filters, settings, configuration boundary).

General workflows keep uncertain outcomes UNKNOWN until matching destination evidence resolves
them. They never blindly repeat an uncertain action. See the
[workflow runbook](../../docs/operations/reliable-browser.md) for local verification and limits.

Release operation and limits: [deployment](../../docs/operations/deployment.md) · [maintenance](../../docs/maintenance.md).

Current release: `20261125-assistant-rc5` ([25 November 2026 record](../../docs/releases/2026-11-25.md)).
That release added the settings below; claims, workflows, crypto and the vault are unchanged.

## Help assistant and freight exchange settings

`AssistantSettings` (`FW_ASSISTANT__*`) configures the console help assistant. It is off by
default (`FW_ASSISTANT__ENABLED=false`); while off, the console answers from documentation search
only. When enabled, the provider URL, API key, model id and both per-million-token prices must be
set: there are no defaults for them, prices must be positive, and the service refuses to start if
any is missing. The remaining fields bound spend and abuse:

| Group | Settings |
|---|---|
| Spend | `daily_budget_usd` (deployment-wide, reserved before each call), `price_input_per_mtok_usd`, `price_output_per_mtok_usd`, `tokenizer_char_ratio` (conservative estimate so reservations over-cover) |
| Time | `timeout_s` per provider call, `total_deadline_s` per answer (at most 28 s, below the edge proxy's 30 s read timeout); start-up fails if the call timeout exceeds the answer deadline |
| Abuse | `public_per_hour` (guests, per address range), `user_per_hour` (signed-in users), `rate_window_s`, `concurrency` and `slot_wait_s` per API process |
| Size | `max_steps`, `max_tool_calls`, `max_output_tokens`, `max_prompt_chars`, `max_question_chars`, `max_history_turns`, `max_history_chars`, `tool_result_max_chars`, `tool_list_limit`, `tool_claims_limit`, `retrieval_top_k`, `excerpt_chars` |
| Provider and data | `deny_data_collection` (asks the router to use only providers that do not train on prompts), `openrouter_extensions`, `temperature`, `docs_base_url` for source links, `feedback_ttl_s`, `stats_retention_days` |

The API key is a secret (`SecretStr`) and belongs only in the private environment. Values in
[.env.example](../../.env.example) are safe defaults, not the deployed budget; the current
deployment's provider, model, prices and daily budget are recorded in the
[release record](../../docs/releases/2026-11-25.md) and
[ADR 0016](../../docs/adr/0016-assistant-provider-egress.md).

`BoardSettings` (`FW_BOARD__*`) configures the owned freight exchange served by `apps/mockboard`.
`console_url` (`FW_BOARD__CONSOLE_URL`) is the console address the exchange's visitor guide shows
as text; it must be an http(s) address, and the line is hidden when unset.

## Authority contract

Redis receipt, lock expiry and worker clocks never replace database authority. Claims, workflow
jobs, account pacing and tenant moves use current database-clock ownership. Uncertainty is a
persisted state, not permission to retry. Keep canonical wire/state definitions stable; environment
choices enter through typed settings and maintained destination data is validated before use.

The generated [settings schema](../../contracts/settings.json) and [environment template](../../.env.example)
are checked for drift. Schema changes require migrations, tenant isolation tests and a reviewed
compatibility plan; see [architecture](../../docs/architecture/overview.md) and
[release safety](../../docs/operations/deployment.md).

## Changes that require coordinated release review

A state, tenant predicate, approval fingerprint, pacing rule or encrypted record format affects
multiple processes. Review every caller and migration, then exercise contention, stale fences,
revoked grants and interrupted acceptance against authoritative destination receipts. Preserve
historical uncertain work rather than rewriting it into success.

Configuration changes must update typed settings, safe environment templates and generated
contracts together. Secrets and operational account values stay outside public source. Use
[data lifecycle](../../docs/security/data-lifecycle.md),
[component ownership](../../docs/operations/service-ownership.md) and
[scale promotion](../../docs/scaling/validation-plan.md) when expanding the shared core.
