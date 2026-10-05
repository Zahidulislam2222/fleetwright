# Gateway (`apps/gateway`)

**In progress.** The live-update gateway will push claim, worker and account events to connected
consoles over server-sent events. Each instance subscribes once per tenant channel in Redis and
fans out to its own clients, so instances scale horizontally and Redis load grows with tenants, not
viewers. See [scaling](../../docs/scaling/README.md).
