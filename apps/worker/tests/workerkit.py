"""Worker test kit: board accounts mirrored into a tenant (password sealed in the vault), a private
cell per test so the fleet only sees that test's tenant, and a fleet runner."""

from __future__ import annotations

import asyncio
import secrets
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
from playwright.async_api import Browser
from pydantic_settings import SettingsConfigDict
from redis.asyncio import Redis
from sqlalchemy import text

from boardkit import Board
from dbkit import Db, new_tenant
from fw_browser.evidence import EvidenceStore
from fw_browser.otp import MailpitOtp
from fw_browser.profiles import load_profiles
from fw_browser.proxy import ProxyPool, load_proxy_config
from fw_browser.targets import load_targets
from fw_browser.vault import CREDENTIAL_PURPOSE, Vault
from fw_core.crypto import aad_for
from fw_core.db import system_tx, tenant_tx
from fw_core.settings import RedisSettings, WorkerSettings, _Base
from fw_queue import client
from fw_worker.runtime import Behaviour, Fleet, Role, idle

ROOT = Path(__file__).resolve().parents[3]
FAST = {
    "contexts": 3,
    "watchers": 1,
    "heartbeat_s": 0.5,
    "account_hold_s": 5.0,
    "restart_backoff_s": 0.5,
    "otp_wait_s": 20.0,
    "login_timeout_ms": 15000,
    "action_timeout_ms": 8000,
    "drain_timeout_s": 10.0,
}


class RedisOnly(_Base):
    model_config = SettingsConfigDict(
        env_prefix="FW_", env_nested_delimiter="__", extra="ignore", env_file=ROOT / ".env"
    )
    redis: RedisSettings


@dataclass
class Tenant:
    id: UUID
    cell: str
    accounts: dict[UUID, tuple[str, str]]  # account id -> (username, password)


async def new_cell(db: Db) -> str:
    cell = f"t-{uuid4().hex[:12]}"
    async with system_tx(db.app) as conn:
        await conn.execute(
            text("INSERT INTO cells (id, name, region, capacity) VALUES (:i, :i, 'test', 8)"), {"i": cell}
        )
    return cell


async def board_tenant(db: Db, board: Board, count: int, wrong_password: set[int] | None = None) -> Tenant:
    """`count` accounts that exist on the board; indexes in wrong_password get a vault password the
    board will reject."""
    cell = await new_cell(db)
    tenant_id = await new_tenant(db, cell)
    made: dict[UUID, tuple[str, str]] = {}
    async with tenant_tx(db.app, tenant_id) as conn:
        for i in range(count):
            username, password = f"w-{secrets.token_hex(4)}", secrets.token_urlsafe(16)
            email = board.admin.post("/admin/accounts", json={"username": username, "password": password}).json()[
                "email"
            ]
            stored = password + "-wrong" if wrong_password and i in wrong_password else password
            account_id = uuid4()
            sealed = db.envelope.seal(stored.encode(), aad_for(tenant_id, account_id, CREDENTIAL_PURPOSE))
            await conn.execute(
                text(
                    """INSERT INTO accounts (tenant_id, id, label, target, username, email,
                                           cred_key_id, cred_wrapped, cred_nonce, cred_sealed)
                       VALUES (:t, :i, :l, 'demo-board', :u, :e, :k, :w, :n, :s)"""
                ),
                {
                    "t": tenant_id,
                    "i": account_id,
                    "l": f"Account {i}",
                    "u": username,
                    "e": email,
                    "k": sealed.key_id,
                    "w": sealed.wrapped_key,
                    "n": sealed.nonce,
                    "s": sealed.ciphertext,
                },
            )
            made[account_id] = (username, password)
    return Tenant(tenant_id, cell, made)


@asynccontextmanager
async def running_fleet(
    db: Db,
    board: Board,
    browser: Browser,
    cell: str,
    evidence_dir: Path,
    behaviours: dict[Role, Behaviour] | None = None,
    **overrides: Any,
) -> AsyncIterator[Fleet]:
    cfg = WorkerSettings.model_validate({"cell": cell, **FAST, **overrides})
    redis: Redis = client.core(RedisOnly().redis)  # type: ignore[call-arg]
    otp = MailpitOtp(board.settings.mailpit.api_url)
    fleet = Fleet(
        cfg=cfg,
        engine=db.worker,
        events=redis,
        browser=browser,
        vault=Vault(db.envelope),
        targets=load_targets(ROOT / "config"),
        base_urls={"demo-board": board.url},
        profiles=load_profiles(ROOT / "config"),
        proxies=ProxyPool(load_proxy_config(ROOT / "config")),
        evidence=EvidenceStore(evidence_dir, 7),
        email_otp=otp,
        behaviours=behaviours or {"watcher": idle, "claimer": idle},
    )
    await fleet.start()
    try:
        yield fleet
    finally:
        await fleet.drain()
        await otp.aclose()
        await redis.aclose()


async def wait_for(check: Callable[[], bool], timeout_s: float, what: str) -> None:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_s
    while not check():
        if loop.time() > deadline:
            stacks = "\n".join(f"--- task {t.get_name()}\n" + _awaiting(t) for t in asyncio.all_tasks())
            raise AssertionError(f"timed out waiting for: {what}\n{stacks}")
        await asyncio.sleep(0.2)


def mailpit_count(board: Board, address: str) -> int:
    reply = httpx.get(
        f"{board.settings.mailpit.api_url}/api/v1/search", params={"query": f'to:"{address}"'}, timeout=10
    )
    reply.raise_for_status()
    return int(reply.json()["messages_count"])


def _awaiting(task: asyncio.Task[Any]) -> str:
    """The chain of coroutines a task is suspended in, innermost last (get_stack shows only the outer one)."""
    lines: list[str] = []
    coro: Any = task.get_coro()
    while coro is not None:
        frame = getattr(coro, "cr_frame", None) or getattr(coro, "gi_frame", None)
        if frame is not None:
            lines.append(f"  {frame.f_code.co_filename}:{frame.f_lineno} in {frame.f_code.co_name}")
        coro = getattr(coro, "cr_await", None) or getattr(coro, "gi_yieldfrom", None)
    return "\n".join(lines)
