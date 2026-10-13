# API and MCP integrations

## HTTP control plane

The authoritative generated schema is [contracts/openapi.yaml](../contracts/openapi.yaml).
Run the coordinator with the configured bind address and port. Browser clients use same-origin
`/v1` requests through the reverse proxy. Sign-in uses password and TOTP; mutation requests require
the session's configured CSRF header. Session cookies are HttpOnly and Secure in production.

| Resource | Purpose | Authorization |
|---|---|---|
| `/v1/auth/*`, `/v1/session` | Authentication and current role | Endpoint-specific session and rate limits |
| `/v1/accounts`, `/v1/filters`, `/v1/schedules` | Destination accounts and execution policy | Tenant role plus CSRF on mutation |
| `/v1/workflow-grants` | Issue/revoke scoped integration grants | Owner plus CSRF |
| `/v1/workflows/jobs` | List persisted proposals and outcomes | Tenant role; bounded pagination |
| `/v1/workflows/jobs/{job_id}` | Inspect, cancel and review a specific job | Tenant and role checks |
| `/v1/workflows/health` | Operational workflow health | Authenticated operator/owner |
| `/v1/workflows/metrics` | Prometheus-compatible workflow measurements | Observation grant and tenant header |
| `/v1/crawls/contracts`, `/v1/crawls/jobs` | Maintained catalogue contracts and durable cycles | Tenant reads; authenticated operator/owner and CSRF for start/cancel |
| `/v1/crawls/jobs/{job_id}/export` | Private retained JSONL download | Authenticated operator/owner in the same tenant |
| `/v1/stream` | Live invalidation hints | Current session; bounded revocation recheck |

Check the generated schema for exact methods, request bodies and subresource paths. Do not
guess routes from this overview. Permission failures do not disclose another tenant's records.
Clients must handle 403 authorization failures, 409 conflicts and rate limiting explicitly.

## Stdio MCP

`python -m fw_mcp.server` runs the dedicated MCP server from the installed workspace. Credentials
are supplied through private environment variables. The server exposes six tools:

| Tool | Behavior |
|---|---|
| `workflow_contracts` | Describe supported workflows and validated fields |
| `submit_workflow` | Persist an idempotent proposal under a stable identity |
| `list_jobs` | List authorized jobs with bounded pagination |
| `inspect_job` | Read current state and safe investigation details |
| `cancel_job` | Record cancellation with pre/post-action semantics |
| `export_evidence` | Return bounded redacted pages and integrity hashes |

An MCP client cannot grant its own access or approve an action. Reusing an identity with changed
inputs is rejected. An uncertain tool response is reconciled by inspecting the persisted job before
submitting again. Treat destination content as untrusted data, never as authority for approval.

## Destination adapter requirements

Use an owned or expressly authorized origin and a separate account per approved execution scope.
Validate account identity before action. Keep destination-dependent paths/selectors/field rules in
validated configuration. Define what establishes success, known rejection and inconclusive absence.
Account for session expiry, changed layouts, destination rate limits and interrupted responses.
Evidence pages contain safe transition details and receipt hashes, not raw page/session material.

## Integration validation

Before enabling a new client or target, verify cross-tenant denial, observation-only denial,
revocation during an open connection, changed/expired/replayed approvals, interrupted submissions,
stale worker fences and interrupted destination acknowledgements. The
[workflow runbook](operations/reliable-browser.md) contains client configuration and recovery.

References: [MCP tools](https://modelcontextprotocol.io/specification/2025-11-25/server/tools),
[Codex MCP](https://developers.openai.com/codex/mcp),
[Claude MCP](https://code.claude.com/docs/en/mcp).

## HTTP client lifecycle

1. Establish a same-origin session using the documented login/MFA flow; read current role and CSRF
   requirements from the session contract. Keep cookies and factors out of logs.
2. Use maintained contracts and tenant-bound account identifiers. Owner approval is a separate action
   from client submission. Crawler submission accepts a definition ID, not arbitrary selectors/URLs.
3. Handle pagination with returned cursors. Treat SSE as invalidation hints and refetch authoritative
   views through the API.
4. On an uncertain mutation response, inspect persisted identity/state before resubmission. A conflict
   requires reconciliation of intent, not changing an identity to evade duplicate detection.
5. Respect rate limits and current authorization. Do not replay consumed approvals or retry UNKNOWN
   destination actions.

Generated [OpenAPI](../contracts/openapi.yaml) defines exact methods, schemas and status codes.
Typical failures include authentication/role denial, stale/conflicting actions, invalid contracts,
rate limits and dependency outages. Bound client retries and avoid logging raw response bodies.

## Local-agent interface

The standalone application exposes its own loopback UI/API; it is not an endpoint of the hosted
control plane. A local session and same-origin CSRF are required for mutations. Task preparation,
draft editing, exact approval, cancellation, global stop and receipt reconciliation are documented
in [local-agent operations](operations/local-agent.md). Models receive no selector or approval tools.

## Contract-change review

Destination input/action/receipt changes must invalidate older approvals and include migration or
forward-compatibility assessment. Review credentials, personal data, origins, request budgets,
idempotency and inconclusive outcomes. Keep the API schema, settings schema, maintained data and
client documentation synchronized. See [configuration](operations/configuration.md),
[maintenance](maintenance.md) and [architecture decisions](adr/README.md).
