"""Phase 3 exit criterion 4 (tenant A cannot read tenant B) and the scale check on the schema:
every tenant table has tenant_id, forced RLS, and indexes that start with tenant_id."""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, ProgrammingError

from dbkit import Db, new_accounts, new_tenant
from fw_core.db import system_tx, tenant_tx

pytestmark = pytest.mark.integration


async def test_tenant_cannot_read_another_tenants_rows(db: Db) -> None:
    a, b = await new_tenant(db), await new_tenant(db)
    await new_accounts(db, a, 3)
    await new_accounts(db, b, 2)
    async with tenant_tx(db.app, a) as conn:
        assert (await conn.execute(text("SELECT count(*) FROM accounts"))).scalar_one() == 3
        assert (
            await conn.execute(text("SELECT count(*) FROM accounts WHERE tenant_id = :b"), {"b": b})
        ).scalar_one() == 0
    async with tenant_tx(db.worker, b) as conn:
        assert (await conn.execute(text("SELECT count(*) FROM accounts"))).scalar_one() == 2


async def test_no_tenant_means_no_rows(db: Db) -> None:
    a = await new_tenant(db)
    await new_accounts(db, a, 1)
    async with system_tx(db.app) as conn:
        assert (await conn.execute(text("SELECT count(*) FROM accounts"))).scalar_one() == 0
    async with system_tx(db.owner) as conn:  # FORCE RLS: not even the table owner sees rows
        assert (await conn.execute(text("SELECT count(*) FROM accounts"))).scalar_one() == 0


async def test_writing_into_another_tenant_is_refused(db: Db) -> None:
    a, b = await new_tenant(db), await new_tenant(db)
    with pytest.raises(DBAPIError, match="row-level security"):
        async with tenant_tx(db.app, a) as conn:
            await conn.execute(
                text("INSERT INTO filters (tenant_id, id, name) VALUES (:b, :i, 'sneaky')"), {"b": b, "i": uuid4()}
            )


async def test_worker_role_has_narrow_privileges(db: Db) -> None:
    a = await new_tenant(db)
    for statement in (
        "SELECT count(*) FROM users",
        "SELECT count(*) FROM audit_log",
        "UPDATE claims SET lane = 'x'",
        "INSERT INTO filters (tenant_id, id, name) "
        "VALUES (NULLIF(current_setting('app.tenant_id', true), '')::uuid, gen_random_uuid(), 'x')",
        "UPDATE accounts SET username = 'x'",
        "DELETE FROM claim_events",
    ):
        with pytest.raises(ProgrammingError, match="permission denied"):
            async with tenant_tx(db.worker, a) as conn:
                await conn.execute(text(statement))


async def test_audit_log_is_append_only_for_the_app(db: Db) -> None:
    a = await new_tenant(db)
    async with tenant_tx(db.app, a) as conn:
        await conn.execute(
            text(
                "INSERT INTO audit_log (tenant_id, actor, role, action, target, detail) VALUES (:t, 'x', 'owner', 'a', 'b', 'c')"
            ),
            {"t": a},
        )
    for statement in ("UPDATE audit_log SET detail = 'changed'", "DELETE FROM audit_log"):
        with pytest.raises(ProgrammingError, match="permission denied"):
            async with tenant_tx(db.app, a) as conn:
                await conn.execute(text(statement))


async def test_scale_check_schema(db: Db) -> None:
    async with system_tx(db.owner) as conn:
        tables = (
            await conn.execute(
                text(
                    """SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity
                       FROM pg_class c JOIN pg_attribute a ON a.attrelid = c.oid AND a.attname = 'tenant_id'
                       WHERE c.relkind = 'r' AND c.relnamespace = 'public'::regnamespace
                         AND c.relname NOT IN ('tenant_cells', 'user_directory')"""
                )
            )
        ).all()
        assert len(tables) >= 11
        assert all(t.relrowsecurity and t.relforcerowsecurity for t in tables), tables
        names = [t.relname for t in tables]
        indexes = (
            await conn.execute(
                text(
                    """SELECT i.relname AS index, t.relname AS table, a.attname AS first_column
                       FROM pg_index x JOIN pg_class i ON i.oid = x.indexrelid JOIN pg_class t ON t.oid = x.indrelid
                       JOIN pg_attribute a ON a.attrelid = t.oid AND a.attnum = x.indkey[0]
                       WHERE t.relname = ANY(:names)"""
                ),
                {"names": names},
            )
        ).all()
        wrong = [(i.index, i.first_column) for i in indexes if i.first_column != "tenant_id"]
        assert not wrong, f"indexes not led by tenant_id: {wrong}"
