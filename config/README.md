# Configuration data

Validated YAML product data, loaded at start-up. Environment settings (URLs, secrets, timeouts)
are **not** here; they come from environment variables (see
[configuration](../docs/operations/configuration.md)).

| File | Contents |
|---|---|
| `targets.yaml` | Target sites: login selectors, captcha, feed page, booking button, API paths, blocked statuses |
| `browser.yaml` | Browser profiles and which account group uses which |
| `proxy.yaml` | Proxy providers (mock provider by default) |
| `board_catalogue.yaml` | Invented lanes, equipment and rates for the mock board |
