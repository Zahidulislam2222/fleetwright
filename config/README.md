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
| `demo.yaml` | Seed groups, filters/schedules, capped workspace controls and owned fault presets; filename is a stable compatibility identifier |
| `uptime.json` | Independent public HTTPS checks and bounded collector settings |
| `container-security-*.txt`, `web-security-apk.txt` | Reviewed exact image package patch/removal inputs |
| `release-signing-public.pem` | Public verification key; private signing material remains ignored |

Authentication-only targets require `name`, `login`, `captcha` (explicitly `null` when absent),
and `api.me` / `api.csrf_header`. They do not need freight endpoints. Legacy freight workers
select only complete freight target contracts, leaving service-only accounts available to
the general workflow runner. Both verified workflows currently use the owned board account.

See [maintenance](../docs/maintenance.md) for release and configuration review.

## Change control

Change destination scope, selectors, model prompts or allowed fields here, then validate against
current typed loaders and run affected real-flow tests. Workflow contract changes invalidate older
approval fingerprints. Do not repurpose an existing action identity for changed inputs.

Environment URLs/model IDs/storage paths/limits and secrets belong to typed settings, never copied
into control-flow modules. Public signing keys may be committed; private keys and actual credentials
must remain outside this directory. Keep local/VPS environment templates and the generated settings
schema synchronized. See [configuration ownership](../docs/operations/configuration.md).
