"""Phase 5 end to end: mock board -> watcher (real Chromium) -> dispatcher -> actors (real Chromium)
-> reconciler, under calm conditions and under chaos. The board's own audit is the judge:
- no load ever receives two booking attempts from the fleet;
- the set of jobs the database says we booked equals the set the board says our accounts booked
  (including bookings whose acknowledgement was lost, which only the reconciler can settle)."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest
from playwright.async_api import Browser, async_playwright
from sqlalchemy import text

from boardkit import Board
from dbkit import Db
from fw_coordinator.control import move_tenant
from fw_core.db import system_tx, tenant_tx
from fw_core.latency import stage_latency
from fw_worker.behaviours import claim, watch
from workerkit import (
    Tenant,
    add_filter,
    board_tenant,
    dump_tasks,
    new_cell,
    running_control,
    running_fleet,
    wait_for,
)

pytestmark = [pytest.mark.integration, pytest.mark.browser]
ENGINE = {"watcher": watch, "claimer": claim}


@pytest.fixture(scope="session")
async def browser() -> AsyncIterator[Browser]:
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        yield b
        await b.close()


async def db_now(db: Db) -> datetime:
    async with system_tx(db.app) as conn:
        return (await conn.execute(text("SELECT clock_timestamp()"))).scalar_one()  # type: ignore[no-any-return]


async def settle(db: Db, tenant: Tenant, timeout_s: float = 60) -> dict[str, int]:
    """Waits until nothing is in flight (LEASED, ACTING or UNKNOWN); returns counts by outcome."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_s
    while True:
        async with tenant_tx(db.app, tenant.id) as conn:
            rows = dict(
                (await conn.execute(text("SELECT coalesce(resolution, state), count(*) FROM claims GROUP BY 1"))).all()  # type: ignore[arg-type]
            )
        if not {"LEASED", "ACTING", "UNKNOWN"} & set(rows):
            return rows
        assert loop.time() < deadline, f"claims still in flight: {rows}"
        await asyncio.sleep(0.5)


async def our_bookings(db: Db, tenant: Tenant, since: datetime) -> set[str]:
    """Jobs published inside the test window that the database says we booked (the board's ground
    truth covers the same window; older jobs still on the feed can be booked too)."""
    async with tenant_tx(db.app, tenant.id) as conn:
        return {
            r.target_job_key
            for r in await conn.execute(
                text(
                    """SELECT target_job_key FROM claims WHERE published_at >= :s
                         AND (state = 'CONFIRMED' OR resolution IN ('confirmed', 'confirmed_by_late_actor'))"""
                ),
                {"s": since},
            )
        }


def board_says(board: Board, tenant: Tenant, since: datetime) -> tuple[set[str], dict[str, Any]]:
    users = {u for u, _ in tenant.accounts.values()}
    truth = board.admin.get("/admin/ground-truth", params={"since": since.isoformat(), "limit": 5000}).json()["loads"]
    ours = {load["ref"] for load in truth if load.get("booked_by") in users}
    audit = board.admin.get("/admin/audit/duplicates", params={"since": since.isoformat()}).json()
    return ours, audit


async def run_engine(
    db: Db, board: Board, browser: Browser, tmp_path: Path, seconds: float, accounts: int = 4, **fleet: Any
) -> tuple[Tenant, datetime, dict[str, int]]:
    tenant = await board_tenant(db, board, accounts)
    await add_filter(db, tenant.id)
    since = await db_now(db)
    async with running_control(db, board, tenant.cell) as control:
        async with running_fleet(db, board, browser, tenant.cell, tmp_path, ENGINE, contexts=accounts, **fleet) as f:
            await wait_for(lambda: all(s.state == "ready" for s in f.slots), 60, "fleet signed in")
            await asyncio.sleep(seconds)
            if os.environ.get("FW_TEST_DUMP_TASKS"):
                print(dump_tasks())
        outcome = await settle(db, tenant)
        print(f"\ncontrol stats: {dict(control.stats)}")
    return tenant, since, outcome


async def test_engine_books_every_matching_load_once(db: Db, board: Board, browser: Browser, tmp_path: Path) -> None:
    tenant, since, outcome = await run_engine(db, board, browser, tmp_path, seconds=15)
    ours, audit = board_says(board, tenant, since)
    confirmed = await our_bookings(db, tenant, since)
    assert audit["duplicate_loads"] == [], audit["duplicate_loads"][:5]
    assert confirmed == ours, (len(confirmed), len(ours), sorted(confirmed ^ ours)[:5])
    assert len(confirmed) >= 50, f"only {len(confirmed)} bookings in 15 s at 10 loads/s: {outcome}"
    async with tenant_tx(db.app, tenant.id) as conn:
        latency = {s.stage: s for s in await stage_latency(conn, tenant.id, since)}
    for stage in ("detect", "dispatch", "lease", "act", "confirm", "end_to_end"):
        assert latency[stage].samples > 0, stage
    print(
        "latency ms (p50/p95/p99):",
        {k: (round(v.p50_ms or 0), round(v.p95_ms or 0), round(v.p99_ms or 0)) for k, v in latency.items()},
    )


