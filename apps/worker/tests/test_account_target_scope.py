"""Legacy fleet slots must leave authentication-only accounts available for workflows."""

from pathlib import Path

import pytest
from sqlalchemy import text

from dbkit import Db, new_accounts, new_tenant
from fw_core.db import tenant_tx
from fw_core.targets import load_targets
from fw_worker import accounts

ROOT = Path(__file__).resolve().parents[3]


def test_legacy_target_inventory_is_explicit() -> None:
    targets = load_targets(ROOT / "config")
    assert targets.freight_targets() == ("demo-board",)


@pytest.mark.integration
async def test_legacy_acquisition_skips_service_only_accounts(db: Db) -> None:
    tenant = await new_tenant(db)
    freight, service = await new_accounts(db, tenant, 2)
    async with tenant_tx(db.app, tenant) as conn:
        await conn.execute(
            text("UPDATE accounts SET target = :target WHERE id = :id"), {"target": "service-only", "id": service}
        )
        held = await accounts.acquire(conn, tenant, "legacy-slot", 30, ("demo-board",), ())
        assert held is not None and held.id == freight
        assert await accounts.acquire(conn, tenant, "other-slot", 30, ("demo-board",), ()) is None
        assert (
            await conn.execute(text("SELECT holder_worker FROM accounts WHERE id = :id"), {"id": service})
        ).scalar_one() is None
        assert await accounts.acquire(conn, tenant, "empty-config-slot", 30, (), ()) is None


@pytest.mark.integration
async def test_legacy_acquisition_leaves_reserved_same_target_account_free(db: Db) -> None:
    tenant = await new_tenant(db)
    freight, workflow = await new_accounts(db, tenant, 2)
    async with tenant_tx(db.app, tenant) as conn:
        await conn.execute(text("UPDATE accounts SET account_group='workflow' WHERE id=:id"), {"id": workflow})
        held = await accounts.acquire(conn, tenant, "legacy-slot", 30, ("demo-board",), ("workflow",))
        assert held is not None and held.id == freight
        assert await accounts.acquire(conn, tenant, "second-slot", 30, ("demo-board",), ("workflow",)) is None
        assert await conn.scalar(text("SELECT holder_worker FROM accounts WHERE id=:id"), {"id": workflow}) is None
