# ADR-006: Many browser contexts per Chromium, roles per slot

- Status: accepted
- Date: 2026-10-05

## Context

One browser per account costs several hundred MB each. Watching and acting need different things:
watchers must see new loads fast; claimers need a warm, logged-in page ready to act.

## Decision

One Chromium per worker process with many isolated contexts ("slots"). A slot is a watcher (listens
to the feed's JSON responses) or a claimer (keeps a warm page and acts on leased claims).

## Consequences

- Measured ≈ 70–103 MB per context, ≈ 1.8 cores at 32 contexts.
- A browser crash takes down every slot in that process; workers are stateless, so the supervisor
  restarts them and leases expire safely.
