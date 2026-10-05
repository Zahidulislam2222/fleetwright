"""Phase 3: Redis Streams consumer groups (reclaim from dead consumers, dead-letter stream), the
outbox relay, and the scale rule that every tenant key carries a `{tenant}` hash tag."""

from __future__ import annotations

import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic_settings import SettingsConfigDict
from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError
from sqlalchemy import text

from dbkit import Db, new_tenant
from fw_core import claims
from fw_core.db import tenant_tx
from fw_core.settings import RedisSettings, _Base
from fw_queue import client, keys, outbox, streams

ROOT = Path(__file__).resolve().parents[3]


class RedisTestSettings(_Base):
    model_config = SettingsConfigDict(
        env_prefix="FW_", env_nested_delimiter="__", extra="ignore", env_file=ROOT / ".env"
    )
    redis: RedisSettings


@pytest.fixture
async def redis() -> AsyncIterator[Redis]:
    r = client.cell(RedisTestSettings().redis, "cell-a")  # type: ignore[call-arg]
    yield r
    await r.aclose()


def test_every_tenant_key_has_a_hash_tag() -> None:
    t = uuid4()
    for key in (
        keys.detected_stream(t),
        keys.act_stream(t),
        keys.dead_letter(keys.act_stream(t)),
        keys.job_seen(t, "L-1"),
        keys.events_channel(t),
        keys.filters_channel(t),
        keys.manual_otp(t, uuid4()),
        keys.worker_command(t, "w1"),
    ):
        assert re.search(r"\{" + str(t) + r"\}", key), key


@pytest.mark.integration
async def test_dead_consumer_messages_are_reclaimed_then_dead_lettered(redis: Redis) -> None:
    stream, group = f"fw:{{{uuid4()}}}:act", keys.ACTOR_GROUP
    await streams.ensure_group(redis, stream, group)
    await streams.ensure_group(redis, stream, group)  # idempotent
    await streams.add(redis, stream, {"claim_id": "c1"}, maxlen=1000)
    first = await streams.read(redis, [stream], group, "dead-worker", count=10, block_ms=100)
    assert [m.fields["claim_id"] for m in first] == ["c1"]
    # dead-worker never acks; another consumer takes the message over once it is idle
    reclaimed = await streams.reclaim(redis, stream, group, "live-worker", idle_ms=0, count=10, max_deliveries=3)
    assert [m.fields["claim_id"] for m in reclaimed] == ["c1"]
    for _ in range(3):  # keeps failing (delivered again and again) ...
        await streams.reclaim(redis, stream, group, "live-worker", idle_ms=0, count=10, max_deliveries=3)
    # ... until it exceeds max_deliveries and moves to the dead-letter stream
    assert await redis.xlen(keys.dead_letter(stream)) == 1
    assert (await redis.xpending(stream, group))["pending"] == 0
    await redis.delete(stream, keys.dead_letter(stream))


@pytest.mark.integration
async def test_outbox_relay_publishes_once_and_marks_rows(db: Db, redis: Redis) -> None:
    t = await new_tenant(db)
    now = datetime.now(UTC)
    async with tenant_tx(db.app, t) as conn:
        ids = [
            await claims.queue_claim(
                conn, t, claims.Detection(f"L-{n}", "A → B", 1000, now, now, 0.0, {}, None), "cell-a", "test"
            )
            for n in range(5)
        ]
    stream = keys.act_stream(t)
    assert await outbox.drain_tenant(db.app, redis, t, batch=100, maxlen=1000) == 5
    assert await outbox.drain_tenant(db.app, redis, t, batch=100, maxlen=1000) == 0, "published rows are not sent twice"
    entries = await redis.xrange(stream)
    assert sorted(e[1]["claim_id"] for e in entries) == sorted(str(i) for i in ids)
    async with tenant_tx(db.app, t) as conn:
        pending = (await conn.execute(text("SELECT count(*) FROM outbox WHERE published_at IS NULL"))).scalar_one()
    assert pending == 0
    await redis.delete(stream)


@pytest.mark.integration
async def test_outbox_rows_survive_a_redis_failure(db: Db) -> None:
    """If Redis is unreachable the relay's transaction rolls back and the rows stay pending."""
    t = await new_tenant(db)
    now = datetime.now(UTC)
    async with tenant_tx(db.app, t) as conn:
        await claims.queue_claim(
            conn, t, claims.Detection("L-x", "A → B", 1000, now, now, 0.0, {}, None), "cell-a", "test"
        )
    broken = Redis.from_url(
        "redis://127.0.0.1:1/0", socket_connect_timeout=0.5, socket_timeout=0.5
    )  # nothing listens on port 1
    with pytest.raises((RedisConnectionError, RedisTimeoutError, OSError)):  # refused (Linux) or timed out (Windows)
        await outbox.drain_tenant(db.app, broken, t, batch=100, maxlen=1000)
    await broken.aclose()
    async with tenant_tx(db.app, t) as conn:
        pending = (await conn.execute(text("SELECT count(*) FROM outbox WHERE published_at IS NULL"))).scalar_one()
    assert pending == 1
