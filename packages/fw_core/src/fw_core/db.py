"""Database access. Every tenant-scoped transaction sets `app.tenant_id`, which the Row-Level
Security policies compare against; a query that forgets the tenant therefore sees nothing."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

from pydantic import SecretStr
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from fw_core.settings import DatabaseSettings


def make_engine(dsn: SecretStr, cfg: DatabaseSettings, app_name: str) -> AsyncEngine:
    return create_async_engine(
        dsn.get_secret_value(),
        pool_size=cfg.pool_size,
        max_overflow=cfg.pool_max_overflow,
        pool_timeout=cfg.pool_timeout_s,
        pool_pre_ping=True,
        connect_args={
            "timeout": cfg.pool_timeout_s,
            "server_settings": {"application_name": app_name, "statement_timeout": str(cfg.statement_timeout_ms)},
        },
    )


@asynccontextmanager
async def tenant_tx(engine: AsyncEngine, tenant_id: UUID) -> AsyncIterator[AsyncConnection]:
    """One transaction bound to one tenant (the setting is transaction-local)."""
    async with engine.begin() as conn:
        await conn.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id)})
        yield conn


@asynccontextmanager
async def system_tx(engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    """A transaction with no tenant: RLS-protected tables return nothing. Used for the tenant and
    cell directories, which are not tenant-scoped."""
    async with engine.begin() as conn:
        yield conn
