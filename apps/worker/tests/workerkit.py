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
from fw_coordinator.control import Control
from fw_core.crypto import aad_for
from fw_core.db import system_tx, tenant_tx
from fw_core.settings import ClaimSettings, ControlSettings, RedisSettings, WorkerSettings, _Base
from fw_core.targets import load_targets
from fw_core.vault import CREDENTIAL_PURPOSE, Vault
from fw_queue import client
from fw_worker.runtime import Behaviour, Fleet, Role, idle

ROOT = Path(__file__).resolve().parents[3]
CELL_REDIS = "cell-a"  # test cells are database-only names; their streams live on this Redis
FAST = {
    "contexts": 3,
    "watchers": 1,
    "heartbeat_s": 0.5,
    "account_hold_s": 5.0,
    "restart_backoff_s": 0.5,
    "otp_wait_s": 20.0,
    "login_timeout_ms": 15000,
    "action_timeout_ms": 5000,  # must stay below the claim lease (8000 ms)
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
    claims_cfg: ClaimSettings | None = None,
    redis_cell: str = CELL_REDIS,
    **overrides: Any,
) -> AsyncIterator[Fleet]:
    cfg = WorkerSettings.model_validate({"cell": cell, **FAST, **overrides})
    redis_cfg = RedisOnly().redis  # type: ignore[call-arg]
    redis: Redis = client.core(redis_cfg)
    cell_redis: Redis = client.cell(redis_cfg, redis_cell, block_ms=int(cfg.heartbeat_s * 1000))
    otp = MailpitOtp(board.settings.mailpit.api_url)
    fleet = Fleet(
        cfg=cfg,
        claims_cfg=claims_cfg or ClaimSettings(),
        engine=db.worker,
        events=redis,
        stream=cell_redis,
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
        await cell_redis.aclose()


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


@asynccontextmanager
async def running_control(db: Db, board: Board, cell: str, redis_cell: str = CELL_REDIS) -> AsyncIterator[Control]:
    redis_cfg = RedisOnly().redis  # type: ignore[call-arg]
    core, cell_redis = client.core(redis_cfg), client.cell(redis_cfg, redis_cell, block_ms=200)
    http = httpx.AsyncClient(timeout=5)
    control = Control(
        cfg=ControlSettings(cell=cell, tenant_refresh_s=0.5, read_block_ms=200, unknown_grace_ms=500),
        claims_cfg=ClaimSettings(reconcile_interval_s=0.5, outbox_poll_ms=100),
        engine=db.app,
        core=core,
        cell_redis=cell_redis,
        vault=Vault(db.envelope),
        targets=load_targets(ROOT / "config"),
        base_urls={"demo-board": board.url},
        http=http,
    )
    await control.start()
    try:
        yield control
    finally:
        await control.stop()
        await http.aclose()
        await core.aclose()
        await cell_redis.aclose()


async def add_filter(db: Db, tenant_id: UUID, name: str = "everything", min_rate_usd: int = 0) -> UUID:
    fid = uuid4()
    async with tenant_tx(db.app, tenant_id) as conn:
        await conn.execute(
            text("INSERT INTO filters (tenant_id, id, name, min_rate_usd) VALUES (:t, :i, :n, :r)"),
            {"t": tenant_id, "i": fid, "n": name, "r": min_rate_usd},
        )
    return fid


def dump_tasks() -> str:
    """Debug aid: what every running task is waiting on."""
    return "\n".join(f"--- task {t.get_name()}\n" + _awaiting(t) for t in asyncio.all_tasks())
