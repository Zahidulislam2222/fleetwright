# Proposal draft: coordinated Playwright workers

I built Fleetwright to coordinate browser actions with durable ownership, predictable recovery and
an inspectable operational record. PostgreSQL owns claims and fencing; Redis Streams distributes
work. Browser actors keep warm authenticated sessions, while separate watchers detect matching
jobs. Filters, schedules, tenant isolation and receipt-based reconciliation are part of the system.

Recorded owned-board engine measurements were approximately **365 ms p50 / 540 ms p95** from
detection to confirmed booking. A separate controlled contention test exercised **200 competitors
and 10,000 jobs** with zero duplicate action attempts and destination-side ground truth. Those
competitors are coordination actors, not 200 Chromium workers. These are fixture measurements;
your destination's authentication, throttling and confirmation behavior must be measured separately.

For a client deployment, I would start with its authorization and action/receipt contract, then
deliver a bounded prototype with a correctness test and measured latency. A larger worker pool
would follow a representative sustained run with agreed resource, failure and recovery limits.
The existing demo is one host; multi-zone availability and large customer capacity are not implied.

## Eight reusable technical answers

These topics are suitable for tailoring to a client's architecture questions. They are not a
verbatim reproduction of an unseen job brief.

### 1. How are workers coordinated?

The database is the ownership authority. Claims carry a lease and fence, and stale actors cannot
advance a claim using an old fence. Redis carries dispatch streams and accelerates contention;
its lock expiry never replaces the database decision. Transactional outboxes preserve events
across temporary queue outages. Tenant identifiers and row-level security isolate operational data.

### 2. How does the browser fleet scale?

Workers reuse Chromium and isolate sessions in browser contexts. Cells group a queue, watchers and
worker pool so capacity can be added in bounded units. Fleet density and authenticated destination
throughput are separate benchmarks: a context-count test alone does not establish a production
worker count. Completed sustained runs and their hardware/workload belong in the
[measurement record](../scaling/verification-2026-10-13.md).

### 3. How are login, OTP and sessions handled?

Destination adapters define authentication and receipt behavior. Session state is encrypted, and
renewal is guarded by account ownership and deadlines. Tests exercise expired/revoked sessions,
delayed login readiness, account contention and receipt-only recovery. This does not authorize
bypassing a destination's access controls or automation policy.

### 4. How is latency controlled without overrunning accounts?

Watchers and actors have different jobs: detect quickly, then act from a warm session. Filters and
schedules are maintained data. Account-group eligibility and database-clock pacing guard admission
and the action boundary. Instrumented stage timestamps explain where time is spent; increasing
concurrency cannot override an account's configured limit. Historical fixture latency is evidence,
not a customer SLA.

### 5. How are duplicate actions and worker crashes handled?

Claims use unique ownership and fencing, and tests compare results against the destination's own
booking log. A crash during an action creates an uncertain outcome. The system queries matching
destination evidence before deciding what happened; it does not assume a timeout means failure.
General approved workflows remain `UNKNOWN` when the receipt is inconclusive. No exactly-once
guarantee is made for arbitrary websites.

### 6. What can an operator inspect?

The console exposes tenant-scoped claims, workers, audit, latency and live invalidation updates.
Approved workflows include exact proposal review and evidence export. Monitoring and recovery
tools have their own authenticated probes, failure/recovery records and restore tests. An
independent probe on an operator's computer is available only while that computer and its network
are running; it is not a continuously staffed external monitoring service.

### 7. How is it deployed, including AWS?

The implemented deployment uses Docker Compose and a small public demonstration fleet. Releases
are rehearsed, checked for drift and compared by file hashes after deployment, with retained
rollback inputs. A configurable AWS reference has Terraform validation and three mocked-plan
checks; no AWS provisioning or zone-loss exercise is claimed. Cloud costs and production topology
must be reviewed before a paid deployment.

### 8. What would a delivery milestone contain?

Written criteria, maintained destination/configuration data, source and tests, reproducible run
instructions, a real browser demonstration and a short evidence report. Acceptance covers both
the expected action and the dangerous paths: competing actors, stale ownership, response loss,
worker interruption, account limits and recovery. A release additionally needs its own exact
artifact, security gates, rehearsal, deployment verification and operational handoff.

Evidence: [test workloads and historical measurements](../testing.md),
[claim architecture](../architecture/claim-lifecycle.md),
[approved workflow operations](../operations/reliable-browser.md),
[AWS reference](../../infra/terraform/README.md), [capacity boundaries](../scaling/README.md).

Portfolio: https://zahidul-islam.com/ · GitHub: https://github.com/Zahidulislam2222
