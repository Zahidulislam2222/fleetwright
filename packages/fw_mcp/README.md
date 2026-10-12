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
