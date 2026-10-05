# ADR-002: A crash during the action is UNKNOWN, never a blind retry

- Status: accepted
- Date: 2026-10-05

## Context

If a worker dies after sending a booking, nobody knows whether the booking happened. Retrying
could book twice; dropping could lose a job that was in fact booked.

## Decision

A claim that expires in `ACTING` becomes `UNKNOWN`. The reconciler checks the target ("what has this
account booked?") with the account's own sealed session and records the truth as `RECONCILED`.

## Consequences

- No duplicate bookings from retries.
- Needs a way to read back the account's bookings on every supported target. A target without one
  must be onboarded with an operator review step.
