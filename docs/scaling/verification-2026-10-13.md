# Scale verification — 13 October 2026

This page records measured evidence from local tests and isolated verification on an existing
server. It does not establish 100k/1M-user capacity,
monthly availability, multi-zone failover, or arbitrary destination exactly-once execution.

The final integrated release-source suite passed **260 tests, with 6 platform/opt-in skips,
in 777.824 seconds**. Five platform-specific cases separately passed on POSIX; the installed
local-model flow also passed separately. This includes the unchanged 200-competitor/10,000-job
contention workload and all four real Chromium freight-engine scenarios. Exact-image scanning,
signing and rehearsal are separate gates; subsequent sections record the verified rc2 artifacts
without declaring a later release deployed.

## Freight correctness and fair admission

The isolated runtime suite passed **31/31 tests in 556.67 seconds**, including the unchanged
200-competitor/10,000-job contention workload, four real Chromium freight-engine scenarios,
owned workflow execution, destination-session recovery, and three new account-policy cases.
The account-policy tests enforce DB-clock pacing, group eligibility, retained queued state and a
single winner among 20 simultaneous budget reservations. Synthetic contention/owned-board fixture
accounts explicitly use a high permitted local test rate; production account limits remain real
database data. Admission reserves the budget; the ACTING boundary rechecks fenced worker/account
authority and refreshes the interval. Completion starts another full interval so slow preparation
or actions cannot consume the following action's cooldown. The final targeted action-boundary
suite passed 27/27 cases in 65.73 seconds (slow contention intentionally excluded from this targeted
run and retained for the final full suite). Both freight and actual browser workflow delays were
exercised and retained in the final integrated source suite.

Workflow scheduler now reads a bounded page from its configured cell directory, admits a bounded
number of jobs per tenant turn and wraps its cursor after exhausting the directory. In-flight
work may finish while stopping; shutdown bounds its wait and preserves durable execution state
for recovery. These controls are implementation evidence, not a throughput guarantee.

Durable cell handover now persists raw detections before Redis delivery and consumes them atomically
with the filter/claim decision. New-cell relay retries unread or in-flight detections after a move;
atomic directory/claim/mailbox changes and retired-slot drain have real DB/Redis crash/rollback tests.
The targeted 21-case handover/control/queue/browser/drain suite passed in 125.76 seconds. A legacy
unpersisted Redis backlog must be drained before upgrading. The final suite also covers the
new multirow mailbox authority, rollback and tenant-isolation cases.

A later full-suite run exposed a slow-host backlog: confirmed jobs were published before each
new test window, although the board audit retained the configured 600 loads/minute. The watcher
was committing one database transaction per raw detection. It now persists a configured bounded
chunk in one atomic insert and updates its local deduplication cache only after commit. Existing
payloads remain authoritative across duplicate delivery.

A controlled real-browser comparison seeded 200 older open loads and injected 150 ms of
PostgreSQL latency per durable transaction. The unchanged 15-second criterion requires at least
50 newly published bookings, no duplicate attempts, and matching database/board outcomes.
Per-row transactions produced **0 new bookings** (84 older bookings confirmed); the bounded
100-row transaction version **passed the same criterion**. This reproduces the failure mechanism
under injected latency; it does not establish the precise original host scheduling conditions.
The original contention and engine assertions remain intact and passed in the final source suite.

## Browser density

The harness uses Chromium 153.0.8010.12 / Playwright 1.63.0, separate browser contexts, an owned
static fixture and repeated click/read operations. Initial Windows runs used a 12-logical/
6-physical-core machine with 25,691,734,016 bytes of RAM. A 50-context attempt stopped after
1,171.187 seconds and 212 rounds; a retry stopped after 414.140 seconds. Both refused to continue
when available RAM fell below the configured 2 GiB floor during overlapping local work.
Neither attempt passed the requested hour, and both are preserved.

Authorized sustained verification instead used an existing 8-core Linux host with
25,199,177,728 bytes of RAM. Each benchmark ran in its own nonroot, read-only, no-network container
with 2 CPU quota, 1,024 PID limit, dropped capabilities and no-new-privileges. The 50-context
container was capped at 6 GiB and the 70-context container at 8 GiB. They overlapped, while
production application HTTP/DB endpoints were never benchmark targets.

The first server 70-context attempt stopped incomplete after 1,799.080 seconds and 244 rounds
because summed process RSS exceeded 8 GiB, while Docker's actual container usage was about
1.77 GiB. Summed RSS counts shared Chromium pages repeatedly. That abort remains preserved.
After regression tests and fresh review, the corrected Linux harness enforces
`memory.current + memory.swap.current` from cgroup v2 against the unchanged caps and fails
closed if bounded accounting is unavailable. Summed RSS remains descriptive. The 2 GiB host
memory floor was never reduced. The earlier 50-context server run was preserved as superseded;
no elapsed time was carried into either corrected run.

