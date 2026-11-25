# ADR-016: Console help assistant and its provider egress

- Status: accepted
- Date: 2026-11-25

## Context

The Fleetwright console must offer a project-specific help assistant (product requirement; the
owned freight exchange carries a visitor guide instead). Console visitors — clients and developers evaluating the product — need answers about
screens, states and live fleet health. The owner chose a paid hosted model through OpenRouter over a
small model on the shared server, whose CPUs are already busy with other applications. Until now the
backend network was internal: no service could reach the internet.

## Decision

- Retrieval over approved public documents with a small BM25 keyword index (no vector store); the
  index is generated and a test fails when it no longer matches the documents.
- Read-only tools only, executed as the asker inside the asker's tenant. No audit or user-list tools.
- Bounded spend: per-user/per-address hourly limits, a per-process concurrency limit, and a daily
  budget reserved atomically in Redis at worst-case cost before each call. A dedicated provider key
  with its own monthly cap per deployment is the intended second layer (planned, not yet in place). Any limit or failure falls back to documentation search.
- AI disclosure before the first question; every AI answer is marked machine-readably.
- Only the API container joins a new, separate `egress` bridge network. `backend` stays internal;
  no other service gains internet access. The API makes outbound calls only to the configured
  provider endpoint; it never fetches visitor-supplied URLs.

## Consequences

The API now has a general outbound route; a future code path that fetches attacker-chosen URLs from
the API would be an SSRF risk and needs the crawler's egress guard. An egress proxy restricted to the
provider host is the next step if the API gains more outbound features. Provider-side retention and
subprocessors follow the provider's terms. Answers can be wrong; evaluation results are recorded with
each release. See [console guide](../console-guide.md) and [threat model](../security/threat-model.md).
