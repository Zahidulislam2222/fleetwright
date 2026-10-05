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


# ---------------- control plane (core Redis, not tenant-scoped) ----------------


def session(token_hash: str) -> str:
    """A signed-in console session (the cookie holds the token; only its hash is a key)."""
    return f"{PREFIX}:session:{token_hash}"


def user_sessions(user_id: UUID | str) -> str:
    """Set of a user's session hashes, so all of them can be revoked at once."""
    return f"{PREFIX}:user-sessions:{user_id}"


def mfa_pending(token_hash: str) -> str:
    return f"{PREFIX}:mfa:{token_hash}"


def login_failures(subject: str) -> str:
    """Failed sign-ins per email or per client address (sliding window counter)."""
    return f"{PREFIX}:login-fail:{subject}"


def totp_used(user_id: UUID | str) -> str:
    """Last accepted TOTP time step, so a code cannot be replayed."""
    return f"{PREFIX}:totp-used:{user_id}"


def demo_run() -> str:
    """The active public demo run (expires on its own; the reset loop restores idle settings)."""
    return f"{PREFIX}:demo:run"


def demo_changed() -> str:
    """Set when a demo visitor changes board adversity; cleared by the reset loop."""
    return f"{PREFIX}:demo:changed"
