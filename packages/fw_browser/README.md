# fw_browser

Browser-side building blocks for workers (Playwright).

| Module | Purpose |
|---|---|
| `login.py` | Sign-in flow: password, then one-time code, then optional captcha, with timeouts |
| `otp.py` | One-time-code adapters (Mailpit API, IMAP) |
| `captcha.py` | Captcha detection; the only solver is for the owned board's own arithmetic captcha. Real targets go to a human operator |
| `proxy.py` | Proxy pool: sticky per account, rotation after repeated blocks, health scoring (local provider by default) |
| `profiles.py` | Stable browser profiles per account group (locale, time zone, viewport) |
| `evidence.py` | Failure evidence (trace chunk + screenshot) with retention pruning |
| `workflows.py` | Owned-origin form actions and bounded, read-only receipt matching; generic authentication independent of freight fields |

Tests: `uv run pytest packages/fw_browser`.

Workflow pages restrict destination origin, block service workers and close WebSockets. Receipt
checks bind the exact account and payload; missing evidence remains inconclusive. Real browser
proof is in the coordinator workflow suite. See the
[workflow runbook](../../docs/operations/reliable-browser.md).

Release operation and limits: [deployment](../../docs/operations/deployment.md) · [maintenance](../../docs/maintenance.md).

## Adding a destination

Obtain explicit authorization and define authentication, account identity, permitted origin,
preconditions, action fields and matching receipt semantics in maintained contracts. Test expired
sessions, changed layouts, rate limits, ambiguous acknowledgements and interruption after acceptance.
Missing receipt data must remain inconclusive unless the destination contract proves otherwise.

The built-in challenge solver is confined to the owned arithmetic fixture. Additional proxy or
challenge services are not enabled merely by changing a URL; review destination policy, credentials,
privacy and cost before integration. See [target onboarding](../../docs/legal/acceptable-use.md).
