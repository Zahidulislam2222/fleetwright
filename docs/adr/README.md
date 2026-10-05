# Architecture decision records

Each record states the context, the decision and its consequences. Records are never rewritten;
a changed decision gets a new record that supersedes the old one.

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
