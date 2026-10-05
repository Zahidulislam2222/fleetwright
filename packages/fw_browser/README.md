# fw_browser

Browser-side building blocks for workers (Playwright).

| Module | Purpose |
|---|---|
| `login.py` | Sign-in flow: password, then one-time code, then optional captcha, with timeouts |
| `otp.py` | One-time-code adapters (Mailpit API, IMAP) |
| `captcha.py` | Captcha detection; the only solver is for the demo board's own arithmetic captcha. Real targets go to a human operator |
| `proxy.py` | Proxy pool: sticky per account, rotation after repeated blocks, health scoring (mock provider by default) |
| `profiles.py` | Stable browser profiles per account group (locale, time zone, viewport) |
| `evidence.py` | Failure evidence (trace chunk + screenshot) with retention pruning |

Tests: `uv run pytest packages/fw_browser`.
