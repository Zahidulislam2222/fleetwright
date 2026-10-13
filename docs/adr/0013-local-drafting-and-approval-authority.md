# ADR-013: Local drafting and exact approval have separate authority

- Status: accepted
- Date: 2026-10-13

## Context

A lightweight assistant must run without the fleet's database/queue services and must not turn
untrusted page text or model output into permission to act. The user must be able to inspect the
exact content and recover after interruption without repeating an uncertain save.

## Decision

Use SQLite/WAL for local task, approval and receipt state. An installed local model emits only a
validated title/body draft. Maintained templates choose origins, selectors and the form/receipt
contract. A single-use, expiring approval binds the complete template, destination, source, request
and final draft. Saving edits creates a fresh proposal/hash; polling preserves unsaved review text.

Use a dedicated persistent browser profile by default. Optional CDP creates an isolated context,
preserving owner tabs without inheriting their login. Loopback API safeguards, bounded browser
requests and context-lifetime WebSocket denial constrain the supported application flow.

## Consequences

The hosted page is an introduction/launch link rather than remote browser control. Interrupted
post-approval work remains UNKNOWN until exact matching receipts resolve it. HTTP/WebSocket
controls are not an operating-system sandbox; arbitrary hostile sites require separate isolation.
Windows directory privacy depends on ACLs; POSIX state modes have separate real-platform checks.

See [local-agent operations](../operations/local-agent.md) and [verification](../testing.md).
