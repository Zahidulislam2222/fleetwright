"""Control loops without browsers: the dispatcher turns detections into exactly one claim per job,
applies filters (with immediate reload on change), and a moved tenant is handed over cleanly."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
from pydantic_settings import SettingsConfigDict
from redis.asyncio import Redis
from sqlalchemy import text

from dbkit import Db, new_tenant
from fw_coordinator.control import Control, move_tenant
from fw_core.db import system_tx, tenant_tx
from fw_core.settings import ClaimSettings, ControlSettings, RedisSettings, _Base
from fw_core.targets import load_targets
from fw_core.vault import Vault
from fw_queue import client, keys, streams

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[3]


class RedisOnly(_Base):
    model_config = SettingsConfigDict(
        env_prefix="FW_", env_nested_delimiter="__", extra="ignore", env_file=ROOT / ".env"
    )
    redis: RedisSettings


async def new_cell(db: Db) -> str:
    cell = f"t-{uuid4().hex[:12]}"
    async with system_tx(db.app) as conn:
        await conn.execute(
            text("INSERT INTO cells (id, name, region, capacity) VALUES (:i, :i, 'test', 8)"), {"i": cell}
        )
    return cell


@asynccontextmanager
async def running_control(db: Db, cell: str, redis_cell: str = "cell-a") -> AsyncIterator[Control]:
    cfg = RedisOnly().redis  # type: ignore[call-arg]
    core, cell_redis = client.core(cfg), client.cell(cfg, redis_cell, block_ms=200)
    http = httpx.AsyncClient(timeout=5)
    control = Control(
        cfg=ControlSettings(cell=cell, tenant_refresh_s=0.3, read_block_ms=200),
        claims_cfg=ClaimSettings(filter_reload_s=60, reconcile_interval_s=0.3, outbox_poll_ms=100),
        engine=db.app,
        core=core,
        cell_redis=cell_redis,
        vault=Vault(db.envelope),
        targets=load_targets(ROOT / "config"),
        base_urls={},
        http=http,
    )
    await control.start()
    try:
        yield control
    finally:
        await control.stop()
        await http.aclose()
        await core.aclose()
        await cell_redis.aclose()


async def add_filter(db: Db, tenant: UUID, **kw: Any) -> UUID:
    fid = uuid4()
    async with tenant_tx(db.app, tenant) as conn:
        await conn.execute(
            text("INSERT INTO filters (tenant_id, id, name, min_rate_usd) VALUES (:t, :i, :n, :r)"),
            {"t": tenant, "i": fid, "n": kw.get("name", "all"), "r": kw.get("min_rate_usd", 0)},
        )
    return fid


async def detect(redis: Redis, tenant: UUID, ref: str, rate: int, watcher: str = "w1") -> None:
    job = {
        "ref": ref,
        "origin": "Dallas, TX",
        "destination": "Memphis, TN",
        "equipment": "Van",
        "weight_lb": 1,
        "rate_usd": rate,
    }
    await streams.add(
        redis,
        keys.detected_stream(tenant),
        {
            "key": ref,
            "job": json.dumps(job),
            "published_at": "",
            "seen_at": "2026-10-05T12:00:00+00:00",
            "offset_ms": "",
            "watcher": watcher,
        },
        1000,
    )


async def until(check: Callable[[], Any], what: str, timeout_s: float = 10) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_s
    while not await check():
        assert loop.time() < deadline, f"timed out waiting for: {what}"
        await asyncio.sleep(0.1)


async def claim_count(db: Db, tenant: UUID) -> int:
    async with tenant_tx(db.app, tenant) as conn:
        return int((await conn.execute(text("SELECT count(*) FROM claims"))).scalar_one())


async def test_one_claim_per_job_filters_and_hot_reload(db: Db) -> None:
    cell = await new_cell(db)
    tenant = await new_tenant(db, cell)
    fid = await add_filter(db, tenant, min_rate_usd=1500)
    async with running_control(db, cell) as control:
        for watcher in ("w1", "w2", "w3"):  # three watchers see the same job
            await detect(control.cell_redis, tenant, "L-A", 2000, watcher)
        await detect(control.cell_redis, tenant, "L-B", 1000)  # below the filter
        await until(lambda: _done(control, 4), "four detections handled")
        assert await claim_count(db, tenant) == 1
        assert control.stats["skipped_duplicate"] == 2 and control.stats["skipped_no_filter"] == 1
        act = await control.cell_redis.xrange(keys.act_stream(tenant))
        assert len(act) == 1, "the claim was published to the act stream straight after its commit"

        async with tenant_tx(db.app, tenant) as conn:
            await conn.execute(text("UPDATE filters SET min_rate_usd = 2500 WHERE id = :i"), {"i": fid})
        await control.core.publish(keys.filters_channel(tenant), "changed")
        await until(lambda: _stat(control, "filter_reloads", 1), "filter reload notification")
        await detect(control.cell_redis, tenant, "L-C", 2000)
        await until(lambda: _stat(control, "skipped_no_filter", 2), "new rule applied")
        assert await claim_count(db, tenant) == 1
        await control.cell_redis.delete(keys.act_stream(tenant), keys.detected_stream(tenant))


async def test_tenant_move_hands_over_queued_claims(db: Db) -> None:
    cell_a, cell_b = await new_cell(db), await new_cell(db)
    tenant = await new_tenant(db, cell_a)
    await add_filter(db, tenant)
    async with running_control(db, cell_a, "cell-a") as a, running_control(db, cell_b, "cell-b") as b:
        await detect(a.cell_redis, tenant, "L-M1", 2000)
        await until(lambda: claim_count_is(db, tenant, 1), "claim queued in cell A")
        moved = await move_tenant(db.app, tenant, cell_b, "test")
        assert moved == 1, "the queued claim is dispatched again for the new cell"
        await until(lambda: _gone(a, tenant), "cell A dropped the tenant")
        await until(lambda: _relayed_to(b, tenant), "cell B published the queued claim on its own Redis")
        assert await a.cell_redis.xlen(keys.act_stream(tenant)) == 1, "cell A published nothing after the move"
        await detect(b.cell_redis, tenant, "L-M2", 2000)
        await until(lambda: claim_count_is(db, tenant, 2), "cell B dispatches new detections")
        async with tenant_tx(db.app, tenant) as conn:
            cells = {r.cell_id for r in await conn.execute(text("SELECT cell_id FROM claims"))}
            audit = (
                await conn.execute(text("SELECT count(*) FROM audit_log WHERE action = 'tenant.move'"))
            ).scalar_one()
        assert cells == {cell_b} and audit == 1
        for r in (a.cell_redis, b.cell_redis):
            await r.delete(keys.act_stream(tenant), keys.detected_stream(tenant))


async def _done(control: Control, n: int) -> bool:
    s = control.stats
    return s["queued"] + s["skipped_duplicate"] + s["skipped_no_filter"] + s["skipped_existing_claim"] >= n


async def _stat(control: Control, name: str, n: int) -> bool:
    return control.stats[name] >= n


async def _gone(control: Control, tenant: UUID) -> bool:
    return tenant not in control.tenants


async def _relayed_to(control: Control, tenant: UUID) -> bool:
    return bool(await control.cell_redis.xlen(keys.act_stream(tenant)))


async def claim_count_is(db: Db, tenant: UUID, n: int) -> bool:
    return await claim_count(db, tenant) == n
