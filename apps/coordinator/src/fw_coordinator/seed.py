"""`python -m fw_coordinator.seed`: creates (or brings up to date) the public demo tenant.

Idempotent. It creates the cell and tenant, the owner (password and TOTP secret from the
environment), the shared demo login (role `demo`), demo carrier accounts on the mock board (their
passwords go only into the vault), and the filters and schedules from config/demo.yaml. Finally it
puts the board on its idle preset. No secret is printed."""

from __future__ import annotations

import asyncio
import json
import secrets
from uuid import UUID, uuid4

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from fw_coordinator.auth import hash_password, new_totp_secret, seal_totp
from fw_coordinator.demo import DemoConfig, load_demo
from fw_core.crypto import Envelope, aad_for
from fw_core.db import make_engine, system_tx, tenant_tx
from fw_core.settings import SeedAppSettings, load
from fw_core.vault import CREDENTIAL_PURPOSE

BOARD_TARGET = "demo-board"


async def _tenant(engine: AsyncEngine, cfg: SeedAppSettings, data: DemoConfig) -> UUID:
    cell = data.seed.cell
    async with system_tx(engine) as conn:
        await conn.execute(
            text(
                """INSERT INTO cells (id, name, region, capacity) VALUES (:i, :n, :r, :c)
                   ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name, region = EXCLUDED.region,
                                                  capacity = EXCLUDED.capacity"""
            ),
            {"i": cfg.seed.cell, "n": cell.name, "r": cell.region, "c": cell.capacity},
        )
        tenant_id = (
            await conn.execute(text("SELECT id FROM tenants WHERE slug = :s"), {"s": cfg.demo.tenant_slug})
        ).scalar_one_or_none()
        if tenant_id is None:
            tenant_id = uuid4()
            await conn.execute(
                text("INSERT INTO tenants (id, slug, name) VALUES (:i, :s, :n)"),
                {"i": tenant_id, "s": cfg.demo.tenant_slug, "n": data.seed.tenant_name},
            )
            await conn.execute(
                text("INSERT INTO tenant_cells (tenant_id, cell_id) VALUES (:t, :c)"),
                {"t": tenant_id, "c": cfg.seed.cell},
            )
    return UUID(str(tenant_id))


async def _user(
    engine: AsyncEngine,
    envelope: Envelope,
    tenant_id: UUID,
    email: str,
    name: str,
    role: str,
    password: str,
    totp_b32: str | None,
) -> None:
    """Creates or updates a console user. `totp_b32=None` keeps an existing secret (or makes one)."""
    email = email.strip().lower()
    async with system_tx(engine) as conn:
        row = (
            await conn.execute(text("SELECT tenant_id, user_id FROM user_directory WHERE email = :e"), {"e": email})
        ).one_or_none()
    if row is not None and row.tenant_id != tenant_id:
        raise SystemExit(f"{email} already belongs to another tenant; refusing to move it")
    user_id = row.user_id if row is not None else uuid4()
    async with tenant_tx(engine, tenant_id) as conn:
        existing = (
            await conn.execute(
                text("SELECT totp_sealed IS NOT NULL AS has_totp FROM users WHERE tenant_id = :t AND id = :u"),
                {"t": tenant_id, "u": user_id},
            )
        ).one_or_none()
        if totp_b32 is None and existing is not None and existing.has_totp:
            await conn.execute(
                text(
                    """UPDATE users SET name = :n, role = :r, password_hash = :p, mfa_enabled = true
                       WHERE tenant_id = :t AND id = :u"""
                ),
                {"t": tenant_id, "u": user_id, "n": name, "r": role, "p": hash_password(password)},
            )
            return
        sealed = seal_totp(envelope, tenant_id, user_id, totp_b32 or new_totp_secret())
        await conn.execute(
            text(
                """INSERT INTO users (tenant_id, id, email, name, role, password_hash,
                                      totp_key_id, totp_wrapped, totp_nonce, totp_sealed, mfa_enabled)
                   VALUES (:t, :u, :e, :n, :r, :p, :k, :w, :nonce, :s, true)
                   ON CONFLICT (tenant_id, id) DO UPDATE SET
                     name = EXCLUDED.name, role = EXCLUDED.role, password_hash = EXCLUDED.password_hash,
                     totp_key_id = EXCLUDED.totp_key_id, totp_wrapped = EXCLUDED.totp_wrapped,
                     totp_nonce = EXCLUDED.totp_nonce, totp_sealed = EXCLUDED.totp_sealed, mfa_enabled = true"""
            ),
            {
                "t": tenant_id,
                "u": user_id,
                "e": email,
                "n": name,
                "r": role,
                "p": hash_password(password),
                "k": sealed.key_id,
                "w": sealed.wrapped_key,
                "nonce": sealed.nonce,
                "s": sealed.ciphertext,
            },
        )
    if row is None:
        async with system_tx(engine) as conn:
            await conn.execute(
                text("INSERT INTO user_directory (email, tenant_id, user_id) VALUES (:e, :t, :u)"),
                {"e": email, "t": tenant_id, "u": user_id},
            )


