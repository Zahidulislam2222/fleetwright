# ADR-003: Transactional outbox for every message that follows a database change

- Status: accepted
- Date: 2026-10-05

## Context

Writing to Postgres and then publishing to Redis can fail between the two steps, so the stream and
the database disagree.

## Decision

The message is written to an `outbox` table in the same transaction as the change. The dispatcher
publishes immediately after commit (fast path) and a relay publishes anything left behind. The relay
checks that the tenant still belongs to its cell before publishing.

## Consequences

- At-least-once delivery; consumers are idempotent (fencing tokens make a duplicate message
  harmless).
- One more table to prune.
