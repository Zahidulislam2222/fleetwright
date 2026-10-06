# Roadmap

Fleetwright is built in ten phases. Each phase ends with written acceptance criteria, automated
gates (tests, types, lint, security scans, build), a real end-to-end check and an independent
review. Dates are not promised; order is.

## Done

| Phase | What shipped |
|---|---|
| 1. Foundation and design | Workspace, typed configuration boundary, landing page, console design prototype with every screen and state, live site, security headers |
| 2. Mock load board | The fictitious test target with login, emailed codes, captcha, live feed, first-booker-wins booking, adversity switches and a ground-truth log |
| 3. Coordination core | Schema with row-level security, claim state machine with fencing tokens, Redis Streams, transactional outbox; 200 × 10,000 load test with zero duplicates |
| 4. Browser runtime | Worker processes with many contexts, session vault with envelope encryption, emailed and manual one-time codes, proxy and captcha adapters, failure evidence |
| 5. Live engine | Watchers, dispatcher with hot-reloaded filters and schedules, actors (HTTP and click), reconciler, cells with live tenant moves, per-stage latency |

## In progress

| Phase | Scope |
|---|---|
| 6. Live console | **Shipped and live:** `/v1` API (OpenAPI contract), sign-in with password + TOTP, roles (owner, operator, viewer, demo), CSRF protection, audit log, anonymous read-only demo view with personal data masked, capped public demo controls with auto-reset, live updates over server-sent events, console wired to real data, single-server production deploy. **Remaining:** metrics and alerting |

## Next

| Phase | Scope |
|---|---|
| 7. Crawler worker | Crawl jobs as data, per-domain politeness, robots.txt and TDM opt-out respected by default, retries and dead-letter, change detection, data-quality alarms, SSRF egress guard, personal-data controls |
| 8. Local AI browser agent | A lightweight local app that works across browser tabs with a local or cloud model; human approval before any publish, send, purchase or delete; prompt-injection defences; AI-content labelling |
| 9. Hardening and scale proof | OWASP ASVS Level 2 checklist, dynamic scanning, container hardening, SBOM and signed images; 50- and 70-context one-hour fleet runs; gateway load test; capacity model with measured numbers; restore drill; cloud reference architecture (infrastructure as code, plan only) |
| 10. Public demo and documentation | Full engine demo on the public site with capped controls, case study, demo videos, final documentation pass |

## Scale milestones

See [scaling](scaling/README.md) for the stages. In short:

1. Single server with backups and monitoring (≈ 75 contexts per 8 GB node).
2. Cloud, one region, multi-AZ: **99.9% availability target**.
3. Many cells: 10,000+ contexts.
4. Gateway fleet and CDN: **1M concurrent connected console sessions** (target, to be load-tested).

## Known limitations (today)

- Blocked responses (401/403/429) mark the claim `FAILED`; they are not re-queued to another account.
- Per-account rate pacing and routing by account group are configured but not yet enforced by the
  dispatcher.
- Detections in flight at the exact moment a tenant moves between cells may be dropped (claims
  already queued are handed over safely).
- Re-planning slots after a tenant change restarts all slots in that worker process.
- The public site runs on a single server, so a server failure takes it offline; there is no backup
  job yet (the demo data is re-created by the seed job). A restore drill is part of Phase 9.
- No metrics or alerting yet; health is checked by container health checks and the deploy smoke test.
- The audit entry for a console action is written in its own transaction right after the action, so
  a crash between the two could lose the entry.
- A revoked session keeps an already-open live-update stream until that stream reconnects.
- The Content Security Policy still allows inline styles and scripts (`'unsafe-inline'`).
- The refetch load caused by live updates with many open consoles has not been load-tested.
- Tests share the local development databases (an isolated test database is planned).
