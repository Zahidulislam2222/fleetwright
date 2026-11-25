# Owned workflow destinations

`apps/mockboard` (the package name is historical and kept for compatibility) serves the owned
freight exchange and the owned maintenance portal. They provide independent destination receipts
for authorized browser verification. The configured catalogue is owned test data; no commercial
freight is offered and no real carrier is involved.

Current release: `20261125-assistant-rc5` ([25 November 2026 record](../../docs/releases/2026-11-25.md)).
That release added the collapsed visitor guide described below; booking, receipts and fault
behaviour are unchanged.

## What it does

The freight exchange includes password/email-code login, session cookies, live loads, first-booker
booking and ground-truth attempt logs. Adversity controls inject 429/5xx, delays, lost responses,
layout changes, competing bookings and session expiry. Owned arithmetic challenges support login
testing; this is not a third-party challenge bypass service.

The maintenance portal uses different fields and CSRF-protected request creation, scoped to the
authenticated account. Receipt checks establish exact account/payload matches.

| Endpoint | Purpose |
|---|---|
| `/login`, `/otp`, `/logout` | Destination authentication |
| `/loads`, `/api/loads` | Freight feed |
| `/api/loads/{ref}/book`, `/api/bookings` | Booking and receipts |
| `/portal`, `/api/portal/requests` | Maintenance form, creation and receipts |
| `/watch`, `/api/public/recent` | Read-only destination activity |
| `/admin/*` | Private bearer-authorized accounts, faults, ground truth and administration |
| `/healthz` | Health |

## Visitor guide

Every exchange page carries a short banner and a collapsed `<details>` guide that explains, for
clients and developers visiting the page, what the exchange is: who operates it, how loads appear,
how Fleetwright's workers sign in and compete with rival bots, which faults can be switched on and
where to watch the fleet. It is closed by default, so browser automation sees the same page as
before. When `FW_BOARD__CONSOLE_URL` is set, the guide shows the console address as text with the
label "Watch the fleet and ask its AI help assistant in the Fleetwright console"; when unset, that
line is hidden. The copy lives under `branding.guide` in
[`config/board_catalogue.yaml`](../../config/board_catalogue.yaml), and
`tests/test_board.py` checks that the guide is present and closed on the login and activity pages.

## Run and configure

Run `uv run uvicorn --factory mockboard.app:create_app --host 127.0.0.1 --port 8100`; match the
configured bind/client ports if changed. Product data lives in `config/board_catalogue.yaml` and
`config/workflows.yaml`; secrets, timeouts, limits and the console address use typed
`FW_BOARD__*` settings (`BoardSettings` in `fw_core.settings`).
See [local setup](../../docs/operations/local-development.md), [workflow verification](../../docs/operations/reliable-browser.md)
and [acceptable use](../../docs/legal/acceptable-use.md).

## Adapter acceptance boundary

Destination receipts are independent of Fleetwright's claim/job tables. Use them to compare account,
action identity and exact payload when testing response loss, competing actors or process death.
Administrative endpoints require the configured private token. Keep these destinations and account
credentials isolated from customer environments; a passing owned contract does not authorize a new
website or establish its idempotency behavior.

The paginated catalogue feeds the separately supervised crawler. Its configured alternate layout
exercises extraction/quality failure; it is independent of the live freight feed. See the
[crawler guide](../../docs/operations/crawler.md) and [test evidence](../../docs/testing.md).

## Verification ownership and data handling

The operator controls these destinations and their maintained catalogue. Keep verification account
pools separate from execution slots and compare receipts against the exact approved account/input
fingerprint. Exercise expiry, changed layout and lost acknowledgement without contacting an
unapproved external service. Resetting a destination never resolves an uncertain accepted action.

Account credentials, raw administrative results and database archives remain private. Apply the
[data lifecycle](../../docs/security/data-lifecycle.md) to exports and retention, and the
[onboarding checklist](../../docs/legal/commercial-readiness.md) before introducing a customer target.
