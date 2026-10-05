# fw_queue

Messaging on Redis.

| Module | Purpose |
|---|---|
| `keys.py` | Every Redis key in one place, with `{tenant}` hash tags so a cell can become a Redis Cluster |
| `streams.py` | Streams with consumer groups, `XAUTOCLAIM` reclaim, dead-letter after N deliveries |
| `outbox.py` | Relay that publishes outbox rows, after checking the tenant still belongs to this cell |
| `client.py` | Redis clients for the core and each cell |

Tests: `uv run pytest packages/fw_queue`.
