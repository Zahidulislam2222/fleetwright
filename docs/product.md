# Fleetwright product guide

Fleetwright coordinates authorized browser operations through a durable control plane. Operators
review exact proposals; scoped MCP clients submit and investigate work; browser workers execute
approved actions; destination receipts establish outcomes. An interrupted action remains UNKNOWN
until evidence resolves it. A human review may be required indefinitely when a destination cannot
provide authoritative evidence.

## Supported workflows

| Workflow | Contract | Success evidence |
|---|---|---|
| Freight booking | Published load reference and permitted destination account | Matching account booking receipt |
| Maintenance request | Stable reference, title and priority on the owned service portal | Matching account/reference/title/priority receipt |

Contracts define input constraints, account targets, preconditions, selectors, action paths,
destination statuses and reconciliation. A contract change invalidates the previous approval.
Adding a third workflow requires a reviewed contract and destination adapter, reconciliation proof,
authorization review and acceptance tests; arbitrary URLs/selectors are not accepted by MCP tools.

## Operator and integration roles

Owners issue/revoke grants and approve exact actions. Operators inspect progress, investigate and
request safe cancellation. Viewers observe authorized information. Public access has restricted
controls and masked data; it cannot approve workflows or issue integration grants. MCP observation
and execution scopes remain separate and current authorization is checked on every invocation.

The hosted `/agent` page links to the separate local SQLite/Ollama application. Three maintained
owned templates draft maintenance, handover and inspection records, then require exact human
approval before a browser form save. Local state, private browser profile and receipts remain on
the owner's device. Optional CDP uses an isolated context and preserves existing tabs; it does
not inherit their logins. The hosted page does not control the local browser.

The console's catalogue crawler runs validated same-origin definitions with durable progress,
bounded HTTP egress, quality guards and private JSONL exports. Public visitors see aggregate state;
operators can start/cancel/export. See [crawler](operations/crawler.md) and
[local agent](operations/local-agent.md) for supported behavior and limits.

The dedicated MCP package supports model-supervised fleet workflows with the owner console.
Codex integration has end-to-end verification; Claude configuration and transport support are
documented, with account-level verification deferred. Implementation and release verification
are separate; consult the release record for what is currently deployed.

## Delivery boundaries

Fleetwright includes its own freight board and service portal for controlled destination testing.
No relationship with a commercial freight marketplace is implied. Customer integrations require
written authorization and the [onboarding checklist](legal/acceptable-use.md).

This repository is source-available under [LICENSE](../LICENSE). Public availability of source is
not a grant of unrestricted commercial use; review the license before distribution or resale.
Hosted service pricing, support agreements and contractual service levels are separate agreements.

## Documentation map

- [Architecture](architecture/overview.md), [workflow operations](operations/reliable-browser.md)
  and [API/MCP reference](integrations.md).
- [Security](security/controls.md), [privacy](legal/privacy.md) and [legal register](legal/README.md).
- [Capacity plan](scaling/capacity-model.md), [1M+ user architecture](scaling/README.md),
  [availability objectives](scaling/slo.md) and [roadmap](roadmap.md).
- [Deployment](operations/runbooks.md), [testing](testing.md) and [maintenance](maintenance.md).

## Onboard an authorized workload

1. Establish the customer/tenant owner, destination permission, account scope and data purpose.
2. Select fleet workflow, catalogue crawler or local agent according to the actual action boundary.
3. Define allowed origins, fields/selectors, identity, rate budgets, retention and success/uncertainty receipts.
4. Provision private accounts and least-privilege grants; validate tenant isolation and owner approvals.
5. Exercise session expiry, rate limits, changed pages, interrupted acknowledgements and recovery.
6. Agree operating ownership, support, measured capacity and recovery objectives before production use.

The built-in destinations provide reproducible acceptance environments. New targets require their
own contract and review; an accessible page or a permissive robots file alone is not authorization.
See [acceptable use](legal/acceptable-use.md), [privacy](legal/privacy.md) and
[security onboarding](security/controls.md).

## Choose the execution path

| Need | Execution path | Authority and state |
|---|---|---|
| Sustained coordinated freight work | Warm fleet actors and watchers | PostgreSQL claims, account pacing and cells |
| A reviewed business action | MCP proposal plus owner console | Versioned workflow approval and fenced worker |
| Approved structured data collection | Catalogue cycle | Durable frontier, extraction allowlist and private export |
| Local content drafting and form save | Standalone local agent | Installed model drafts; SQLite binds human approval and receipt |

Current verification includes the full 260-case regression, separate post-correction agent checks,
real MCP/model browser flows and 50/70-context fixture endurance hours. These do not establish a
customer workload or availability SLA. [Testing](testing.md) records their scope;
[future scale and availability](scaling/README.md) has explicit promotion gates.
