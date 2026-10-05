"""Alembic environment: runs migrations as role fw_owner over the async driver.
The engine is handed in by fw_coordinator.migrate (from settings), never read from alembic.ini."""

import asyncio

from alembic import context
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine


def _run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=None, transaction_per_migration=True)
    with context.begin_transaction():
        context.run_migrations()


async def _main(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        await conn.run_sync(_run)
        await conn.commit()


asyncio.run(_main(context.config.attributes["engine"]))
