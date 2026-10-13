# Fleetwright MCP — Reliable Browser Operations

Local stdio MCP server backed by Fleetwright's existing coordination core. It supervises the
owned freight-booking and maintenance-request workflows. It does not offer arbitrary URLs,
selectors or a human-approval tool.

Tools: `workflow_contracts`, `submit_workflow`, `list_jobs`, `inspect_job`, `cancel_job`,
`export_evidence`. Every invocation rechecks the configured tenant, current user role, grant
scope, database-clock expiry and revocation. Observation and execution permissions are separate.

See [the workflow runbook](../../docs/operations/reliable-browser.md) for owner approval,
client setup, worker operation, monitoring, backup and recovery.

Release operation and limits: [deployment](../../docs/operations/deployment.md) · [maintenance](../../docs/maintenance.md).

## Install, connect and supervise

Install the root locked workspace with `uv sync --frozen`; run
`uv run python -m fw_mcp.server` with the workspace as the working directory. An owner first issues
a tenant-bound grant and supplies its values privately through `FW_MCP__TENANT_ID` and
`FW_MCP__ACCESS_TOKEN`. Keep tokens out of arguments, prompts and committed client configuration.

The MCP process accesses configured PostgreSQL authority directly; it is a trusted local integration,
not a public HTTP MCP endpoint. A separate `fw_worker.workflows` process performs approved actions.
After an uncertain submission, inspect the stable job identity before retrying. Follow pagination
cursors for lists/evidence and handle revoked/expired grants as authorization failures. See the
[API/tool contract](../../docs/integrations.md) and [configuration](../../docs/operations/configuration.md).
