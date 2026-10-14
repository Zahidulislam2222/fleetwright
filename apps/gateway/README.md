# Live-update gateway

Authorized server-sent events for connected Fleetwright consoles. Each process subscribes to
tenant channels and fans out to its connected clients. It checks session authorization before
updates and while idle at `FW_GATEWAY__REVOCATION_CHECK_S`; revoked/expired sessions close within
that configured interval. Connection counts and keepalive settings are bounded.

Run `uv run python -m fw_gateway` from the workspace. Bind/Redis/session configuration comes from
typed settings and the private environment. Integration tests include idle-stream revocation.
The service does not prove million-session capacity: slow-consumer/reconnect/refetch load and
gateway density require the [scaling validation ladder](../../docs/scaling/README.md).
See [configuration](../../docs/operations/configuration.md) and [SLOs](../../docs/scaling/slo.md).

## Client contract and operation

The same-origin edge exposes `/v1/stream`. Events invalidate cached console data; clients refetch
through the authorized API rather than treating an event as a complete durable record. Keep
connection caps, heartbeat/revocation checks and refetch coalescing aligned with typed settings
and maintained dashboard data. Disconnect slow or expired consumers within the configured bounds.

For failures, inspect Redis connectivity, current authorization and reconnect behavior before
increasing limits. Measure fan-out, reconnect storms, slow clients and database refetch separately.
See [API integration](../../docs/integrations.md), [runbooks](../../docs/operations/runbooks.md)
and [verification](../../docs/testing.md).

## Capacity promotion and incident evidence

Before increasing connection caps, record authorized tenant/session population, active request
rate, delivered invalidations, outbound queue memory and reconnect/refetch amplification. Measure
p95/p99 delivery and revocation latency with slow readers and a skewed tenant. Include a cold
cache and loss of a gateway replica in each proposed tier's acceptance run.

Keep private API snapshots outside public caches. PostgreSQL remains the source for resynchronizing
state after a lost hint; notification delivery does not authorize an action. The
[validation plan](../../docs/scaling/validation-plan.md) and
[service ownership matrix](../../docs/operations/service-ownership.md) define promotion and recovery.
