# Configuration

Fleetwright has **one configuration boundary**: `packages/fw_core/src/fw_core/settings.py`. Every
service reads typed settings from environment variables; nothing environment-specific is
hardcoded in business code (a test enforces this). See [ADR-008](../adr/0008-config-boundary.md).

## How variables are named

- Prefix `FW_`, groups separated by a double underscore: `FW_WORKER__CONTEXTS=4` sets
  `worker.contexts`.
- A local `.env` in the working directory is read automatically. In production, variables come
  from the environment or a secret manager.
- [`.env.example`](../../.env.example) lists every variable with safe example values and
  `__PLACEHOLDER__` markers for secrets. A test fails if a settings field and `.env.example` drift
  apart.
- `FWDEV_` variables are for the local Compose stack only (host ports, local database passwords).
- The VPS uses the templates in [`deploy/env/`](../../deploy/env/): `fleetwright.env.example` (all
  `FW_` settings, hostnames are Compose service names) and `postgres.env.example` (database role
  passwords). `deploy/make_vps_env.py <dir>` fills both with one set of fresh secrets. A test fails
  if `.env.example` and the VPS template define different `FW_` settings.

## Groups

| Group | Used by | Main settings |
|---|---|---|
| `FW_ENVIRONMENT`, `FW_CONFIG_DIR`, `FW_LOG_LEVEL` | All | `local`, `test`, `vps` or `aws`; folder with YAML product data |
| `FW_APP_DB__*`, `FW_WORKER_DB__*`, `FW_OWNER_DB__*`, `FW_BOARD_DB__*` | Per role | DSN (secret), pool size, overflow, pool timeout, statement timeout |
| `FW_REDIS__*` | Control, workers, API | Core URL, map of cell id → Redis URL, socket timeout |
| `FW_CLAIMS__*` | Control, workers | Lease TTL, maximum queued age, stream length cap, deliveries before dead-letter, reclaim idle time, outbox poll and batch, reconcile interval |
| `FW_CONTROL__*` | Control process | Cell id, tenant refresh interval, stream read block and count, grace before checking an `UNKNOWN` claim, duplicate window |
| `FW_WORKER__*` | Workers | Cell id, contexts per process, watcher count, headless, action mode (`http` or `click`), heartbeat, recycle after N actions, session refresh share, action/login timeouts, OTP wait, account hold, drain timeout |
| `FW_VAULT__*` | Control, workers | Master key (secret, base64) and key id |
| `FW_STORAGE__*` | Workers | Evidence folder and retention days |
| `FW_BOARD__*`, `FW_BOARD_CLIENT__*`, `FW_MAILPIT__*` | Mock board and its clients | Board admin token (secret), session and OTP lifetimes, feed rate and ceiling, internal and public URLs |
| `FW_AUTH__*` | Console API | Cookie names and flags, CSRF header, session and pending-MFA lifetimes, lockout (failures per account and per address range), password attempts per address range (right or wrong), concurrent password hashes, TOTP window |
| `FW_DEMO__*` | Console API | Public read-only view on/off, shared demo login (email, password, show its live code), run length and rate caps, reset delay, demo tenant |
| `FW_API__*`, `FW_GATEWAY__*` | Console API, live-update gateway | Bind host and port (required), proxy hops to trust for the client address, page sizes, worker staleness thresholds; gateway keepalive and client limits |
| `FW_SEED__*` | Seed job | Cell for the demo tenant, owner email, password and TOTP secret |

Built-in guards: for example, a worker refuses to start if `FW_CLAIMS__LEASE_TTL_MS` is not larger
than `FW_WORKER__ACTION_TIMEOUT_MS`, because an action could then outlive its lease.

## Product data (YAML in `config/`)

| File | Contents |
|---|---|
| `targets.yaml` | Each target site: login selectors, captcha, feed page, booking button, API paths, statuses that mean "blocked" |
| `browser.yaml` | Browser profiles (locale, time zone, viewport) and which account group uses which profile |
| `proxy.yaml` | Proxy providers (a mock provider ships by default): sticky sessions, rotation, health |
| `board_catalogue.yaml` | The mock board's lanes, equipment and rate ranges |

Everything is validated at start-up; an invalid file stops the service with a clear error.
