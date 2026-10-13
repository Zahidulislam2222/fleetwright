# Configuration data

Validated YAML product data, loaded at start-up. Environment settings (URLs, secrets, timeouts)
are **not** here; they come from environment variables (see
[configuration](../docs/operations/configuration.md)).

| File | Contents |
|---|---|
| `targets.yaml` | Authentication selectors and identity API; freight-capable targets additionally define feed/booking paths |
| `browser.yaml` | Browser profiles and which account group uses which |
| `proxy.yaml` | Proxy providers (local provider by default) |
| `board_catalogue.yaml` | Invented lanes, equipment and rates for the owned freight board |
| `workflows.yaml` | Validated workflow inputs, action identity, browser forms, receipts and operator messages |
| `testing.yaml` | Isolated local test database names |
| `crawls.yaml` | Same-origin crawl seeds, extraction selectors, field/type limits and robots policy |
| `crawl_catalogue.yaml` | Invented records for the owned paginated crawler destination |
| `agent.yaml` | Maintained local-model templates, prompts, source/form/receipt contracts |
| `uptime.json` | Independent public HTTPS checks and bounded collector settings |
| `container-security-*.txt` | Reviewed image package patch/removal inputs |
| `release-signing-public.pem` | Public verification key; private signing material remains ignored |

Authentication-only targets require `name`, `login`, `captcha` (explicitly `null` when absent),
and `api.me` / `api.csrf_header`. They do not need freight endpoints. Legacy freight workers
select only complete freight target contracts, leaving service-only accounts available to
the general workflow runner. Both verified workflows currently use the owned board account.

See [maintenance](../docs/maintenance.md) for release and configuration review.
