# Fleetwright product and delivery scope

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
