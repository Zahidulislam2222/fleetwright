# Fleetwright: making browser automation inspectable and recoverable

Fleetwright is a portfolio engineering project built against owned freight and request-portal
fixtures. It is not a client testimonial, and its test outcomes are not third-party business metrics.

## The problem

Independent scripts can appear fast while competing for the same job, losing progress at a crash
or repeating an action whose acknowledgement was lost. Crawlers can quietly return fewer records,
and a model-driven browser assistant can confuse page instructions with permission to act.

The project connects three capabilities around explicit authority and evidence: coordinated
browser workers, durable catalogue crawling and a lightweight local draft-and-review assistant.

## The implementation

PostgreSQL is the fleet's claim authority, with leases, fencing, tenant isolation and transactional
outboxes. Redis Streams transports work. Warm browser actors perform actions, while separate
watchers detect opportunities. An ambiguous action is investigated using destination receipts;
the system never treats a missing acknowledgement as proof that nothing happened.

The crawler keeps a durable frontier, typed field allowlists, shared origin pacing and complete-cycle
quality checks. Its output is a bounded private JSONL export. The local assistant uses SQLite and
an installed local model; templates choose operations, and a human approves the exact draft.
Changed, expired and replayed approvals are rejected before the browser performs the save.

## Before and after

| Before | Implemented outcome | Evidence boundary |
|---|---|---|
| Uncoordinated action attempts | Fenced claims and destination-ground-truth duplicate checks | Controlled 200-competitor / 10,000-job test; not 200 browsers |
| Slow setup on every action | Warm sessions and measured stages | Owned-board engine p50 approximately 365 ms / p95 540 ms; historical fixture workload |
| Catalogue page scripts without durable progress | Resumable frontier, quality alarms and approved-field exports | Owned paginated catalogue and adversarial HTTP/TLS tests |
| A local-agent prototype | Three real local-model browser form saves with exact human approval | Owned maintenance, handover and inspection templates; no social posting integration |
| A timeout treated as failure | UNKNOWN state and matching-receipt reconciliation | Lost acknowledgements and killed-worker tests |

## Problems found during verification

An early contention test booked only 77 of 10,000 jobs and still reported no duplicates. That
result was too weak to establish usefulness. Coverage assertions were added so the test requires
substantial successful work and exercised action-phase recovery, as well as the duplicate invariant.

Fresh review later found that HTTP request interception did not constrain WebSocket connections.
Real dedicated-browser and CDP tests observed an off-origin handshake and marker before approval.
A context-lifetime WebSocket denial policy changed both tests to zero destination handshakes and
messages. The checks observe the destination rather than trusting a page-side error.

Crawler review also exposed a timeout that cancelled an await while its blocking network operation
continued. Fetches now run in an owned disposable process, with termination and process-exit
confirmation before retry. Slow-response tests exercise that physical boundary.

## What the evidence supports

The recorded tests support correctness and recovery on the stated fixtures, real local model
drafting, and explicit approval boundaries. A local agent/configuration verification run passed
25 cases with actual Ollama and Chromium; separate Linux tests checked private state permissions.
The browser-transport and fetch-timeout findings were corrected with regression tests. A disclosed
development-only dependency advisory remains separate from those fixes and from final release
scans; see the [workflow verification notes](../operations/reliable-browser.md).

They do not establish arbitrary-site exactly-once execution, a hostile-site OS sandbox, 1M-user
capacity, multi-zone recovery or measured monthly availability. Fleet density, authenticated
throughput and control-plane concurrency are different workloads. Release claims require their
own rehearsal and deployment evidence; local implementation alone is not proof of publication.

Source and evidence: [architecture](../architecture/overview.md), [testing](../testing.md),
[crawler](../operations/crawler.md), [local agent](../operations/local-agent.md),
[scaling measurements](../scaling/verification-2026-10-13.md), [release record](../releases/2026-10-13.md).
