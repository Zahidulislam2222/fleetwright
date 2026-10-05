# ADR-004: Tenant isolation with Postgres row-level security (FORCE)

- Status: accepted
- Date: 2026-10-05

## Context

Fleetwright is designed as a multi-tenant service. A single missing `WHERE tenant_id = …` in
application code would leak one customer's data to another.

## Decision

Every tenant table has row-level security `ENABLE` and `FORCE`, with a policy on
`current_setting('app.tenant_id')`, set per transaction (`SET LOCAL`). Indexes start with `tenant_id`.
Workers use a role with column-level grants only.

## Consequences

- A forgotten filter returns zero rows instead of another tenant's rows (tested, mutation-checked).
- Cross-tenant admin work needs an explicit system path (directory tables only).
