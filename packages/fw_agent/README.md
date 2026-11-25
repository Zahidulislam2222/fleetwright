# Standalone local browser agent

`python -m fw_agent` starts the local UI and SQLite application. It needs Python, installed Playwright
Chromium and an installed local Ollama model. PostgreSQL, Redis, Docker and paid APIs are not runtime
requirements. Configuration belongs to `fw_core.settings.AgentAppSettings`; maintained templates,
prompts and UI copy belong to `config/agent.yaml`.

This agent is separate from the console help assistant: it runs a local model on the user's device
and drafts form content for approval, while the help assistant answers questions in the hosted
console and has no write tools.

Current release: `20261125-publication-rc1` (application code from the assistant release `20261125-assistant-rc5`) ([25 November 2026 record](../../docs/releases/2026-11-25.md)).
That release added machine-readable AI provenance, described below.

## What it does

The model drafts plain text only. The human sees the exact destination and draft, then authorizes
one hash-bound save. A failed acknowledgement becomes `UNKNOWN`; receipt reconciliation can
confirm it, but cannot repeat it. Three owned lab workflows cover maintenance, dispatch handover
and inspection summaries. They save owned local records and send no emails or purchases.

See [operations and security contract](../../docs/operations/local-agent.md).

## AI provenance in the approval fingerprint

Every model-drafted proposal records `provenance: {ai_generated: true, model: <model id>}`. When a
person edits the draft, the replacement proposal keeps that record and adds `human_edited: true`.
The review page shows the matching label from `config/agent.yaml` ("AI-generated draft from the
local model", plus "Edited by a person after generation" when applicable).

Provenance is part of the proposal that the approval fingerprint covers, together with the origin,
template, request, source and draft. If any of them changes after the approval hash is issued, the
approval is refused, so the AI marking cannot be stripped without a fresh human approval.
`tests/test_authority.py` checks each of these six components.

## Install and recover

From the root workspace, run `uv sync --frozen` and `uv run playwright install chromium`. Configure
the `FW_AGENT__*` group from the safe environment template, start the installed local model service,
then run `uv run python -m fw_agent`. The application refuses non-loopback model/API/CDP addresses,
cloud-backed model metadata and models missing from local inventory.

Dedicated profiles are the default. Optional CDP creates an isolated context and preserves owner
tabs without inheriting their login. HTTP/WebSocket controls do not constitute an OS hostile-site
sandbox. POSIX state is restricted to private permissions; Windows privacy depends on directory ACLs.
After interruption, keep SQLite/profile data and reconcile UNKNOWN receipts without repeating the
save. Native UI edits survive blur/refresh/polling and require a fresh hash before approval.

## Local ownership and acceptance record

The device owner controls the installed model, task database, profile and destination allowlist.
Verify model inventory locally and inspect the exact proposed form fields before approving one
save. A changed draft requires a fresh approval fingerprint; cancellation preserves any accepted
or uncertain outcome and its receipt history.

The operational check uses the native local interface, edited text surviving blur/refresh,
proposal approval, exact destination receipt, bounded stop and retained SQLite/profile state.
Document the actual model and workload in a dated private verification record. Follow
[data handling](../../docs/security/data-lifecycle.md) and
[customer readiness](../../docs/legal/commercial-readiness.md) for additional integrations.
