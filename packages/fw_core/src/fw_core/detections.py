"""Durable raw-detection mailbox: Redis is delivery, PostgreSQL is the authority."""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

DETECTED_TOPIC = "detection.dispatch"
FIELDS = frozenset({"key", "job", "published_at", "seen_at", "offset_ms", "watcher"})


def record(fields: dict[str, str]) -> dict[str, Any]:
    if set(fields) != FIELDS or not fields["key"] or not isinstance(json.loads(fields["job"]), dict):
        raise ValueError("invalid detection protocol fields")
    return {"payload": fields, "identity": hashlib.sha256(fields["key"].encode()).hexdigest()}


async def persist_many(conn: AsyncConnection, tenant: UUID, fields: list[dict[str, str]]) -> int:
    """Atomically persist a caller-bounded batch; first authoritative payload wins on replay."""
    by_identity: dict[str, dict[str, Any]] = {}
    for value in fields:
        item = record(value)
        by_identity.setdefault(item["identity"], item)
    records = list(by_identity.values())
    if not records:
        return 0
    inserted = await conn.execute(
        text("""INSERT INTO outbox(tenant_id,topic,payload,detection_key)
             SELECT :t,:topic,r.payload,r.identity FROM jsonb_to_recordset(CAST(:rows AS jsonb))
               AS r(payload jsonb,identity text)
             ON CONFLICT(tenant_id,detection_key) WHERE topic='detection.dispatch' DO NOTHING RETURNING id"""),
        {"t": tenant, "topic": DETECTED_TOPIC, "rows": json.dumps(records)},
    )
    return len(inserted.all())


async def persist(conn: AsyncConnection, tenant: UUID, fields: dict[str, str]) -> int:
    """Idempotent per tenant/job, before any transport publish; no external action occurs here."""
    identity = record(fields)["identity"]
    inserted = await conn.scalar(
        text("""INSERT INTO outbox(tenant_id,topic,payload,detection_key)
             VALUES(:t,:topic,CAST(:p AS jsonb),:key)
             ON CONFLICT(tenant_id,detection_key) WHERE topic='detection.dispatch' DO NOTHING RETURNING id"""),
        {"t": tenant, "topic": DETECTED_TOPIC, "p": json.dumps(fields), "key": identity},
    )
    if inserted is not None:
        return int(inserted)
    existing = await conn.scalar(
        text("SELECT id FROM outbox WHERE tenant_id=:t AND topic=:topic AND detection_key=:key"),
        {"t": tenant, "topic": DETECTED_TOPIC, "key": identity},
    )
    if existing is None:
        raise RuntimeError("concurrent detection record unavailable")
    return int(existing)


async def pending(conn: AsyncConnection, tenant: UUID, identity: int) -> dict[str, Any] | None:
    """Locks authoritative payload until the filter/claim decision and consume marker commit."""
    payload = await conn.scalar(
        text("""SELECT payload FROM outbox WHERE tenant_id=:t AND id=:id AND topic=:topic
             AND consumed_at IS NULL FOR UPDATE"""),
        {"t": tenant, "id": identity, "topic": DETECTED_TOPIC},
    )
    return None if payload is None else dict(payload)


async def consume(conn: AsyncConnection, tenant: UUID, identity: int) -> None:
    await conn.execute(
        text("UPDATE outbox SET consumed_at=clock_timestamp() WHERE tenant_id=:t AND id=:id AND topic=:topic"),
        {"t": tenant, "id": identity, "topic": DETECTED_TOPIC},
    )
