"""Database test kit: engines for the three roles and helpers that create isolated tenants.
Each test works in its own fresh tenant, so tests never see each other's rows (that is RLS too)."""

from __future__ import annotations

import base64
import os
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic_settings import SettingsConfigDict
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from fw_core.crypto import Envelope, aad_for
from fw_core.db import make_engine, system_tx, tenant_tx
from fw_core.settings import DatabaseSettings, VaultSettings, _Base

ROOT = Path(__file__).resolve().parents[3]
TEST_POOL = 100  # 200 concurrent competitors share these pools in one test process
CELLS = ("cell-a", "cell-b")


class DbTestSettings(_Base):
    model_config = SettingsConfigDict(
        env_prefix="FW_", env_nested_delimiter="__", extra="ignore", env_file=ROOT / ".env"
    )
    app_db: DatabaseSettings
    worker_db: DatabaseSettings
    owner_db: DatabaseSettings
    vault: VaultSettings


@dataclass
class Db:
    app: AsyncEngine
    worker: AsyncEngine
    owner: AsyncEngine
    envelope: Envelope


@pytest.fixture(scope="session")
async def db() -> AsyncIterator[Db]:
    cfg = DbTestSettings()  # type: ignore[call-arg]
    pools = {"pool_size": TEST_POOL, "pool_max_overflow": 20, "pool_timeout_s": 60.0}
    app = make_engine(cfg.app_db.dsn, cfg.app_db.model_copy(update=pools), "test-app")
    worker = make_engine(cfg.worker_db.dsn, cfg.worker_db.model_copy(update=pools), "test-worker")
    owner = make_engine(cfg.owner_db.dsn, cfg.owner_db, "test-owner")
    async with system_tx(app) as conn:
        for cell in CELLS:
            await conn.execute(
                text(
                    "INSERT INTO cells (id, name, region, capacity) VALUES (:i, :n, 'local', 64) ON CONFLICT DO NOTHING"
                ),
                {"i": cell, "n": cell},
            )
    yield Db(app, worker, owner, Envelope(cfg.vault.master_key_b64.get_secret_value(), cfg.vault.key_id))
    for engine in (app, worker, owner):
        await engine.dispose()


async def new_tenant(db: Db, cell: str = "cell-a") -> UUID:
    tenant_id = uuid4()
    async with system_tx(db.app) as conn:
        await conn.execute(
            text("INSERT INTO tenants (id, slug, name) VALUES (:i, :s, :n)"),
            {"i": tenant_id, "s": f"t-{tenant_id.hex[:12]}", "n": f"Test tenant {tenant_id.hex[:6]}"},
        )
        await conn.execute(
            text("INSERT INTO tenant_cells (tenant_id, cell_id) VALUES (:t, :c)"), {"t": tenant_id, "c": cell}
        )
    return tenant_id


async def new_accounts(db: Db, tenant_id: UUID, count: int) -> list[UUID]:
    ids = []
    async with tenant_tx(db.app, tenant_id) as conn:
        for i in range(count):
            account_id = uuid4()
            sealed = db.envelope.seal(base64.b64encode(os.urandom(12)), aad_for(tenant_id, account_id, "credential"))
            await conn.execute(
                text(
                    """INSERT INTO accounts (tenant_id, id, label, target, username, email,
                                           cred_key_id, cred_wrapped, cred_nonce, cred_sealed)
                       VALUES (:t, :i, :l, 'demo-board', :u, :e, :k, :w, :n, :s)"""
                ),
                {
                    "t": tenant_id,
                    "i": account_id,
                    "l": f"Test account {i}",
                    "u": f"acct-{account_id.hex[:10]}",
                    "e": f"acct-{account_id.hex[:10]}@board.demo.test",
                    "k": sealed.key_id,
                    "w": sealed.wrapped_key,
                    "n": sealed.nonce,
                    "s": sealed.ciphertext,
                },
            )
            ids.append(account_id)
    return ids
