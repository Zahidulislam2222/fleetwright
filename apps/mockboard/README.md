# Mock load board (`apps/mockboard`)

A **fictitious** freight load board, built so the fleet can be tested end to end without touching
any real site. It is clearly labelled as a demo and does not imitate any real board.

## What it does

- Sign-in with password, then a one-time code sent by email (Mailpit locally), then a session
  cookie with a configurable lifetime.
- A live feed of invented loads at a configurable rate (up to 100 per second for stress runs).
  Every load records its **ground-truth publish time**.
- Booking: first booker wins; every attempt, including double-booking attempts, is logged.
- A simple arithmetic captcha after too many fast requests.
- **Adversity switches**, changed live through the admin API: rate limits (429), random 5xx,
  slow responses, lost acknowledgements (booked, but answers 500), layout change, rival bots that
  book loads first, forced session expiry, single-session mode, captcha threshold.

## Endpoints

| Path | Purpose |
|---|---|
| `GET /login`, `POST /login`, `GET/POST /otp`, `POST /logout` | Sign-in flow |
| `GET /loads` | Feed page (polls `/api/loads`) |
| `GET /api/me`, `GET /api/loads`, `POST /api/loads/{ref}/book`, `GET /api/bookings` | JSON API used by the page (booking needs the CSRF token) |
| `GET/POST /captcha` | Captcha challenge |
| `GET /watch`, `GET /api/public/recent` | Public read-only view of recent activity |
| `/admin/*` | Settings, accounts, forced expiry, ground truth, duplicate audit, reset (bearer token) |
| `GET /healthz` | Health check |

## Run

```bash
uv run uvicorn --factory mockboard.app:create_app --host 127.0.0.1 --port 8100
uv run pytest apps/mockboard        # starts its own board instance
```

Settings: `FW_BOARD__*` and `FW_BOARD_DB__*` (see [configuration](../../docs/operations/configuration.md)).
Lanes, equipment and rates come from `config/board_catalogue.yaml`.
