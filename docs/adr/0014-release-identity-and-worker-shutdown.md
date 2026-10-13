# ADR-014: Bind release identity and stop all actors before replacement

- Status: accepted
- Date: 2026-10-13

## Context

Source parity does not establish image identity. Separately built application/web images can
differ, tags can move, and an actor left running during dependency replacement can retain stale
authority or lose an acknowledgement. New durable-detection topics are incompatible with older
backends that may reject or prune them.

## Decision

Freeze an immutable source/artifact inventory and sign its exact primary files using an independently
retained trust anchor. Bind native app and web identities/SBOMs separately; inspect those identities
before startup and compare running roles afterward. Retain native vulnerability reports as scoped
point-in-time evidence.

Give every browser/execution worker a configured stop grace exceeding its application drain bound.
Gracefully stop freight, workflow and present crawler workers before recreating dependencies.
Verify successful non-OOM exits, released holds and retained uncertainty. Keep old control available
until all configured legacy streams have zero unread/pending work and no unexplained dead letters;
then stop control, validate a fresh archive and migrate.

## Consequences

Routine rollback changes static web assets while preserving compatible backends and durable mailbox
state. An older backend requires a separately tested recovery procedure; it is not a safe default.
Signatures, source/image parity and graceful exits complement behavioral verification rather than
replacing it. See [deployment](../operations/deployment.md) and
[exact artifact verification](../../tools/security/release-artifacts.md).
