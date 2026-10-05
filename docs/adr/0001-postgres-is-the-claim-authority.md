# ADR-001: Postgres is the claim authority; Redis is a fast path

- Status: accepted
- Date: 2026-10-05

## Context

Two workers must never book the same job. Redis `SET NX PX` locks are fast, but a lock can expire
while its holder is paused (garbage collection, a frozen VM), and a failover can lose it. A second
worker then acts too.

## Decision

Claims live in Postgres. A unique constraint on `(tenant_id, target_job_key)` picks the winner and a
fencing token from a sequence guards every later step. Redis is used only to drop obvious duplicates
early (`SET NX` per job) and to move messages quickly.

## Consequences

- Correctness never depends on Redis. Losing a Redis cell loses speed, not safety.
- Each claim costs a few short Postgres transactions; this is the throughput limit to watch
  (see the capacity model).
