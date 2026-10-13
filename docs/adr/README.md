# Architecture decision records

Each record states the context, the decision and its consequences. A changed architectural decision gets a new record that supersedes the old one; preserve the
original context and consequences. Editorial terminology changes do not create a new decision.

| # | Decision | Status |
|---|---|---|
| 001 | [Postgres is the claim authority; Redis is a fast path](0001-postgres-is-the-claim-authority.md) | Accepted |
| 002 | [A crash during the action is UNKNOWN, never a blind retry](0002-unknown-is-never-retried.md) | Accepted |
| 003 | [Transactional outbox for every message that follows a database change](0003-transactional-outbox.md) | Accepted |
| 004 | [Tenant isolation with Postgres row-level security (FORCE)](0004-row-level-security.md) | Accepted |
| 005 | [Cells: scale workers by adding independent units](0005-cells.md) | Accepted |
| 006 | [Many browser contexts per Chromium, roles per slot](0006-contexts-not-browsers.md) | Accepted |
| 007 | [Envelope encryption for sessions and credentials](0007-envelope-encryption.md) | Accepted |
| 008 | [One typed configuration boundary; product data in YAML](0008-config-boundary.md) | Accepted |
| 009 | [What "1M users" and "99% uptime" mean here](0009-scale-targets.md) | Accepted |
| 010 | [Approved workflows, reserved accounts and release verification](0010-approved-workflows-and-release-account-pools.md) | Accepted; clarifies 009 |
| 011 | [One durable crawl frontier and pinned HTTP egress](0011-durable-crawl-frontier.md) | Accepted |
| 012 | [Persist raw detections before cell delivery](0012-durable-raw-detections.md) | Accepted; extends 003 |
| 013 | [Local drafting and exact approval have separate authority](0013-local-drafting-and-approval-authority.md) | Accepted |
| 014 | [Bind release identity and stop all actors before replacement](0014-release-identity-and-worker-shutdown.md) | Accepted |

## Reading the decisions

Start with authority (001–004), then process/cell isolation (005–007), configuration (008) and
future scale objectives (009–010). Crawler egress/frontier (011) and durable raw detections (012)
explain the newer persistence boundaries and backend compatibility requirements.
Local assistant authority (013) and native image/all-worker lifecycle identity (014) complete the
operational boundaries used by the current implementation.

An accepted decision describes the chosen design, not a certification or measured capacity.
Use [current architecture](../architecture/overview.md), [test evidence](../testing.md) and
[release operations](../operations/deployment.md) for implementation status and promotion gates.
