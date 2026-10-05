"""Account mutex at the worker level: a slot holds one account at a time through
accounts.holder_worker / holder_expires_at, renewed on every heartbeat. A slot that fails to renew
has lost its account and must stop using it at once."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from fw_browser.vault import Account


async def acquire(conn: AsyncConnection, tenant_id: UUID, slot_id: str, hold_s: float) -> Account | None:
    row = (
        await conn.execute(
            text(
                """UPDATE accounts SET holder_worker = :w, holder_expires_at = clock_timestamp() + make_interval(secs => :s)
                   WHERE tenant_id = :t AND id = (
                     SELECT id FROM accounts
                     WHERE tenant_id = :t AND enabled
                       AND (holder_expires_at IS NULL OR holder_expires_at < clock_timestamp() OR holder_worker = :w)
                     ORDER BY holder_worker = :w DESC, id LIMIT 1 FOR UPDATE SKIP LOCKED)
                   RETURNING id, target, username, email, account_group, otp_channel"""
            ),
            {"t": tenant_id, "w": slot_id, "s": hold_s},
        )
    ).one_or_none()
    if row is None:
        return None
    return Account(tenant_id, row.id, row.target, row.username, row.email, row.account_group, row.otp_channel)


async def renew(conn: AsyncConnection, account: Account, slot_id: str, hold_s: float) -> bool:
    result = await conn.execute(
        text(
            """UPDATE accounts SET holder_expires_at = clock_timestamp() + make_interval(secs => :s)
               WHERE tenant_id = :t AND id = :a AND holder_worker = :w AND holder_expires_at > clock_timestamp()"""
        ),
        {"t": account.tenant_id, "a": account.id, "w": slot_id, "s": hold_s},
    )
    return int(result.rowcount) == 1


async def release(conn: AsyncConnection, account: Account, slot_id: str) -> None:
    await conn.execute(
        text(
            """UPDATE accounts SET holder_worker = NULL, holder_expires_at = NULL
               WHERE tenant_id = :t AND id = :a AND holder_worker = :w"""
        ),
        {"t": account.tenant_id, "a": account.id, "w": slot_id},
    )
