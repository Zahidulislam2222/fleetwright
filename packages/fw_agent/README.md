# Standalone local browser agent

`python -m fw_agent` starts the local UI and SQLite application. It needs Python, installed Playwright
Chromium and an installed local Ollama model. PostgreSQL, Redis, Docker and paid APIs are not runtime
requirements. Configuration belongs to `fw_core.settings.AgentAppSettings`; maintained templates,
prompts and UI copy belong to `config/agent.yaml`.

The model drafts plain text only. The human sees the exact destination and draft, then authorizes
one hash-bound save. A failed acknowledgement becomes `UNKNOWN`; receipt reconciliation can
confirm it, but cannot repeat it. Three owned lab workflows cover maintenance, dispatch handover
and inspection summaries. They save local demonstration records and send no emails or purchases.

See [operations and security contract](../../docs/operations/local-agent.md).