async def test_engine_under_chaos_has_zero_duplicates_and_reconciles_lost_answers(
    db: Db, board: Board, browser: Browser, tmp_path: Path
) -> None:
    chaos = {
        "ack_loss_rate": 0.2,  # booked, but the answer is lost: only the reconciler can tell
        "error_rate": 0.05,
        "slow_rate": 0.1,
        "slow_ms": 400,
        "competitor_share": 0.3,  # rival bots book some loads first
        "layout_variant": "b",  # the page layout changes; the watcher reads the network, not the layout
    }
    board.admin.patch("/admin/settings", json=chaos).raise_for_status()
    await asyncio.sleep(1.1)
    tenant, since, outcome = await run_engine(db, board, browser, tmp_path, seconds=20)
    ours, audit = board_says(board, tenant, since)
    confirmed = await our_bookings(db, tenant, since)
    assert audit["duplicate_loads"] == [], audit["duplicate_loads"][:5]
    assert confirmed == ours, (len(confirmed), len(ours), sorted(confirmed ^ ours)[:5])
    reconciled = outcome.get("confirmed", 0) + outcome.get("not_booked", 0) + outcome.get("confirmed_by_late_actor", 0)
    assert reconciled > 0, f"chaos should have produced lost answers to reconcile: {outcome}"
    assert outcome.get("FAILED", 0) > 0, f"rivals should have taken some loads: {outcome}"
    assert len(confirmed) >= 30, outcome


async def test_engine_click_mode(db: Db, board: Board, browser: Browser, tmp_path: Path) -> None:
    tenant, since, outcome = await run_engine(db, board, browser, tmp_path, seconds=12, action_mode="click")
    ours, audit = board_says(board, tenant, since)
    confirmed = await our_bookings(db, tenant, since)
    assert audit["duplicate_loads"] == []
    assert confirmed == ours
    assert len(confirmed) >= 10, outcome


async def test_tenant_moves_between_cells_while_running(db: Db, board: Board, browser: Browser, tmp_path: Path) -> None:
    """Cell A runs the tenant; it is moved to cell B (own control loops, own Redis, own fleet).
    A's slots retire and release the accounts; B's slots take them, restoring sessions from the
    vault (no new sign-in); bookings continue; still no duplicate attempts."""
    tenant = await board_tenant(db, board, 3)
    await add_filter(db, tenant.id)
    cell_b = await new_cell(db)
    since = await db_now(db)
    async with (
        running_control(db, board, tenant.cell, "cell-a"),
        running_control(db, board, cell_b, "cell-b"),
        running_fleet(db, board, browser, tenant.cell, tmp_path, ENGINE, contexts=3, redis_cell="cell-a") as fleet_a,
        running_fleet(db, board, browser, cell_b, tmp_path, ENGINE, contexts=3, redis_cell="cell-b") as fleet_b,
    ):
        await wait_for(lambda: all(s.state == "ready" for s in fleet_a.slots), 60, "cell A signed in")
        assert fleet_b.slots == [], "cell B has no tenants yet"
        await asyncio.sleep(6)
        before = len(await our_bookings(db, tenant, since))
        await move_tenant(db.app, tenant.id, cell_b, "test")
        await wait_for(
            lambda: all(s.retired for s in fleet_a.slots) or not fleet_a.slots, 10, "cell A retired its slots"
        )
        await wait_for(
            lambda: len(fleet_b.slots) == 3 and all(s.state == "ready" for s in fleet_b.slots), 60, "cell B took over"
        )
        assert sum(s.sign_ins for s in fleet_b.slots) == 0, "sessions came from the vault"
        await asyncio.sleep(8)
    await settle(db, tenant)
    after = await our_bookings(db, tenant, since)
    ours, audit = board_says(board, tenant, since)
    assert audit["duplicate_loads"] == []
    assert after == ours
    assert len(after) > before > 0, (before, len(after))
    async with tenant_tx(db.app, tenant.id) as conn:
        late = (
            await conn.execute(
                text("SELECT count(*) FROM claims WHERE cell_id = :c AND state IN ('CONFIRMED', 'RECONCILED')"),
                {"c": cell_b},
            )
        ).scalar_one()
    assert late > 0, "claims were processed in cell B after the move"
