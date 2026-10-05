# Changelog

All notable changes, newest first. Version numbers follow the workspace version in
`pyproject.toml`.

## 0.2.0 (2026-10-05): the engine

### Added
- **Mock load board** (`apps/mockboard`): login with emailed one-time code, captcha, live feed with
  ground-truth publish times, first-booker-wins booking, booking-attempt audit, adversity switches
  (rate limits, errors, slow responses, lost acknowledgements, layout change, rival bots, forced
  session expiry, single session), admin API.
- **Coordination core**: schema with row-level security forced on every tenant table; claim state
  machine with fencing tokens and database-clock leases; Redis Streams with consumer groups,
  reclaim and dead-letter; transactional outbox and relay.
- **Worker runtime** (`apps/worker`, `packages/fw_browser`): one Chromium per process with many
  contexts; account holder leases; session vault with envelope encryption; emailed and manual
  one-time codes; proxy and captcha adapters (mock providers); failure evidence with retention;
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
- Landing page and console design prototype (every screen with ready, loading, empty, error and
  denied states; light and dark themes).
- Live static deployment with security headers.
