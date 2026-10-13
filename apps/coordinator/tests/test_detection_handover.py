"""Durable raw detections survive unread streams, cell moves and crash boundaries."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock
from uuid import UUID

import httpx
import pytest
from sqlalchemy import event, text
from test_control import RedisOnly, add_filter, new_cell

from dbkit import Db, new_accounts, new_tenant
from fw_coordinator.control import Control, move_tenant
from fw_core import claims, detections
from fw_core.db import tenant_tx
from fw_core.settings import ClaimSettings, ControlSettings
from fw_core.targets import load_targets
from fw_core.vault import Vault
from fw_queue import client, keys, outbox, streams

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[3]


def fields(reference: str) -> dict[str, str]:
    return {
        "key": reference,
        "job": json.dumps({"ref": reference, "origin": "Dallas, TX", "destination": "Memphis, TN", "rate_usd": 2000}),
        "published_at": "",
        "seen_at": datetime.now(UTC).isoformat(),
        "offset_ms": "",
        "watcher": "owned-test",
    }


@asynccontextmanager
async def controls(db: Db) -> AsyncIterator[tuple[Control, Control, UUID]]:
    cfg = RedisOnly().redis
    cell_a, cell_b = await new_cell(db), await new_cell(db)
    tenant = await new_tenant(db, cell_a)
    await add_filter(db, tenant)
    core = client.core(cfg)
    a_redis, b_redis = client.cell(cfg, "cell-a"), client.cell(cfg, "cell-b")
    async with httpx.AsyncClient() as http:
        common = {
            "claims_cfg": ClaimSettings(detection_retry_s=0.1),
            "engine": db.app,
            "core": core,
            "vault": Vault(db.envelope),
            "targets": load_targets(ROOT / "config"),
            "base_urls": {},
            "http": http,
        }
        a = Control(cfg=ControlSettings(cell=cell_a), cell_redis=a_redis, **common)
        b = Control(cfg=ControlSettings(cell=cell_b), cell_redis=b_redis, **common)
        try:
            await a.refresh_tenants()
            await b.refresh_tenants()
            yield a, b, tenant
        finally:
            for redis in (a_redis, b_redis):
                await redis.delete(keys.detected_stream(tenant), keys.act_stream(tenant))
                await redis.aclose()
            await core.aclose()


async def persist(db: Db, tenant: UUID, reference: str) -> int:
    async with tenant_tx(db.worker, tenant) as conn:
        return await detections.persist(conn, tenant, fields(reference))


async def relay(control: Control, tenant: UUID) -> int:
    return await outbox.drain_tenant(control.engine, control.cell_redis, tenant, 100, 1000, control.cfg.cell, 0.1)


async def read(control: Control, tenant: UUID) -> list[streams.Message]:
    return await streams.read(
        control.cell_redis, [keys.detected_stream(tenant)], keys.DISPATCHER_GROUP, control.consumer, 100, 100
    )


async def count(db: Db, tenant: UUID) -> int:
    async with tenant_tx(db.app, tenant) as conn:
        return int(await conn.scalar(text("SELECT count(*) FROM claims")))


async def test_batched_mailbox_preserves_authority_and_tenant_isolation(db: Db) -> None:
    tenant, other = await new_tenant(db), await new_tenant(db)
    first = fields("batch-first")
    tampered = {**first, "job": json.dumps({"ref": "batch-first", "rate_usd": 1})}
    batch = [first, fields("batch-second"), tampered]
    async with tenant_tx(db.worker, tenant) as conn:
        assert await detections.persist_many(conn, tenant, batch) == 2
    async with tenant_tx(db.worker, tenant) as conn:
        assert await detections.persist_many(conn, tenant, [tampered, fields("batch-third")]) == 1
        stored = list((await conn.execute(text("SELECT payload FROM outbox ORDER BY id"))).scalars())
        assert len(stored) == 3
        assert stored[0] == first
        assert [item["key"] for item in stored] == ["batch-first", "batch-second", "batch-third"]
    async with tenant_tx(db.worker, other) as conn:
        assert await conn.scalar(text("SELECT count(*) FROM outbox")) == 0
        assert await detections.persist_many(conn, other, [first]) == 1
    async with tenant_tx(db.worker, tenant) as conn:
        assert await conn.scalar(text("SELECT count(*) FROM outbox")) == 3


async def test_batched_mailbox_is_atomic_on_invalid_input_and_commit_failure(db: Db) -> None:
    tenant = await new_tenant(db)
    with pytest.raises(ValueError):
        async with tenant_tx(db.worker, tenant) as conn:
            await detections.persist_many(conn, tenant, [fields("valid-before-invalid"), {"key": "invalid"}])
    with pytest.raises(RuntimeError, match="before-commit"):
        async with tenant_tx(db.worker, tenant) as conn:
            assert await detections.persist_many(conn, tenant, [fields("rolled-back-a"), fields("rolled-back-b")]) == 2
            raise RuntimeError("before-commit")
    async with tenant_tx(db.worker, tenant) as conn:
        assert await conn.scalar(text("SELECT count(*) FROM outbox")) == 0
        assert await detections.persist_many(conn, tenant, []) == 0


async def test_unread_old_stream_replays_to_current_cell_without_loss(db: Db) -> None:
    async with controls(db) as (a, b, tenant):
        ids = [await persist(db, tenant, "unread-a"), await persist(db, tenant, "unread-b")]
        assert await relay(a, tenant) == 2
        assert await a.cell_redis.xlen(keys.detected_stream(tenant)) == 2  # nobody read them
        assert await move_tenant(db.app, tenant, b.cfg.cell, "test") == 0
        await a.refresh_tenants()
        await b.refresh_tenants()
        assert tenant not in a.tenants and await relay(a, tenant) == 0
        assert await relay(b, tenant) == 2
        for message in await read(b, tenant):
            await b.dispatch(message)
        assert await count(db, tenant) == 2
        async with tenant_tx(db.app, tenant) as conn:
            assert (
                await conn.scalar(
                    text("SELECT count(*) FROM outbox WHERE id=ANY(:ids) AND consumed_at IS NOT NULL"), {"ids": ids}
                )
                == 2
            )
            assert set((await conn.execute(text("SELECT cell_id FROM claims"))).scalars()) == {b.cfg.cell}


async def test_inflight_old_dispatch_uses_new_cell_and_durable_payload(db: Db) -> None:
    async with controls(db) as (a, b, tenant):
        await persist(db, tenant, "authoritative")
        await relay(a, tenant)
        (inflight,) = await read(a, tenant)
        await move_tenant(db.app, tenant, b.cfg.cell, "test")
        await a.refresh_tenants()
        await b.refresh_tenants()
        inflight.fields.update(key="tampered-transport", job=json.dumps({"ref": "tampered-transport", "rate_usd": 0}))
        await a.dispatch(inflight)
        assert await count(db, tenant) == 1
        async with tenant_tx(db.app, tenant) as conn:
            row = (await conn.execute(text("SELECT target_job_key,cell_id FROM claims"))).one()
            assert (row.target_job_key, row.cell_id) == ("authoritative", b.cfg.cell)
        assert await a.cell_redis.xlen(keys.act_stream(tenant)) == 0
        assert await relay(b, tenant) == 1
        assert await b.cell_redis.xlen(keys.act_stream(tenant)) == 1


async def test_relay_crash_after_xadd_replays_without_duplicate_claim(db: Db, monkeypatch: pytest.MonkeyPatch) -> None:
    async with controls(db) as (a, _b, tenant):
        identity = await persist(db, tenant, "relay-crash")
        original = streams.add

        async def crash(*args, **kwargs):
            await original(*args, **kwargs)
            raise RuntimeError("test relay death after Redis acceptance")

        monkeypatch.setattr(streams, "add", crash)
        with pytest.raises(RuntimeError, match="relay death"):
            await relay(a, tenant)
        async with tenant_tx(db.app, tenant) as conn:
            assert await conn.scalar(text("SELECT published_at FROM outbox WHERE id=:id"), {"id": identity}) is None
        monkeypatch.setattr(streams, "add", original)
        assert await relay(a, tenant) == 1
        assert await a.cell_redis.xlen(keys.detected_stream(tenant)) == 2
        for message in await read(a, tenant):
            await a.dispatch(message)
        assert await count(db, tenant) == 1 and a.stats["skipped_duplicate"] == 1


async def test_dispatch_crash_rolls_back_claim_and_consume_then_retries(
    db: Db, monkeypatch: pytest.MonkeyPatch
) -> None:
    async with controls(db) as (a, _b, tenant):
        identity = await persist(db, tenant, "dispatch-crash")
        await relay(a, tenant)
        (message,) = await read(a, tenant)
        original = detections.consume
        monkeypatch.setattr(detections, "consume", AsyncMock(side_effect=RuntimeError("test precommit crash")))
        with pytest.raises(RuntimeError, match="precommit"):
            await a.dispatch(message)
        assert await count(db, tenant) == 0
        async with tenant_tx(db.app, tenant) as conn:
            assert await conn.scalar(text("SELECT consumed_at FROM outbox WHERE id=:id"), {"id": identity}) is None
            await conn.execute(
                text("UPDATE outbox SET published_at=clock_timestamp()-interval '1 minute' WHERE id=:id"),
                {"id": identity},
            )
        monkeypatch.setattr(detections, "consume", original)
        assert await relay(a, tenant) == 1
        for replay in await read(a, tenant):
            await a.dispatch(replay)
        assert await count(db, tenant) == 1


async def test_unconsumed_mailbox_survives_prune_and_tenant_isolation(db: Db) -> None:
    async with controls(db) as (a, _b, tenant):
        identity = await persist(db, tenant, "retention")
        assert identity == await persist(db, tenant, "retention")
        await relay(a, tenant)
        async with tenant_tx(db.app, tenant) as conn:
            await conn.execute(
                text("UPDATE outbox SET published_at=clock_timestamp()-interval '1 day' WHERE id=:id"), {"id": identity}
            )
        assert await outbox.prune(db.app, tenant, keep_s=1, batch=100) == 0
        alien = await new_tenant(db)
        async with tenant_tx(db.app, alien) as conn:
            assert await detections.pending(conn, alien, identity) is None
        (message,) = await read(a, tenant)
        await a.dispatch(message)
        assert await outbox.prune(db.app, tenant, keep_s=1, batch=100) == 1


async def test_move_failure_rolls_back_directory_claims_and_detection_replay(db: Db) -> None:
    async with controls(db) as (a, b, tenant):
        await persist(db, tenant, "queued")
        await relay(a, tenant)
        for message in await read(a, tenant):
            await a.dispatch(message)
        pending = await persist(db, tenant, "pending")
        await relay(a, tenant)

        def fail_audit(_conn, _cursor, statement, _parameters, _context, _many):
            if "INSERT INTO audit_log" in statement:
                raise RuntimeError("test move death before commit")

        event.listen(db.app.sync_engine, "before_cursor_execute", fail_audit)
        try:
            with pytest.raises(RuntimeError, match="move death"):
                await move_tenant(db.app, tenant, b.cfg.cell, "test")
        finally:
            event.remove(db.app.sync_engine, "before_cursor_execute", fail_audit)
        async with tenant_tx(db.app, tenant) as conn:
            assert (
                await conn.scalar(text("SELECT cell_id FROM tenant_cells WHERE tenant_id=:t"), {"t": tenant})
                == a.cfg.cell
            )
            assert set((await conn.execute(text("SELECT cell_id FROM claims"))).scalars()) == {a.cfg.cell}
            assert await conn.scalar(text("SELECT published_at FROM outbox WHERE id=:id"), {"id": pending}) is not None


async def test_old_actor_cannot_lease_claim_after_move(db: Db) -> None:
    async with controls(db) as (a, b, tenant):
        (account,) = await new_accounts(db, tenant, 1)
        await persist(db, tenant, "old-actor")
        await relay(a, tenant)
        for message in await read(a, tenant):
            await a.dispatch(message)
        await move_tenant(db.app, tenant, b.cfg.cell, "test")
        async with tenant_tx(db.app, tenant) as conn:
            identity = await conn.scalar(text("SELECT id FROM claims"))
        async with tenant_tx(db.worker, tenant) as conn:
            assert (
                await claims.lease(
                    conn,
                    tenant,
                    identity,
                    worker_id="old",
                    account_id=account,
                    ttl_ms=5000,
                    max_age_s=120,
                    cell_id=a.cfg.cell,
                )
                is None
            )
        async with tenant_tx(db.worker, tenant) as conn:
            assert await claims.lease(
                conn,
                tenant,
                identity,
                worker_id="new",
                account_id=account,
                ttl_ms=5000,
                max_age_s=120,
                cell_id=b.cfg.cell,
            )
