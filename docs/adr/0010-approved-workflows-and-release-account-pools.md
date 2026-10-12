# ADR-010: Durable approved workflows and reserved execution accounts

- Status: accepted
- Date: 2026-10-13
- Extends: ADR-001, ADR-002, ADR-005 and ADR-008; clarifies ADR-009 availability wording.

## Context

Freight-specific claims do not describe every authorized browser operation. A workflow needs exact
inputs, approval identity, permitted accounts, destination preconditions and receipt semantics.
Long-lived freight slots also occupy accounts indefinitely, so simply adding another worker can
leave it without execution capacity.

## Decision

Add versioned validated workflow contracts, durable PostgreSQL jobs, scoped revocable stdio MCP
and human owner approval bound to the full canonical action. Preserve uncertainty after action
intent and reconcile using destination evidence. Fencing protects database authority; it does not
make an arbitrary destination validate a token or guarantee exactly-once external side effects.

Supervise the approved-workflow runner separately. Seed a dedicated named account pool and exclude
its group from legacy slot acquisition through typed settings. Keep the same account-hold authority
across both runtimes. Validate release template settings and prove both workers together.

Build static/backend/config artifacts from committed release inputs, store full commit metadata and
verify local/live hashes. Run the existing backup loop under a protected host service; its Docker
authority remains restricted to administrators. Keep independent-copy recovery as a separate gate.

## Consequences

New adapters require a deliberate authorization/receipt contract and adverse-condition tests.
Approval changes on any contract/input/account change. A missing receipt may remain inconclusive.
Reserved pools and worker configuration must agree. Shared-host availability remains unmeasured;
99% and 99.9% are objectives requiring monitoring and recovery proof, rather than a statement that
a particular percentage is impossible or already achieved. General workflow cell assignment and
the million-session design require further scale work.
