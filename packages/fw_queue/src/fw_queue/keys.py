"""Every Redis key and channel in one place. Tenant keys carry a `{tenant}` hash tag, so all of a
tenant's keys land in the same slot of a future Redis Cluster and tenants spread across slots."""

from __future__ import annotations

from uuid import UUID

PREFIX = "fw"


def _t(tenant_id: UUID | str) -> str:
    return f"{PREFIX}:{{{tenant_id}}}"


def detected_stream(tenant_id: UUID | str) -> str:
    return f"{_t(tenant_id)}:detected"


def act_stream(tenant_id: UUID | str) -> str:
    return f"{_t(tenant_id)}:act"


def dead_letter(stream: str) -> str:
    return f"{stream}:dlq"


def job_seen(tenant_id: UUID | str, job_key: str) -> str:
    """Fast-path de-duplication of detections. Only a filter in front of Postgres, never the authority."""
    return f"{_t(tenant_id)}:seen:{job_key}"


def events_channel(tenant_id: UUID | str) -> str:
    """Live updates for dashboards (core Redis pub/sub, fanned out by the gateway)."""
    return f"{_t(tenant_id)}:events"


def filters_channel(tenant_id: UUID | str) -> str:
    """Filter or schedule changed: dispatchers reload immediately."""
    return f"{_t(tenant_id)}:filters"


def manual_otp(tenant_id: UUID | str, account_id: UUID | str) -> str:
    return f"{_t(tenant_id)}:otp:{account_id}"


def worker_command(tenant_id: UUID | str, worker_id: str) -> str:
    return f"{_t(tenant_id)}:cmd:{worker_id}"


DISPATCHER_GROUP = "dispatchers"
ACTOR_GROUP = "actors"
