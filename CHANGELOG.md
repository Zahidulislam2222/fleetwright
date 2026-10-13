# Changelog

## Unreleased — crawler, local agent and operational recovery

- Durable tenant-scoped catalogue crawling, pinned HTTP/TLS destination checks, bounded physical
  request deadlines, JSON/CSS field contracts, quality alarms, retention and private console export.
- Standalone SQLite/Ollama browser application with three owned templates, exact human approvals,
  receipt reconciliation, isolated CDP support, HTTP/WebSocket guards and private POSIX state.
- Renewable observe-only monitoring, free public-repository independent uptime workflow and
  authenticated encrypted off-host archive recovery.
- Account-group and actual action cooldown enforcement, bounded cell-scoped workflow turns,
  graceful draining, static inline-script hashes and configurable offline-tested AWS reference.
- Container hardening, CycloneDX inventory and independently verifiable offline release provenance.
- Durable raw-detection replay across tenant handover, exact native app/web image identity checks,
  static-only compatible rollback and all-worker shutdown-grace verification.
- Professional component READMEs and product/integration/architecture/operations documentation,
  with current fixture evidence and explicit future scale/availability promotion criteria.

Full backend regression: 260 passed / 6 expected skips; subsequent agent UI correction separately
passed 25 tests. Both 50/70-context fixture hours and actual local-model templates passed. Latest
exact rehearsal is completion rc2 / source `847bcd40`; final release evidence is recorded separately.

## 2026-10-13 — reliable browser operations

Deployed as `20261013-reliable-browser-rc5`; [release evidence and boundaries](docs/releases/2026-10-13.md).

- Dedicated local MCP package for versioned freight-booking and maintenance-request workflows,
  with scoped revocable access, idempotent submissions and bounded paginated evidence.
- Exact-action human owner approval in the API and console; fenced durable execution, safe
  cancellation and receipt-based reconciliation after interrupted responses or process death.
- Fair persisted recovery rotation, authenticated operational gauges/alerts, verified database
  archives and fresh-cluster restoration tooling.
- Transactional console audit, durable intent for external actions, bounded idle-stream revocation,
  and isolated serialized test databases.
- Actual Codex MCP and real-browser verification; Claude verification deferred by the owner.
- Dedicated reserved workflow account pool, supervised workflow worker and protected host backup service templates.
- Complete public product/API/security/privacy/legal/operations/scaling/SLO/maintenance documentation and refreshed READMEs.
- Publication/configuration regressions and quality CI; final regression run147passed; unchanged contention benchmark passed separately in205.19s.

All notable changes, newest first. Version numbers follow the workspace version in
`pyproject.toml`.

## 0.2.0 (2026-10-05): the engine

### Added
- **owned freight board** (`apps/mockboard`): login with emailed one-time code, captcha, live feed with
  ground-truth publish times, first-booker-wins booking, booking-attempt audit, adversity switches
  (rate limits, errors, slow responses, lost acknowledgements, layout change, rival bots, forced
  session expiry, single session), admin API.
- **Coordination core**: schema with row-level security forced on every tenant table; claim state
  machine with fencing tokens and database-clock leases; Redis Streams with consumer groups,
  reclaim and dead-letter; transactional outbox and relay.
- **Worker runtime** (`apps/worker`, `packages/fw_browser`): one Chromium per process with many
  contexts; account holder leases; session vault with envelope encryption; emailed and manual
  one-time codes; proxy and captcha adapters (controlled providers); failure evidence with retention;
  graceful drain.
- **Live engine**: watchers on the feed's JSON responses; per-cell control process with dispatcher
  (filters, schedules, hot reload), outbox relay and reconciler; actors in HTTP or click mode;
  cells with live tenant moves; per-stage latency percentiles.
- **Documentation**: architecture, ADRs, scaling and capacity model, SLOs, threat model, security
  controls, US/EU compliance register, privacy, acceptable use, runbooks, roadmap.

### Verified
- 66 automated tests; 200 competitors × 10,000 jobs with zero duplicate bookings.

## 0.1.0 (2026-10-05): design and live site

### Added
- Landing page and console design interaction reference (every screen with ready, loading, empty, error and
  denied states; light and dark themes).
- Live static deployment with security headers.
