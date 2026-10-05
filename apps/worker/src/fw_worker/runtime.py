"""Worker runtime: one Chromium per process, one browser context per slot. Each slot holds one
account (database mutex), keeps that account signed in (vault restore, sign-in with OTP, refresh
before expiry), and runs its role's behaviour (watcher or claimer, added in Phase 5). The fleet
heartbeats every slot, measures memory, recycles contexts, and drains cleanly on shutdown."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import socket
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from importlib.metadata import version
from typing import Any, Literal
from uuid import UUID

import psutil
from playwright.async_api import Browser, BrowserContext, Page
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from fw_browser import captcha, login
from fw_browser.evidence import EvidenceStore
from fw_browser.otp import POLL_S, OtpProvider
from fw_browser.profiles import Profiles
from fw_browser.proxy import ProxyPool
from fw_core.db import system_tx, tenant_tx
from fw_core.settings import ClaimSettings, WorkerSettings
from fw_core.targets import Targets
from fw_core.vault import Account, StoredSession, Vault
from fw_queue import keys
from fw_worker import accounts
from fw_worker.otp_manual import ManualOtp

log = logging.getLogger(__name__)

Role = Literal["watcher", "claimer"]
SlotState = Literal["starting", "signing_in", "ready", "paused", "failed", "stopped"]
Behaviour = Callable[["Slot"], Awaitable[None]]


class SessionLost(Exception):
    """The target no longer accepts the slot's session."""


class ProcessMeter:
    """Memory and CPU of this process plus every child (Playwright driver, Chromium processes).

    Memory is USS — memory unique to each process — because Chromium processes share a lot of
    memory and summing resident sizes counts it many times. Process objects are kept between
    samples: psutil's CPU % is measured against the previous sample of the same object."""

    def __init__(self) -> None:
        self._procs: dict[int, psutil.Process] = {}

    def sample(self) -> tuple[int, float]:
        me = psutil.Process()
        current = {p.pid: p for p in (me, *me.children(recursive=True))}
        self._procs = {pid: self._procs.get(pid, proc) for pid, proc in current.items()}
        uss, cpu = 0, 0.0
        for proc in self._procs.values():
            with contextlib.suppress(psutil.Error):
                uss += proc.memory_full_info().uss
                cpu += proc.cpu_percent(None)
        return uss // (1024 * 1024), cpu


