"""Time helpers. Lease and expiry decisions use the database clock; this is for display and stamps
taken outside the database (e.g. a watcher's seen_at), which record their clock offset."""

from __future__ import annotations

from datetime import UTC, datetime


def utcnow() -> datetime:
    return datetime.now(UTC)


def iso(dt: datetime | None) -> str | None:
    return None if dt is None else dt.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")
