"""Cell-scoped fair pages and bounded graceful drain preserve recovery authority."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import text

from dbkit import Db, new_tenant
from fw_core import workflows as jobs
from fw_core.db import system_tx
from fw_core.settings import WorkflowAppSettings, load
from fw_worker.runtime import Fleet
from fw_worker.workflows import Runner
from workerkit import new_cell


@pytest.mark.integration
async def test_scheduler_pages_only_its_cell_with_bounded_turns(db: Db, monkeypatch: pytest.MonkeyPatch) -> None:
    cell, other = await new_cell(db), await new_cell(db)
    tenants = sorted([await new_tenant(db, cell) for _ in range(3)])
    alien = await new_tenant(db, other)
    cfg = load(WorkflowAppSettings)
    cfg = cfg.model_copy(
        update={
            "worker": cfg.worker.model_copy(update={"cell": cell}),
            "workflows": cfg.workflows.model_copy(update={"tenant_batch": 2, "jobs_per_tenant": 1}),
        }
    )
    seen = []

    async def ready(_conn: object, tenant: object, limit: int) -> list[object]:
        assert limit == 1
        seen.append(tenant)
        return [uuid4()]

    monkeypatch.setattr(jobs, "ready_jobs", ready)
    runner = Runner(cfg, db.app, None, None, "test-scheduler")
    runner.run_one = AsyncMock(return_value=True)
    await runner.tick()
    assert seen == tenants[:2]
    await runner.tick()
    assert seen == tenants
    await runner.tick()  # exhaust/wrap cursor; no repeated admission during an empty page
    await runner.tick()
    assert seen == [*tenants, *tenants[:2]] and alien not in seen
    runner.stopping.set()
    before = runner.run_one.await_count
    await runner.tick()
    assert runner.run_one.await_count == before


async def test_drain_finishes_ready_tasks_cancels_stalled_tasks_and_releases_accounts() -> None:
    fleet = object.__new__(Fleet)
    fleet.cfg = SimpleNamespace(drain_timeout_s=0.05)
    fleet.stopping = asyncio.Event()
    fleet._heartbeat = AsyncMock()
    finite = asyncio.create_task(asyncio.sleep(0.01), name="finishing-slot")
    stalled = asyncio.create_task(asyncio.Event().wait(), name="stalled-slot")
    heartbeat = asyncio.create_task(asyncio.Event().wait(), name="heartbeat")
    fleet._tasks = [finite, stalled, heartbeat]
    fleet.slots = [SimpleNamespace(close=AsyncMock())]
    fleet._retired_slots = []
    await asyncio.wait_for(fleet.drain(), 1)
    assert fleet.stopping.is_set() and finite.done() and not finite.cancelled()
    assert stalled.cancelled() and heartbeat.cancelled()
    fleet.slots[0].close.assert_awaited_once_with(release=True)
    assert [call.kwargs["state_override"] for call in fleet._heartbeat.await_args_list] == ["draining", "stopped"]


@pytest.mark.integration
async def test_stale_directory_page_cannot_admit_after_tenant_move(db: Db, monkeypatch: pytest.MonkeyPatch) -> None:
    cell, other = await new_cell(db), await new_cell(db)
    tenant = await new_tenant(db, cell)
    cfg = load(WorkflowAppSettings)
    cfg = cfg.model_copy(update={"worker": cfg.worker.model_copy(update={"cell": cell})})
    take = AsyncMock()
    monkeypatch.setattr(jobs, "take", take)
    async with system_tx(db.app) as conn:
        await conn.execute(text("UPDATE tenant_cells SET cell_id=:c WHERE tenant_id=:t"), {"c": other, "t": tenant})
    runner = Runner(cfg, db.app, None, None, "old-cell-runner")
    assert not await runner.run_one(tenant, uuid4())
    take.assert_not_awaited()


async def test_forced_drain_after_replan_closes_retired_generation() -> None:
    fleet = object.__new__(Fleet)
    fleet.cfg = SimpleNamespace(drain_timeout_s=0.01)
    fleet.stopping = asyncio.Event()
    fleet._heartbeat = AsyncMock()
    fleet.generation = 0
    fleet.tenants = [uuid4()]
    old = SimpleNamespace(retired=False, state="ready", context=object(), account=object(), close=AsyncMock())
    fleet.slots = [old]
    fleet._retired_slots = []
    stalled = asyncio.create_task(asyncio.Event().wait(), name="retired-operation")
    fleet._tasks = [stalled]
    await fleet._apply_plan([])
    assert old.retired and fleet.slots == [] and fleet._retired_slots == [old]
    await asyncio.wait_for(fleet.drain(), 1)
    assert stalled.cancelled()
    old.close.assert_awaited_once_with(release=True)
    assert fleet._retired_slots == []
