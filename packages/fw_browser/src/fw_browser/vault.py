"""Session vault: an account's signed-in browser state (Playwright storage_state: cookies plus local
storage) sealed with the tenant/account-bound envelope key and stored in account_sessions. A worker
that restarts reuses the session instead of signing in again (no new OTP), and refreshes it before
the target expires it.

Credentials are opened here too, only in memory, only when a sign-in is needed."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from fw_core.crypto import Envelope, Sealed, aad_for

SESSION_PURPOSE = "session"
CREDENTIAL_PURPOSE = "credential"
SessionState = Literal["fresh", "expiring", "expired", "otp_required"]


@dataclass(frozen=True)
class Account:
    tenant_id: UUID
    id: UUID
    target: str
    username: str
    email: str
    account_group: str
    otp_channel: str


@dataclass(frozen=True)
class StoredSession:
    storage_state: dict[str, Any]
    state: SessionState
    expires_at: datetime | None
    refreshed_at: datetime

    def needs_refresh(self, now: datetime, share: float) -> bool:
        """True once `share` of the session's lifetime has passed (e.g. 0.7 = refresh at 70%)."""
        if self.state != "fresh":
            return True
        if self.expires_at is None:
            return False
        lifetime = (self.expires_at - self.refreshed_at).total_seconds()
        return lifetime <= 0 or (now - self.refreshed_at).total_seconds() >= share * lifetime


def session_expiry(storage_state: dict[str, Any]) -> datetime | None:
    """Earliest expiry among persistent cookies (session cookies, expires = -1, are ignored)."""
    stamps = [float(c["expires"]) for c in storage_state.get("cookies", []) if float(c.get("expires", -1)) > 0]
    return datetime.fromtimestamp(min(stamps), UTC) if stamps else None


class Vault:
    def __init__(self, envelope: Envelope) -> None:
        self._envelope = envelope

    async def password(self, conn: AsyncConnection, account: Account) -> str:
        row = (
            await conn.execute(
                text(
                    """SELECT cred_key_id, cred_wrapped, cred_nonce, cred_sealed FROM accounts
                       WHERE tenant_id = :t AND id = :a"""
                ),
                {"t": account.tenant_id, "a": account.id},
            )
        ).one()
        sealed = Sealed(row.cred_key_id, row.cred_wrapped, row.cred_nonce, row.cred_sealed)
        return self._envelope.open(sealed, aad_for(account.tenant_id, account.id, CREDENTIAL_PURPOSE)).decode()

    async def save(self, conn: AsyncConnection, account: Account, storage_state: dict[str, Any]) -> StoredSession:
        expires_at = session_expiry(storage_state)
        sealed = self._envelope.seal(
            json.dumps(storage_state, separators=(",", ":")).encode(),
            aad_for(account.tenant_id, account.id, SESSION_PURPOSE),
        )
        row = (
            await conn.execute(
                text(
                    """INSERT INTO account_sessions
                         (tenant_id, account_id, key_id, wrapped, nonce, sealed, state, expires_at, ttl_s, refreshed_at)
                       VALUES (:t, :a, :k, :w, :n, :s, 'fresh', :e,
                               CASE WHEN CAST(:e AS timestamptz) IS NULL THEN NULL
                                    ELSE greatest(0, extract(epoch FROM CAST(:e AS timestamptz) - clock_timestamp()))::int END,
                               clock_timestamp())
                       ON CONFLICT (tenant_id, account_id) DO UPDATE SET
                         key_id = EXCLUDED.key_id, wrapped = EXCLUDED.wrapped, nonce = EXCLUDED.nonce,
                         sealed = EXCLUDED.sealed, state = 'fresh', expires_at = EXCLUDED.expires_at,
                         ttl_s = EXCLUDED.ttl_s, refreshed_at = EXCLUDED.refreshed_at
                       RETURNING refreshed_at"""
                ),
                {
                    "t": account.tenant_id,
                    "a": account.id,
                    "k": sealed.key_id,
                    "w": sealed.wrapped_key,
                    "n": sealed.nonce,
                    "s": sealed.ciphertext,
                    "e": expires_at,
                },
            )
        ).one()
        return StoredSession(storage_state, "fresh", expires_at, row.refreshed_at)

    async def load(self, conn: AsyncConnection, account: Account) -> StoredSession | None:
        row = (
            await conn.execute(
                text(
                    """SELECT key_id, wrapped, nonce, sealed, state, expires_at, refreshed_at FROM account_sessions
                       WHERE tenant_id = :t AND account_id = :a"""
                ),
                {"t": account.tenant_id, "a": account.id},
            )
        ).one_or_none()
        if row is None:
            return None
        plain = self._envelope.open(
            Sealed(row.key_id, row.wrapped, row.nonce, row.sealed),
            aad_for(account.tenant_id, account.id, SESSION_PURPOSE),
        )
        return StoredSession(json.loads(plain), row.state, row.expires_at, row.refreshed_at)

    @staticmethod
    async def mark(conn: AsyncConnection, account: Account, state: SessionState) -> None:
        await conn.execute(
            text("UPDATE account_sessions SET state = :s WHERE tenant_id = :t AND account_id = :a"),
            {"s": state, "t": account.tenant_id, "a": account.id},
        )
