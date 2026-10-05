# ADR-007: Envelope encryption for sessions and credentials

- Status: accepted
- Date: 2026-10-05

## Context

The vault stores target-site passwords and logged-in session state. A database dump must not hand
out working sessions.

## Decision

Each record gets its own random AES-256-GCM data key, wrapped by a master key identified by
`key_id`. The associated data binds the ciphertext to tenant, account and purpose, so a ciphertext
copied to another row does not decrypt. On AWS, the wrap moves to KMS without changing callers.

## Consequences

- Key rotation is per `key_id`; old records stay readable until re-sealed.
- The master key must be protected like any root secret (environment or secret manager only).