@dataclass
class Fleet:
    """Everything a slot needs, created once per process (see fw_worker.__main__)."""

    cfg: WorkerSettings
    claims_cfg: ClaimSettings
    engine: AsyncEngine
    events: Redis  # core Redis: dashboard events
    stream: Redis  # this cell's Redis: detected and act streams
    browser: Browser
    vault: Vault
    targets: Targets
    base_urls: dict[str, str]
    profiles: Profiles
    proxies: ProxyPool
    evidence: EvidenceStore
    email_otp: OtpProvider
    behaviours: dict[Role, Behaviour]
    process_id: str = field(default_factory=lambda: f"{socket.gethostname()}-{os.getpid()}")
    slots: list[Slot] = field(default_factory=list)
    stopping: asyncio.Event = field(default_factory=asyncio.Event)
    memory_mb: int = 0
    clock_offset_ms: float | None = None  # database clock minus this host's clock
    tenants: list[UUID] = field(default_factory=list)
    generation: int = 0
    meter: ProcessMeter = field(default_factory=ProcessMeter)
    _tasks: list[asyncio.Task[None]] = field(default_factory=list)

    def __post_init__(self) -> None:
        # The ACTING window must fit inside the lease, or a healthy but slow action is declared
        # lost (UNKNOWN) while it is still running.
        if self.claims_cfg.lease_ttl_ms <= self.cfg.action_timeout_ms:
            raise ValueError("claims.lease_ttl_ms must be greater than worker.action_timeout_ms")

    # ---------------- lifecycle ----------------

    async def start(self) -> None:
        await self.measure_clock()
        await self._apply_plan(await self._tenants_in_cell())
        self._tasks.append(asyncio.create_task(self._heartbeat_loop(), name="heartbeat"))
        log.info("fleet started", extra={"slots": len(self.slots), "tenants": len(self.tenants), "cell": self.cfg.cell})

    async def _tenants_in_cell(self) -> list[UUID]:
        async with system_tx(self.engine) as conn:
            return [
                r.tenant_id
                for r in await conn.execute(
                    text("SELECT tenant_id FROM tenant_cells WHERE cell_id = :c ORDER BY tenant_id"),
                    {"c": self.cfg.cell},
                )
            ]

    async def _apply_plan(self, tenants: list[UUID]) -> None:
        """(Re)plans the slots. On any change in the cell's tenants (a move) every current slot is
        retired — it finishes its operation, releases its account and stops — and a fresh plan
        starts. Simple and correct; moves are rare."""
        for slot in self.slots:
            slot.retired = True
        self.generation += 1
        self.tenants = tenants
        self.slots = plan_slots(self, tenants)
        self._tasks += [asyncio.create_task(s.run(), name=s.id) for s in self.slots]

    async def measure_clock(self) -> None:
        """Offset of the database clock from this host's clock, from a round trip (midpoint rule).
        Detection times are corrected with it so latency is measured on one clock."""
        t0 = time.time()
        async with system_tx(self.engine) as conn:
            db_now = (await conn.execute(text("SELECT clock_timestamp()"))).scalar_one()
        t1 = time.time()
        self.clock_offset_ms = (db_now.timestamp() - (t0 + t1) / 2) * 1000

    def db_now(self) -> datetime:
        return datetime.now(UTC) + timedelta(milliseconds=self.clock_offset_ms or 0.0)

    async def drain(self) -> None:
        """Stop taking work, let in-flight operations finish (bounded), release every account."""
        self.stopping.set()
        await self._heartbeat(state_override="draining")
        slot_tasks = [t for t in self._tasks if t.get_name() != "heartbeat" and not t.done()]
        _, pending = await asyncio.wait(slot_tasks, timeout=self.cfg.drain_timeout_s) if slot_tasks else (set(), set())
        for task in pending:
            task.cancel()
        for task in self._tasks:
            if task.get_name() == "heartbeat":
                task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        for slot in self.slots:
            await slot.close(release=True)
        await self._heartbeat(state_override="stopped")
        log.info("fleet drained", extra={"slots": len(self.slots), "forced": len(pending)})

    # ---------------- heartbeat ----------------

    async def _heartbeat_loop(self) -> None:
        while not self.stopping.is_set():
            try:
                await self.measure_clock()
                tenants = await self._tenants_in_cell()
                if tenants != self.tenants:
                    log.info("cell tenants changed; re-planning slots", extra={"cell": self.cfg.cell})
                    await self._apply_plan(tenants)
                await self._heartbeat()
            except Exception:
                log.exception("heartbeat failed")
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self.stopping.wait(), self.cfg.heartbeat_s)

    async def _heartbeat(self, state_override: str | None = None) -> None:
        self.memory_mb, cpu = self.meter.sample()
        per_slot = self.memory_mb // max(1, sum(s.context is not None for s in self.slots))
        for slot in self.slots:
            async with tenant_tx(self.engine, slot.tenant_id) as conn:
                if (
                    slot.account is not None
                    and state_override is None
                    and not await accounts.renew(conn, slot.account, slot.id, self.cfg.account_hold_s)
                ):
                    log.warning("account hold lost; slot stops using it", extra={"slot": slot.id})
                    slot.hold_lost = True
                await conn.execute(
                    text(
                        """INSERT INTO workers (tenant_id, id, process_id, cell_id, mode, account_id, state, version,
                                                memory_mb, cpu_pct, clock_offset_ms, heartbeat_at)
                           VALUES (:t, :i, :p, :c, :m, :a, :s, :v, :mem, :cpu, :off, clock_timestamp())
                           ON CONFLICT (tenant_id, id) DO UPDATE SET process_id = EXCLUDED.process_id,
                             account_id = EXCLUDED.account_id, state = EXCLUDED.state, version = EXCLUDED.version,
                             memory_mb = EXCLUDED.memory_mb, cpu_pct = EXCLUDED.cpu_pct,
                             clock_offset_ms = EXCLUDED.clock_offset_ms, heartbeat_at = EXCLUDED.heartbeat_at"""
                    ),
                    {
                        "t": slot.tenant_id,
                        "i": slot.id,
                        "p": self.process_id,
                        "c": self.cfg.cell,
                        "m": slot.role,
                        "a": None if slot.account is None else slot.account.id,
                        "s": state_override or ("running" if slot.state != "stopped" else "stopped"),
                        "v": version("fw-worker"),
                        "mem": per_slot if slot.context is not None else None,
                        "cpu": cpu,
                        "off": self.clock_offset_ms,
                    },
                )

    async def emit(self, tenant_id: UUID, event: dict[str, Any]) -> None:
        """Live event for the dashboard (no secrets: ids, states and timings only)."""
        payload = {"at": datetime.now(UTC).isoformat(), **event}
        try:
            await self.events.publish(keys.events_channel(tenant_id), json.dumps(payload, default=str))
        except Exception:
            log.warning("event publish failed", extra={"type": event.get("type")})

    def otp_for(self, slot: Slot, account: Account) -> OtpProvider:
        if account.otp_channel == "email":
            return self.email_otp
        if account.otp_channel == "manual":
            return ManualOtp(
                self.events,
                account.tenant_id,
                account.id,
                lambda: self.emit(
                    account.tenant_id, {"type": "otp_required", "slot": slot.id, "account_id": account.id}
                ),
                POLL_S,
            )
        raise login.SignInFailed(f"OTP channel {account.otp_channel!r} is not supported yet")


