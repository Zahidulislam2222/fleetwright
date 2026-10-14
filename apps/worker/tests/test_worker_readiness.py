"""Fresh heartbeats measure execution readiness, including the real database/API boundary."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import text

from dbkit import Db, new_tenant
from fw_coordinator.views import workers
from fw_core.db import tenant_tx
from fw_core.settings import CoordinatorSettings, load
from fw_worker.runtime import Fleet


@pytest.mark.integration
@pytest.mark.parametrize(
    ("slot_state", "connected", "expected_state", "expected_status"),
    [
        ("ready", True, "running", "healthy"),
        ("ready", False, "starting", "stale"),
        ("failed", True, "starting", "stale"),
        ("signing_in", True, "starting", "stale"),
        ("paused", True, "starting", "stale"),
        ("stopped", True, "stopped", "dead"),
    ],
)
async def test_heartbeat_and_api_require_ready_slot_and_connected_browser(
    db: Db, slot_state: str, connected: bool, expected_state: str, expected_status: str
) -> None:
    tenant = await new_tenant(db)
    fleet = object.__new__(Fleet)
    fleet.engine = db.worker
    fleet.cfg = SimpleNamespace(cell="cell-a")
    fleet.process_id = "test-readiness"
    fleet.clock_offset_ms = 0.0
    fleet.browser = SimpleNamespace(is_connected=lambda: connected)
    fleet.meter = SimpleNamespace(sample=lambda: (0, 0.0))
    slot_id = "test-readiness-" + uuid4().hex
    fleet.slots = [
        SimpleNamespace(
            id=slot_id,
            tenant_id=tenant,
            retired=False,
            account=None,
            context=None,
            state=slot_state,
            role="watcher",
        )
    ]
    fleet._retired_slots = []
    await fleet._heartbeat()
    async with tenant_tx(db.app, tenant) as conn:
        state = await conn.scalar(text("SELECT state FROM workers WHERE id=:i"), {"i": slot_id})
        response = await workers(conn, tenant, load(CoordinatorSettings).api)
    assert state == expected_state
    item = next(row for row in response["items"] if row["id"] == slot_id)
    assert item["status"] == expected_status
