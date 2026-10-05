"""Transactional outbox relay. State changes and their dispatch messages are written in one database
transaction (fw_core.claims); this relay copies pending outbox rows to the tenant's cell stream and
marks them published. A crash between XADD and the UPDATE re-sends the message later, which is
safe because consumers are idempotent (a claim lease can only be won once).

The dispatcher drains a tenant right after its own commit (low latency); a periodic loop catches
anything left behind (crash, Redis outage)."""

from __future__ import annotations

from uuid import UUID

from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from fw_core.claims import DISPATCH_TOPIC
from fw_core.db import tenant_tx
from fw_queue import keys, streams


async def drain_tenant(engine: AsyncEngine, redis: Redis, tenant_id: UUID, batch: int, maxlen: int) -> int:
    async with tenant_tx(engine, tenant_id) as conn:
        rows = (
            await conn.execute(
                text(
                    """SELECT id, topic, payload FROM outbox WHERE tenant_id = :t AND published_at IS NULL
                       ORDER BY id LIMIT :n FOR UPDATE SKIP LOCKED"""
                ),
                {"t": tenant_id, "n": batch},
            )
        ).all()
        if not rows:
            return 0
        for row in rows:
            if row.topic != DISPATCH_TOPIC:
                raise ValueError(f"unknown outbox topic {row.topic!r}")
            await streams.add(
                redis,
                keys.act_stream(tenant_id),
                {"claim_id": row.payload["claim_id"], "tenant_id": str(tenant_id), "outbox_id": str(row.id)},
                maxlen,
            )
        await conn.execute(
            text("UPDATE outbox SET published_at = clock_timestamp() WHERE tenant_id = :t AND id = ANY(:ids)"),
            {"t": tenant_id, "ids": [r.id for r in rows]},
        )
        return len(rows)


async def prune(engine: AsyncEngine, tenant_id: UUID, keep_s: int, batch: int) -> int:
    """Deletes published rows older than keep_s (bounded batch)."""
    async with tenant_tx(engine, tenant_id) as conn:
        result = await conn.execute(
            text(
                """DELETE FROM outbox WHERE (tenant_id, id) IN (
                     SELECT tenant_id, id FROM outbox WHERE tenant_id = :t AND published_at IS NOT NULL
                       AND published_at < clock_timestamp() - make_interval(secs => :keep) LIMIT :n)"""
            ),
            {"t": tenant_id, "keep": keep_s, "n": batch},
        )
        return int(result.rowcount)