def plan_slots(fleet: Fleet, tenants: list[UUID]) -> list[Slot]:
    """Spreads the process's contexts across the cell's tenants; each tenant's first `watchers`
    slots watch, the rest claim."""
    if not tenants:
        return []
    slots: list[Slot] = []
    watchers: dict[UUID, int] = dict.fromkeys(tenants, 0)
    for n in range(fleet.cfg.contexts):
        tenant = tenants[n % len(tenants)]
        role: Role = "watcher" if watchers[tenant] < fleet.cfg.watchers else "claimer"
        watchers[tenant] += role == "watcher"
        slots.append(Slot(fleet, f"{fleet.process_id}-g{fleet.generation}-s{n}", tenant, role))
    return slots


@dataclass
class Slot:
    fleet: Fleet
    id: str
    tenant_id: UUID
    role: Role
    state: SlotState = "starting"
    account: Account | None = None
    context: BrowserContext | None = None
    page: Page | None = None
    session: StoredSession | None = None
    actions: int = 0
    sign_ins: int = 0
    captchas: int = 0
    restores: int = 0
    hold_lost: bool = False
    retired: bool = False  # the fleet re-planned; finish, release the account, stop
    csrf: str | None = None  # the target's anti-forgery token for this session
    last_error: str | None = None
    _cleanup: set[asyncio.Task[None]] = field(default_factory=set, repr=False)

    @property
    def cfg(self) -> WorkerSettings:
        return self.fleet.cfg

    async def run(self) -> None:
        while not self.fleet.stopping.is_set() and not self.retired:
            try:
                if not await self.prepare():
                    await self._pause(self.cfg.restart_backoff_s)
                    continue
                await self.fleet.behaviours[self.role](self)
            except captcha.CaptchaNeedsOperator:
                await self._set_state("paused", "captcha needs an operator")
                await self._pause(self.cfg.restart_backoff_s)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.last_error = type(exc).__name__
                log.warning("slot failed; restarting it", extra={"slot": self.id, "error": type(exc).__name__})
                log.debug("slot failure detail", extra={"slot": self.id}, exc_info=True)
                await self._set_state("failed", type(exc).__name__)
                await self.close(release=False)
                await self._pause(self.cfg.restart_backoff_s)
        await self._set_state("stopped")
        if self.retired:
            await self.close(release=True)
            with contextlib.suppress(Exception):
                async with tenant_tx(self.fleet.engine, self.tenant_id) as conn:
                    await conn.execute(
                        text("UPDATE workers SET state = 'stopped' WHERE tenant_id = :t AND id = :i"),
                        {"t": self.tenant_id, "i": self.id},
                    )

    async def prepare(self) -> bool:
        """Account held, context open, session valid. False if there is nothing to do yet."""
        if self.hold_lost:
            self.hold_lost = False
            await self._set_state("paused", "account hold lost")
            await self.close(release=False)
            self.account = None
        if self.account is None:
            async with tenant_tx(self.fleet.engine, self.tenant_id) as conn:
                self.account = await accounts.acquire(conn, self.tenant_id, self.id, self.cfg.account_hold_s)
            if self.account is None:
                await self._set_state("paused", "no free account")
                return False
        if self.context is not None and self.actions >= self.cfg.recycle_after_actions:
            log.info("recycling context", extra={"slot": self.id, "actions": self.actions})
            await self.close(release=False)
        if self.context is None:
            await self._open_context()
        if self.session is None or self.session.needs_refresh(datetime.now(UTC), self.cfg.session_refresh_share):
            await self.operation("sign-in", self._sign_in)
        if self.state != "ready":
            await self._set_state("ready")
        return True

    def due_for_attention(self) -> bool:
        """Behaviours call this between iterations and return when it is True."""
        return (
            self.fleet.stopping.is_set()
            or self.retired
            or self.hold_lost
            or self.actions >= self.cfg.recycle_after_actions
            or self.session is None
            or self.session.needs_refresh(datetime.now(UTC), self.cfg.session_refresh_share)
        )

    async def operation[T](
        self, label: str, fn: Callable[[], Awaitable[T]], expected: tuple[type[Exception], ...] = ()
    ) -> T:
        """Runs fn inside a trace chunk; on an unexpected failure the chunk and a screenshot become
        evidence. `expected` failures (e.g. a session that simply expired) are not evidence."""
        assert self.context is not None
        traced = self.cfg.evidence_on_failure
        if traced:
            await self.context.tracing.start_chunk(title=label)
        try:
            result = await fn()
        except expected:
            if traced:
                await self.context.tracing.stop_chunk()
            raise
        except Exception:
            if traced:
                with contextlib.suppress(Exception):
                    folder = await self.fleet.evidence.capture(self.context, self.page, self.tenant_id, label)
                    await self.fleet.emit(
                        self.tenant_id, {"type": "evidence", "slot": self.id, "label": label, "path": folder.name}
                    )
            raise
        if traced:
            await self.context.tracing.stop_chunk()
        return result

    async def close(self, release: bool) -> None:
        if self.context is not None:
            with contextlib.suppress(Exception):
                await asyncio.wait_for(self.context.close(), self.cfg.action_timeout_ms / 1000)
        self.context, self.page = None, None
        if release and self.account is not None:
            with contextlib.suppress(Exception):
                async with tenant_tx(self.fleet.engine, self.tenant_id) as conn:
                    await accounts.release(conn, self.account, self.id)
            self.account, self.session = None, None

    # ---------------- internals ----------------

    async def _open_context(self) -> None:
        assert self.account is not None
        async with tenant_tx(self.fleet.engine, self.tenant_id) as conn:
            self.session = await self.fleet.vault.load(conn, self.account)
        exit_ = self.fleet.proxies.exit_for(str(self.account.id), asyncio.get_running_loop().time())
        options: dict[str, Any] = self.fleet.profiles.for_group(self.account.account_group).context_options()
        proxy = ProxyPool.playwright_proxy(exit_)
        if proxy is not None:
            options["proxy"] = proxy
        if self.session is not None:
            options["storage_state"] = self.session.storage_state
        self.context = await self.fleet.browser.new_context(**options)
        self.context.set_default_timeout(self.cfg.action_timeout_ms)
        if self.cfg.evidence_on_failure:
            await self.context.tracing.start(screenshots=True, snapshots=True)
            await self.context.tracing.stop_chunk()  # chunks are opened per operation
        self.page = await self.context.new_page()
        self.actions = 0
        if self.session is not None:
            try:
                await self.operation("restore-session", self.check_session, (SessionLost,))
                self.restores += 1
                log.info("session restored from vault", extra={"slot": self.id})
            except SessionLost:
                self.session = None

    async def check_session(self) -> None:
        """Asks the target who we are. 401 = the session is gone; a captcha is solved or escalated."""
        assert self.context is not None and self.account is not None
        spec = self.fleet.targets.get(self.account.target)
        response = await self.context.request.get(self.fleet.base_urls[self.account.target] + spec.api.me)
        if response.status == 401:
            raise SessionLost("target rejected the session")
        if response.status == 403 and "captcha" in (await response.text()):
            await self.solve_captcha()
            return
        if not response.ok:
            raise SessionLost(f"session check returned {response.status}")

    async def keep_alive(self) -> None:
        """Session check between behaviour iterations. A lost session is marked expired in the vault
        and the slot signs in again on its next prepare()."""
        try:
            await self.operation("session-check", self.check_session, (SessionLost,))
        except SessionLost:
            assert self.account is not None
            log.info("session lost; signing in again", extra={"slot": self.id})
            async with tenant_tx(self.fleet.engine, self.tenant_id) as conn:
                await Vault.mark(conn, self.account, "expired")
            self.session = None

    async def solve_captcha(self) -> None:
        assert self.page is not None and self.account is not None
        spec = self.fleet.targets.get(self.account.target)
        await self.fleet.emit(self.tenant_id, {"type": "captcha", "slot": self.id, "account_id": self.account.id})
        challenge = spec.captcha.url.replace("**", "").lstrip("*")
        await self.page.goto(self.fleet.base_urls[self.account.target] + challenge)
        await captcha.solve(self.page, spec.captcha, self.cfg.action_timeout_ms)
        self.captchas += 1

    async def _sign_in(self) -> None:
        assert self.context is not None and self.page is not None and self.account is not None
        account = self.account
        await self._set_state("signing_in")
        spec = self.fleet.targets.get(account.target)
        async with tenant_tx(self.fleet.engine, self.tenant_id) as conn:
            password = await self.fleet.vault.password(conn, account)
        # The old page's own scripts react to a lost session (the board redirects itself to its
        # login page), which would interrupt our navigation: sign in on a fresh page instead. The old
        # page is closed in the background with a bound: Playwright's close() has no timeout and was
        # seen to hang forever on a page in the middle of its own redirect.
        old, self.page = self.page, await self.context.new_page()
        self._background(old.close(), "close-page")
        await self.context.clear_cookies()
        await login.sign_in(
            self.page,
            self.fleet.base_urls[account.target],
            spec,
            username=account.username,
            password=password,
            otp_address=account.email,
            otp=self.fleet.otp_for(self, account),
            timeouts=login.SignInTimeouts(self.cfg.login_timeout_ms, self.cfg.otp_wait_s, self.cfg.otp_clock_margin_s),
        )
        del password
        state = await self.context.storage_state()
        async with tenant_tx(self.fleet.engine, self.tenant_id) as conn:
            self.session = await self.fleet.vault.save(conn, account, dict(state))
        self.sign_ins += 1
        self.csrf = None
        log.info("signed in", extra={"slot": self.id, "account_id": str(account.id)})
        await self.fleet.emit(self.tenant_id, {"type": "signed_in", "slot": self.id, "account_id": account.id})

    def _background(self, aw: Awaitable[object], what: str) -> None:
        """Fire-and-forget cleanup, bounded by the action timeout; failures are logged, not raised."""

        async def bounded() -> None:
            try:
                await asyncio.wait_for(aw, self.cfg.action_timeout_ms / 1000)
            except Exception as exc:
                log.warning(
                    "background cleanup failed", extra={"slot": self.id, "what": what, "error": type(exc).__name__}
                )

        task = asyncio.create_task(bounded(), name=f"{self.id}-{what}")
        self._cleanup.add(task)
        task.add_done_callback(self._cleanup.discard)

    async def _set_state(self, state: SlotState, note: str | None = None) -> None:
        if state == self.state:
            return
        self.state = state
        await self.fleet.emit(
            self.tenant_id, {"type": "slot", "slot": self.id, "role": self.role, "state": state, "note": note}
        )

    async def _pause(self, seconds: float) -> None:
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self.fleet.stopping.wait(), seconds)


async def idle(slot: Slot) -> None:
    """Phase 4 behaviour: keep the session alive and return when the slot needs attention."""
    while not slot.due_for_attention():
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(slot.fleet.stopping.wait(), slot.cfg.heartbeat_s)
        if not slot.fleet.stopping.is_set():
            await slot.keep_alive()
