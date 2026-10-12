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

Authentication-only targets require `name`, `login`, `captcha` (explicitly `null` when absent),
and `api.me` / `api.csrf_header`. They do not need freight endpoints. Legacy freight workers
select only complete freight target contracts, leaving service-only accounts available to
the general workflow runner. Both verified workflows currently use the owned board account.

See [maintenance](../docs/maintenance.md) for release and configuration review.
