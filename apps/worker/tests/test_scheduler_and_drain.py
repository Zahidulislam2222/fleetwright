"""Cell-scoped fair pages and bounded graceful drain preserve recovery authority."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import text

from dbkit import Db, new_accounts, new_tenant
from fw_core import workflows as jobs
from fw_core.db import system_tx, tenant_tx
from fw_core.settings import WorkerSettings, WorkflowAppSettings, load
from fw_worker import accounts
from fw_worker.runtime import Fleet, Slot
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


@pytest.mark.integration
@pytest.mark.parametrize("delete_retired_tenant", [True, False])
async def test_deleted_retired_tenant_cannot_abort_current_account_and_context_drain(
    db: Db, delete_retired_tenant: bool, caplog: pytest.LogCaptureFixture
) -> None:
    cell = await new_cell(db)
    current_tenant, retired_tenant = await new_tenant(db, cell), await new_tenant(db, cell)
    await new_accounts(db, current_tenant, 1)
    fleet = object.__new__(Fleet)
    fleet.cfg = WorkerSettings(cell=cell, drain_timeout_s=0.01)
    fleet.engine = db.worker
    fleet.process_id = "test-drain-" + uuid4().hex
    fleet.browser = SimpleNamespace(is_connected=lambda: True)
    fleet.stopping = asyncio.Event()
    fleet.meter = SimpleNamespace(sample=lambda: (1, 0.0))
    current = Slot(fleet, fleet.process_id + "-g2-s0", current_tenant, "claimer", state="ready")
    retired = Slot(fleet, fleet.process_id + "-g1-s0", retired_tenant, "watcher", state="ready")
    current_context, retired_context = AsyncMock(), AsyncMock()
    current.context, retired.context = current_context, retired_context
    async with tenant_tx(db.worker, current_tenant) as conn:
        current.account = await accounts.acquire(conn, current_tenant, current.id, 30, ("demo-board",), ())
    assert current.account is not None
    fleet.slots, fleet._retired_slots = [retired, current], []
    await fleet._heartbeat()  # Both old and current generations have real FK-constrained rows.
    retired.retired = True
    fleet.slots, fleet._retired_slots = [current], [retired]
    if delete_retired_tenant:
        async with system_tx(db.owner) as conn:
            await conn.execute(text("DELETE FROM tenants WHERE id=:t"), {"t": retired_tenant})
    stalled = asyncio.create_task(asyncio.Event().wait(), name=current.id)
    heartbeat = asyncio.create_task(asyncio.Event().wait(), name="heartbeat")
    fleet._tasks = [stalled, heartbeat]
    try:
        await fleet.drain()
        assert stalled.cancelled() and heartbeat.cancelled()
        current_context.close.assert_awaited_once()
        retired_context.close.assert_awaited_once()
        assert current.account is None and current.context is None and retired.context is None
        async with tenant_tx(db.app, current_tenant) as conn:
            assert await conn.scalar(text("SELECT state FROM workers WHERE id=:i"), {"i": current.id}) == "stopped"
            assert await conn.scalar(text("SELECT count(*) FROM accounts WHERE holder_worker IS NOT NULL")) == 0
        async with tenant_tx(db.app, retired_tenant) as conn:
            retired_state = await conn.scalar(text("SELECT state FROM workers WHERE id=:i"), {"i": retired.id})
        assert retired_state is None if delete_retired_tenant else retired_state == "stopped"
        if delete_retired_tenant:
            assert "retired worker heartbeat row absent" in caplog.text
    finally:
        # Test hygiene only: a deliberately failing pre-fix drain must not leak asyncio tasks.
        for task in fleet._tasks:
            task.cancel()
        await asyncio.gather(*fleet._tasks, return_exceptions=True)


@pytest.mark.parametrize("extra_cleanup_failure", [False, True])
async def test_initial_heartbeat_failure_still_attempts_all_cleanup_and_reraises_original(
    extra_cleanup_failure: bool,
) -> None:
    fleet = object.__new__(Fleet)
    fleet.cfg = SimpleNamespace(drain_timeout_s=0.01)
    fleet.stopping = asyncio.Event()
    original = RuntimeError("test-heartbeat-unavailable")
    fleet._heartbeat = AsyncMock(side_effect=[original, None])
    contexts = [SimpleNamespace(close=AsyncMock()), SimpleNamespace(close=AsyncMock())]
    if extra_cleanup_failure:
        contexts[0].close.side_effect = RuntimeError("test-context-close-unavailable")
    fleet.slots, fleet._retired_slots = contexts, []
    stalled = asyncio.create_task(asyncio.Event().wait(), name="current-operation")
    heartbeat = asyncio.create_task(asyncio.Event().wait(), name="heartbeat")
    fleet._tasks = [stalled, heartbeat]
    try:
        with pytest.raises(RuntimeError, match="test-heartbeat-unavailable") as caught:
            await fleet.drain()
        assert caught.value is original
        assert stalled.cancelled() and heartbeat.cancelled()
        for slot in contexts:
            slot.close.assert_awaited_once_with(release=True)
        assert fleet._heartbeat.await_count == 2
        if extra_cleanup_failure:
            assert isinstance(caught.value.__cause__, ExceptionGroup)
            assert "test-context-close-unavailable" in str(caught.value.__cause__.exceptions[0])
    finally:
        for task in fleet._tasks:
            task.cancel()
        await asyncio.gather(*fleet._tasks, return_exceptions=True)
