"""Account policy uses the DB clock and preserves queued work for an eligible consumer."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from dbkit import Db, new_accounts, new_tenant
from fw_core import claims
from fw_core.db import tenant_tx

pytestmark = pytest.mark.integration


async def queued(db: Db, tenant: UUID, filter_id: UUID | None = None) -> UUID:
    now = datetime.now(UTC)
    detection = claims.Detection(uuid4().hex, "test lane", 1, now, now, 0.0, {}, filter_id)
    async with tenant_tx(db.app, tenant) as conn:
        claim = await claims.queue_claim(conn, tenant, detection, "cell-a", "test")
        assert claim is not None
        return claim


async def test_pacing_leaves_claim_queued_and_uses_database_time(db: Db) -> None:
    tenant = await new_tenant(db)
    (account,) = await new_accounts(db, tenant, 1)
    first, second = await queued(db, tenant), await queued(db, tenant)
    async with tenant_tx(db.app, tenant) as conn:
        await conn.execute(text("UPDATE accounts SET rate_limit_per_min=60 WHERE id=:a"), {"a": account})
    async with tenant_tx(db.worker, tenant) as conn:
        held = await claims.lease(
            conn, tenant, first, worker_id="first", account_id=account, ttl_ms=10000, max_age_s=120
        )
        assert held is not None
        assert await claims.start_acting(conn, tenant, held, "first", 10000)
        assert await claims.finish(conn, tenant, held, "first", "confirmed", "test") == "CONFIRMED"
    with pytest.raises(claims.AccountBusy):
        async with tenant_tx(db.worker, tenant) as conn:
            await claims.lease(
                conn, tenant, second, worker_id="second", account_id=account, ttl_ms=10000, max_age_s=120
            )
    async with tenant_tx(db.app, tenant) as conn:
        assert await conn.scalar(text("SELECT state FROM claims WHERE id=:c"), {"c": second}) == "QUEUED"
        await conn.execute(
            text("UPDATE accounts SET next_action_at=clock_timestamp()-interval '1 second' WHERE id=:a"), {"a": account}
        )
    async with tenant_tx(db.worker, tenant) as conn:
        assert await claims.lease(
            conn, tenant, second, worker_id="second", account_id=account, ttl_ms=10000, max_age_s=120
        )


async def test_group_mismatch_does_not_lease_or_consume_budget(db: Db) -> None:
    tenant = await new_tenant(db)
    wrong, eligible = await new_accounts(db, tenant, 2)
    group_filter = uuid4()
    async with tenant_tx(db.app, tenant) as conn:
        await conn.execute(
            text("INSERT INTO filters(tenant_id,id,name,account_group) VALUES(:t,:f,'restricted','priority')"),
            {"t": tenant, "f": group_filter},
        )
        await conn.execute(text("UPDATE accounts SET account_group='priority' WHERE id=:a"), {"a": eligible})
    claim = await queued(db, tenant, group_filter)
    with pytest.raises(claims.AccountBusy):
        async with tenant_tx(db.worker, tenant) as conn:
            await claims.lease(conn, tenant, claim, worker_id="wrong", account_id=wrong, ttl_ms=10000, max_age_s=120)
    async with tenant_tx(db.app, tenant) as conn:
        assert await conn.scalar(text("SELECT next_action_at FROM accounts WHERE id=:a"), {"a": wrong}) is None
    async with tenant_tx(db.worker, tenant) as conn:
        assert await claims.lease(
            conn, tenant, claim, worker_id="eligible", account_id=eligible, ttl_ms=10000, max_age_s=120
        )


async def test_parallel_admission_allows_only_one_budget_reservation(db: Db) -> None:
    tenant = await new_tenant(db)
    (account,) = await new_accounts(db, tenant, 1)
    async with tenant_tx(db.app, tenant) as conn:
        await conn.execute(text("UPDATE accounts SET rate_limit_per_min=1 WHERE id=:a"), {"a": account})

    async def enter() -> bool:
        async with tenant_tx(db.worker, tenant) as conn:
            return await claims.admit_account(conn, tenant, account)

    assert sum(await asyncio.gather(*(enter() for _ in range(20)))) == 1


async def test_delayed_preparation_and_action_refresh_completion_cooldown(db: Db) -> None:
    tenant = await new_tenant(db)
    (account,) = await new_accounts(db, tenant, 1)
    first, second = await queued(db, tenant), await queued(db, tenant)
    async with tenant_tx(db.app, tenant) as conn:
        await conn.execute(text("UPDATE accounts SET rate_limit_per_min=600 WHERE id=:a"), {"a": account})
    async with tenant_tx(db.worker, tenant) as conn:
        held = await claims.lease(
            conn, tenant, first, worker_id="first", account_id=account, ttl_ms=10000, max_age_s=120
        )
        assert held is not None
    await asyncio.sleep(0.15)  # preparation outlasts the initial100ms admission interval
    async with tenant_tx(db.worker, tenant) as conn:
        assert await claims.start_acting(conn, tenant, held, "first", 10000)
    await asyncio.sleep(0.15)  # even a slow actual action cannot consume the completion cooldown
    async with tenant_tx(db.worker, tenant) as conn:
        assert await claims.finish(conn, tenant, held, "first", "confirmed", "test") == "CONFIRMED"
    async with tenant_tx(db.app, tenant) as conn:
        assert await conn.scalar(
            text("SELECT next_action_at>clock_timestamp() FROM accounts WHERE id=:a"), {"a": account}
        )
    with pytest.raises(claims.AccountBusy):
        async with tenant_tx(db.worker, tenant) as conn:
            await claims.lease(
                conn, tenant, second, worker_id="second", account_id=account, ttl_ms=10000, max_age_s=120
            )


async def test_action_boundary_rechecks_account_enabled_and_worker_identity(db: Db) -> None:
    tenant = await new_tenant(db)
    (account,) = await new_accounts(db, tenant, 1)
    claim = await queued(db, tenant)
    async with tenant_tx(db.worker, tenant) as conn:
        held = await claims.lease(
            conn, tenant, claim, worker_id="owner", account_id=account, ttl_ms=10000, max_age_s=120
        )
        assert held is not None
        assert not await claims.start_acting(conn, tenant, held, "other-worker", 10000)
    async with tenant_tx(db.app, tenant) as conn:
        await conn.execute(text("UPDATE accounts SET enabled=false WHERE id=:a"), {"a": account})
    async with tenant_tx(db.worker, tenant) as conn:
        assert not await claims.start_acting(conn, tenant, held, "owner", 10000)


async def test_wrong_worker_cannot_record_outcome_or_extend_account_budget(db: Db) -> None:
    tenant = await new_tenant(db)
    (account,) = await new_accounts(db, tenant, 1)
    claim = await queued(db, tenant)
    async with tenant_tx(db.worker, tenant) as conn:
        held = await claims.lease(
            conn, tenant, claim, worker_id="owner", account_id=account, ttl_ms=10000, max_age_s=120
        )
        assert held is not None and await claims.start_acting(conn, tenant, held, "owner", 10000)
    async with tenant_tx(db.app, tenant) as conn:
        budget = await conn.scalar(text("SELECT next_action_at FROM accounts WHERE id=:a"), {"a": account})
    async with tenant_tx(db.worker, tenant) as conn:
        assert await claims.finish(conn, tenant, held, "intruder", "confirmed", "test") is None
    async with tenant_tx(db.app, tenant) as conn:
        assert await conn.scalar(text("SELECT next_action_at FROM accounts WHERE id=:a"), {"a": account}) == budget
        assert await conn.scalar(text("SELECT state FROM claims WHERE id=:c"), {"c": claim}) == "ACTING"
    async with tenant_tx(db.worker, tenant) as conn:
        assert await claims.finish(conn, tenant, held, "owner", "confirmed", "test") == "CONFIRMED"
