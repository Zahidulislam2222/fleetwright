# ADR-015: browser readiness and child-process supervision

Status: accepted; records the browser-recovery implementation verified on 14 October 2026.

## Context

A running freight Python process can outlive its Playwright driver or browser. Heartbeat freshness
alone then reports useful capacity incorrectly. A browser disconnect callback also failed to
identify actual driver termination in a dedicated process reproduction. Planned SIGTERM still
needs account release and a successful bounded drain.

## Decision

Supervise the Chromium connection with a read-only CDP roundtrip and disconnect notification.
The typed heartbeat interval owns probe cadence and the action timeout bounds session creation,
send and successful detach together. A failed probe proceeds to whole-browser disposal, avoiding
unbounded failure-path detach. Attempt all later resource cleanup even when an earlier step fails.

Unexpected connection loss causes process failure after cleanup so the existing container
supervisor starts a fresh browser. Only connected, ready slots report running; starting slots
remain stale in API health totals. Preserve explicit stopped/draining state and durable uncertain
action history through recovery.

## Consequences and verification

Readiness and process liveness become separate signals. Operators verify actual bookings and
destination receipts alongside health. Normal SIGTERM remains an exit0 drain with stopped rows
and zero held accounts; child loss deliberately exits for supervisor recovery.

Tests terminate the actual driver/browser child, stall protocol send/detach, exercise SIGTERM and
cleanup failures, and inspect database/API readiness. Exact-release rehearsal additionally checks
one supervisor restart, ready slots, identity/source parity and strict shutdown. See
[dated evidence](../releases/2026-10-14.md) and
[service ownership](../operations/service-ownership.md). The original reason for the earlier
production child loss remains unproven; this decision addresses detection, recovery and telemetry.