async def _board_accounts(
    engine: AsyncEngine, envelope: Envelope, http: httpx.AsyncClient, cfg: SeedAppSettings, tenant_id: UUID, count: int
) -> int:
    """Demo carrier accounts: created on the board with a random password kept only in the vault."""
    base = cfg.board_client.internal_url.rstrip("/")
    headers = {"Authorization": f"Bearer {cfg.board_client.admin_token.get_secret_value()}"}
    created = 0
    for i in range(1, count + 1):
        username = f"{cfg.demo.tenant_slug}-carrier-{i}"
        async with tenant_tx(engine, tenant_id) as conn:
            exists = (
                await conn.execute(
                    text("SELECT 1 FROM accounts WHERE tenant_id = :t AND target = :g AND username = :u"),
                    {"t": tenant_id, "g": BOARD_TARGET, "u": username},
                )
            ).scalar_one_or_none()
        if exists:
            continue
        password = secrets.token_urlsafe(18)
        reply = await http.post(
            f"{base}/admin/accounts", json={"username": username, "password": password}, headers=headers
        )
        reply.raise_for_status()
        account_id = uuid4()
        sealed = envelope.seal(password.encode(), aad_for(tenant_id, account_id, CREDENTIAL_PURPOSE))
        async with tenant_tx(engine, tenant_id) as conn:
            await conn.execute(
                text(
                    """INSERT INTO accounts (tenant_id, id, label, target, username, email,
                                           cred_key_id, cred_wrapped, cred_nonce, cred_sealed)
                       VALUES (:t, :i, :l, :g, :u, :e, :k, :w, :n, :s)"""
                ),
                {
                    "t": tenant_id,
                    "i": account_id,
                    "l": f"Demo carrier {i}",
                    "g": BOARD_TARGET,
                    "u": username,
                    "e": reply.json()["email"],
                    "k": sealed.key_id,
                    "w": sealed.wrapped_key,
                    "n": sealed.nonce,
                    "s": sealed.ciphertext,
                },
            )
        created += 1
    return created


async def _rules(conn: AsyncConnection, tenant_id: UUID, data: DemoConfig) -> None:
    for f in data.seed.filters:
        await conn.execute(
            text(
                """INSERT INTO filters (tenant_id, id, name, origin, destination, min_rate_usd)
                   VALUES (:t, :i, :n, :o, :d, :r) ON CONFLICT (tenant_id, name) DO NOTHING"""
            ),
            {"t": tenant_id, "i": uuid4(), "n": f.name, "o": f.origin, "d": f.destination, "r": f.min_rate_usd},
        )
    ids = {
        r.name: r.id
        for r in await conn.execute(text("SELECT id, name FROM filters WHERE tenant_id = :t"), {"t": tenant_id})
    }
    for s in data.seed.schedules:
        missing = [n for n in s.filters if n not in ids]
        if missing:
            raise SystemExit(f"schedule {s.name!r} names unknown filters {missing}")
        await conn.execute(
            text(
                """INSERT INTO schedules (tenant_id, id, name, timezone, windows, targets)
                   VALUES (:t, :i, :n, :z, CAST(:w AS jsonb), CAST(:g AS uuid[]))
                   ON CONFLICT (tenant_id, name) DO NOTHING"""
            ),
            {
                "t": tenant_id,
                "i": uuid4(),
                "n": s.name,
                "z": s.timezone,
                "w": json.dumps([w.model_dump() for w in s.windows]),
                "g": [str(ids[n]) for n in s.filters],
            },
        )


async def seed(cfg: SeedAppSettings, data: DemoConfig) -> dict[str, object]:
    engine = make_engine(cfg.app_db.dsn, cfg.app_db, "fw-seed")
    envelope = Envelope(cfg.vault.master_key_b64.get_secret_value(), cfg.vault.key_id)
    try:
        async with httpx.AsyncClient(timeout=cfg.board_client.timeout_s) as http:
            tenant_id = await _tenant(engine, cfg, data)
            await _user(
                engine,
                envelope,
                tenant_id,
                cfg.seed.owner_email,
                cfg.seed.owner_name,
                "owner",
                cfg.seed.owner_password.get_secret_value(),
                cfg.seed.owner_totp_b32.get_secret_value(),
            )
            if cfg.demo.account_password is not None:
                await _user(
                    engine,
                    envelope,
                    tenant_id,
                    cfg.demo.account_email,
                    data.seed.demo_user_name,
                    "demo",
                    cfg.demo.account_password.get_secret_value(),
                    None,
                )
            created = await _board_accounts(engine, envelope, http, cfg, tenant_id, data.seed.board_accounts)
            async with tenant_tx(engine, tenant_id) as conn:
                await _rules(conn, tenant_id, data)
            headers = {"Authorization": f"Bearer {cfg.board_client.admin_token.get_secret_value()}"}
            reply = await http.patch(
                cfg.board_client.internal_url.rstrip("/") + "/admin/settings", json=data.idle, headers=headers
            )
            reply.raise_for_status()
    finally:
        await engine.dispose()
    return {"tenant": str(tenant_id), "board_accounts_created": created}


def main() -> None:
    cfg = load(SeedAppSettings)
    result = asyncio.run(seed(cfg, load_demo(cfg.config_dir)))
    print(f"demo tenant ready: {result}")


if __name__ == "__main__":
    main()
