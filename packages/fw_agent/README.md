# Standalone local browser agent

`python -m fw_agent` starts the local UI and SQLite application. It needs Python, installed Playwright
Chromium and an installed local Ollama model. PostgreSQL, Redis, Docker and paid APIs are not runtime
requirements. Configuration belongs to `fw_core.settings.AgentAppSettings`; maintained templates,
prompts and UI copy belong to `config/agent.yaml`.

The model drafts plain text only. The human sees the exact destination and draft, then authorizes
one hash-bound save. A failed acknowledgement becomes `UNKNOWN`; receipt reconciliation can
confirm it, but cannot repeat it. Three owned lab workflows cover maintenance, dispatch handover
and inspection summaries. They save owned local records and send no emails or purchases.

See [operations and security contract](../../docs/operations/local-agent.md).

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