Both corrected, uninterrupted hour windows **passed**, with all requested contexts retained,
zero action errors and container exit code 0:

| Contexts | Actual duration | Complete rounds / fixture clicks | Memory cap / CPU quota | Maximum sampled cgroup charge |
|---|---|---|---|---|
| 50 | 3,601.986 s | 516 / 25,800 | 6 GiB / 2 | 1,535,565,824 bytes |
| 70 | 3,602.632 s | 468 / 32,760 | 8 GiB / 2 | 2,082,316,288 bytes |

The lowest sampled host availability was 15,664,308,224 bytes, above the unchanged floor.
Each uploaded harness/fixture/config file was SHA-256 checked against local bytes. The runs used
an isolated verification image; they establish neither final release binary identity nor
freight throughput, 100k/1M-user capacity, or an availability SLO.

Configuration: `loadtest/density.json`; command: `python -m loadtest.density loadtest/density.json`.
The server profiles select cgroup accounting and the corresponding container cap. Atomic progress
and final reports preserve incomplete attempts and completed windows independently.

## Control-plane network benchmark

`loadtest/http.json` defines 16 API clients, 32 SSE clients (2 deliberately slow), 30 seconds and
five-second reconnect turns. It refuses non-literal loopback targets and redirects and bounds
latency sample storage. The acceptance fixture serves the real coordinator and gateway against
isolated local data, publishes timestamped invalidations, and separately forces a Hub queue
overflow. OS/TCP buffering means a slow HTTP reader alone does not prove bounded application queue
eviction; that proof is reported separately.

Initial network runs completed eligible requests with no HTTP errors but failed harness teardown:
Python3.12 Windows Proactor raised WinError10054 before socket detach during rapid SSE reconnects,
leaving server.wait_closed pending. The harness now uses a dedicated standard selector loop for
network-only work, with fresh async pools in that loop. The initial corrected acceptance passed
in a 7-case scheduler/tool/network suite. A later combined
run exposed Redis timeout failures during cold client/database setup on the shared event loop.
The harness now constructs one verified SSL context and 48 independent clients before starting
the Hub/publisher, and prewarms the configured database pools and Redis. Cold database setup
(1.359 seconds) and client setup (0.016 seconds) are reported separately. The final 20-case
handover/engine/network/density selection passed in 135.60 seconds. Its steady-state window
was 30.297 seconds:

| Measurement | Observed |
|---|---|
| API requests / SSE connections / reconnects |1,199 /192 /160 |
| SSE data frames / deliberate slow-reader frames |12,420 /489 |
| HTTP/network errors / forced Hub slow-consumer eviction |0 / passed |
| API latency p50 / p95 / p99 |223.48 /762.90 /1,636.80ms |
| SSE connection latency p50 / p95 / p99 |415.60 /1,351.44 /1,420.05ms |
| Timestamped event delivery p50 / p95 / p99 |28.38 /161.47 /1,321.47ms |

These measurements overlap local browser/image work and include deliberate reconnects/slow
readers; they are not isolated service capacity, an SLO, or a representative multi-tenant workload.

## AWS reference

Terraform 1.16.5 and signed hashicorp/aws 6.68.0 provider passed `validate`; all **3 mock-plan tests
passed**. Inputs cover regions/zones, private subnets, immutable image, encrypted multi-zone data,
Redis ACL/TLS, replicas, secrets references and private archives. No AWS credentials, paid API calls,
provisioning or actual zone-loss test were used. The reference documents deployment prerequisites;
mock validation does not prove the full production topology can be applied successfully.

## Exact-image assurance and remaining scale limits

The `20261013-free-local-rc2` native server app and static-web images each passed Trivy with
zero HIGH/CRITICAL findings; their identity-verified CycloneDX inventories contain 1,094 and
72 components. The actual app image passed two-context Chromium navigation/isolation and ten
module imports. The web image's three exact Alpine security patch versions were verified offline.
Local rehearsal and native server image IDs differ; source parity is not binary parity.

The scoped passive rc2 rehearsal scan completed in 61.265 seconds with no HIGH alerts, retaining
one MEDIUM inline-style CSP warning, one LOW COEP warning and six informational alerts. Raw exit 2
means warnings: there were zero failures, two warnings, 64 passes and no ignored rules. The observed
web image/release/manifest identity remained unchanged through the scan. All 129 served static files
matched the release manifest. See [security assurance](../security/asvs.md) for exception boundaries.

These image and browser checks do not increase the measured API/SSE concurrency or establish a
monthly availability result. The 50/70 fixture-hour image is distinct from the final app image;
neither run is recast as a final-release throughput test. No 1k/10k/100k/1M-session, representative
multi-tenant browser-density or actual multi-zone failure result is claimed. Each newer release
must repeat its own artifact and behavior gates before activation.

See [AWS reference](../../infra/terraform/README.md), [scaling roadmap](README.md),
[capacity model](capacity-model.md), and [security assurance](../security/asvs.md).
