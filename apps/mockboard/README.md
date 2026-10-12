# Owned workflow destinations

The owned freight exchange and maintenance portal provide independent destination receipts for
authorized browser verification. Catalogue records do not offer commercial freight. The historical
package/path name remains stable for compatibility.

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

Run `uv run uvicorn --factory mockboard.app:create_app --host 127.0.0.1 --port 8100`; match the
configured bind/client ports if changed. Product data lives in `config/board_catalogue.yaml` and
`config/workflows.yaml`; secrets/timeouts/limits use typed settings.
See [local setup](../../docs/operations/local-development.md), [workflow verification](../../docs/operations/reliable-browser.md)
and [acceptable use](../../docs/legal/acceptable-use.md).
