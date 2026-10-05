"""Per-cell control loops (`python -m fw_coordinator.control`):

- dispatcher: reads detections from the cell's `detected` streams, applies the tenant's active
  filters, drops fast-path duplicates, queues a claim (claim + outbox row in one transaction) and
  publishes it to the `act` stream right away;
- relay: publishes outbox rows that were left behind (crash, Redis outage, re-queued claims);
- reconciler: applies lease timeouts and resolves UNKNOWN claims by asking the target what the
  account actually booked (with the session from the vault), never by retrying.

A tenant belongs to exactly one cell (tenant_cells); the loops refresh that list, so a moved
tenant is dropped here and picked up by the new cell's control process."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import signal
import socket
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID

import httpx
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from fw_core import claims, filters
from fw_core.crypto import Envelope
from fw_core.db import make_engine, system_tx, tenant_tx
from fw_core.logs import setup_logging
from fw_core.settings import ClaimSettings, ControlAppSettings, ControlSettings, load
from fw_core.targets import Targets, load_targets
from fw_core.vault import Account, Vault
from fw_queue import client, keys, outbox, streams

log = logging.getLogger(__name__)


@dataclass
class Control:
    cfg: ControlSettings
    claims_cfg: ClaimSettings
    engine: AsyncEngine
    core: Redis  # events and filter-change notifications
    cell_redis: Redis  # this cell's streams
    vault: Vault
    targets: Targets
    base_urls: dict[str, str]
    http: httpx.AsyncClient
    consumer: str = field(default_factory=lambda: f"{socket.gethostname()}-{os.getpid()}")
    tenants: list[UUID] = field(default_factory=list)
    stats: Counter[str] = field(default_factory=Counter)
    stopping: asyncio.Event = field(default_factory=asyncio.Event)
    _rules: dict[UUID, tuple[list[filters.Filter], list[filters.Schedule], float]] = field(default_factory=dict)
    _tasks: list[asyncio.Task[None]] = field(default_factory=list)

    # ---------------- lifecycle ----------------

    async def start(self) -> None:
        await self.refresh_tenants()
        for name, loop in (
            ("tenants", self._tenant_loop),
            ("dispatch", self._dispatch_loop),
            ("relay", self._relay_loop),
            ("reconcile", self._reconcile_loop),
            ("filters", self._filter_change_loop),
        ):
            self._tasks.append(asyncio.create_task(self._guard(name, loop), name=name))
        log.info("control started", extra={"cell": self.cfg.cell, "tenants": len(self.tenants)})

    async def stop(self) -> None:
        self.stopping.set()
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)

    async def _guard(self, name: str, loop: Any) -> None:
        """Keeps a loop alive: an error is logged and the loop restarts after a short pause."""
        while not self.stopping.is_set():
            try:
                await loop()
            except asyncio.CancelledError:
                raise
            except Exception:
                self.stats[f"{name}_errors"] += 1
                log.exception("control loop failed; restarting", extra={"loop": name})
                await self._sleep(self.cfg.tenant_refresh_s)

    async def _sleep(self, seconds: float) -> None:
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self.stopping.wait(), seconds)

    # ---------------- tenants and rules ----------------

    async def refresh_tenants(self) -> None:
        async with system_tx(self.engine) as conn:
            current = [
                r.tenant_id
                for r in await conn.execute(
                    text("SELECT tenant_id FROM tenant_cells WHERE cell_id = :c ORDER BY tenant_id"),
                    {"c": self.cfg.cell},
                )
            ]
        for t in set(current) - set(self.tenants):
            await streams.ensure_group(self.cell_redis, keys.detected_stream(t), keys.DISPATCHER_GROUP)
            log.info("tenant joined cell", extra={"tenant_id": str(t), "cell": self.cfg.cell})
        for t in set(self.tenants) - set(current):
            self._rules.pop(t, None)
            log.info("tenant left cell", extra={"tenant_id": str(t), "cell": self.cfg.cell})
        self.tenants = current

    async def _tenant_loop(self) -> None:
        while not self.stopping.is_set():
            await self._sleep(self.cfg.tenant_refresh_s)
            await self.refresh_tenants()

    async def rules(self, tenant_id: UUID) -> list[filters.Filter]:
        """Active filters right now; reloaded on a change notification or after filter_reload_s."""
        loop_now = asyncio.get_running_loop().time()
        cached = self._rules.get(tenant_id)
        if cached is None or loop_now - cached[2] > self.claims_cfg.filter_reload_s:
            async with tenant_tx(self.engine, tenant_id) as conn:
                fs, ss = await filters.load(conn, tenant_id)
            cached = (fs, ss, loop_now)
            self._rules[tenant_id] = cached
        return filters.active(cached[0], cached[1], datetime.now(UTC))

    async def _filter_change_loop(self) -> None:
        pubsub = self.core.pubsub()
        await pubsub.psubscribe(keys.filters_channel("*"))
        try:
            while not self.stopping.is_set():
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message is None:
                    continue
                channel = str(message["channel"])
                tenant = channel.split("{", 1)[-1].split("}", 1)[0]
                with contextlib.suppress(ValueError):
                    self._rules.pop(UUID(tenant), None)
                    self.stats["filter_reloads"] += 1
        finally:
            await cast(Any, pubsub).aclose()  # redis-py leaves PubSub.aclose unannotated

    # ---------------- dispatcher ----------------

    async def _dispatch_loop(self) -> None:
        idle_rounds = 0
        while not self.stopping.is_set():
            if not self.tenants:
                await self._sleep(self.cfg.tenant_refresh_s)
                continue
            names = [keys.detected_stream(t) for t in self.tenants]
            batch = await streams.read(
                self.cell_redis,
                names,
                keys.DISPATCHER_GROUP,
                self.consumer,
                self.cfg.read_count,
                self.cfg.read_block_ms,
            )
            idle_rounds = 0 if batch else idle_rounds + 1
            if idle_rounds and idle_rounds % 10 == 0:  # pick up messages a dead dispatcher never acked
                for name in names:
                    batch += await streams.reclaim(
                        self.cell_redis,
                        name,
                        keys.DISPATCHER_GROUP,
                        self.consumer,
                        self.claims_cfg.autoclaim_idle_ms,
                        self.cfg.read_count,
                        self.claims_cfg.max_deliveries,
                    )
            for msg in batch:
                await self.dispatch(msg)

    async def dispatch(self, msg: streams.Message) -> None:
        tenant_id = UUID(msg.stream.split("{", 1)[1].split("}", 1)[0])
        if tenant_id not in self.tenants:  # moved away; the new cell's watchers see it again
            await streams.ack(self.cell_redis, msg, keys.DISPATCHER_GROUP)
            return
        job: dict[str, Any] = json.loads(msg.fields["job"])
        match = filters.first_match(await self.rules(tenant_id), job)
        if match is None:
            self.stats["skipped_no_filter"] += 1
            await streams.ack(self.cell_redis, msg, keys.DISPATCHER_GROUP)
            return
        # Fast path: the first detection of a job owns the key; copies from other watchers stop
        # here. A redelivery of the owning message (dispatcher crashed) carries the same id.
        seen = keys.job_seen(tenant_id, msg.fields["key"])
        fresh = await self.cell_redis.set(seen, msg.id, nx=True, ex=self.cfg.seen_ttl_s)
        if not fresh and await self.cell_redis.get(seen) != msg.id:
            self.stats["skipped_duplicate"] += 1
            await streams.ack(self.cell_redis, msg, keys.DISPATCHER_GROUP)
            return
        detection = claims.Detection(
            key=msg.fields["key"],
            lane=f"{job.get('origin', '?')} → {job.get('destination', '?')}",
            rate_usd=int(job.get("rate_usd", 0)),
            published_at=_ts(msg.fields.get("published_at")),
            seen_at=_ts(msg.fields["seen_at"]) or datetime.now(UTC),
            clock_offset_ms=float(msg.fields["offset_ms"]) if msg.fields.get("offset_ms") else None,
            payload=job,
            filter_id=match.id,
        )
        async with tenant_tx(self.engine, tenant_id) as conn:
            claim_id = await claims.queue_claim(
                conn, tenant_id, detection, self.cfg.cell, f"dispatcher:{self.consumer}"
            )
        if claim_id is not None:
            self.stats["queued"] += 1
            await outbox.drain_tenant(
                self.engine,
                self.cell_redis,
                tenant_id,
                self.claims_cfg.outbox_batch,
                self.claims_cfg.stream_maxlen,
                self.cfg.cell,
            )
            await self.emit(tenant_id, {"type": "claim", "state": "QUEUED", "claim_id": claim_id, "key": detection.key})
        else:
            self.stats["skipped_existing_claim"] += 1
        await streams.ack(self.cell_redis, msg, keys.DISPATCHER_GROUP)

    # ---------------- relay ----------------

    async def _relay_loop(self) -> None:
        while not self.stopping.is_set():
            for t in list(self.tenants):
                sent = await outbox.drain_tenant(
                    self.engine,
                    self.cell_redis,
                    t,
                    self.claims_cfg.outbox_batch,
                    self.claims_cfg.stream_maxlen,
                    self.cfg.cell,
                )
                self.stats["relayed"] += sent
            await self._sleep(self.claims_cfg.outbox_poll_ms / 1000)

    # ---------------- reconciler ----------------

    async def _reconcile_loop(self) -> None:
        while not self.stopping.is_set():
            for t in list(self.tenants):
                await self.reconcile_tenant(t)
            await self._sleep(self.claims_cfg.reconcile_interval_s)

    async def reconcile_tenant(self, tenant_id: UUID) -> None:
        async with tenant_tx(self.engine, tenant_id) as conn:
            sweep = await claims.sweep_leases(
                conn, tenant_id, self.claims_cfg.queued_max_age_s, self.claims_cfg.outbox_batch, "reconciler"
            )
            pending = await claims.unknown_claims(
                conn, tenant_id, self.cfg.unknown_grace_ms, self.claims_cfg.outbox_batch
            )
        self.stats["requeued"] += len(sweep.requeued)
        self.stats["expired"] += len(sweep.expired)
        self.stats["unknown"] += len(sweep.unknown)
        for claim_id in sweep.unknown:
            await self.emit(tenant_id, {"type": "claim", "state": "UNKNOWN", "claim_id": claim_id})
        by_account: dict[UUID, list[claims.UnknownClaim]] = {}
        for u in pending:
            by_account.setdefault(u.account_id, []).append(u)
        for account_id, items in by_account.items():
            booked = await self.bookings(tenant_id, account_id)
            if booked is None:
                self.stats["reconcile_blocked"] += 1
                continue
            for u in items:
                async with tenant_tx(self.engine, tenant_id) as conn:
                    done = await claims.resolve_unknown(
                        conn,
                        tenant_id,
                        u.claim_id,
                        u.target_job_key in booked,
                        "reconciler",
                        "checked the target's bookings",
                    )
                if done:
                    self.stats["reconciled"] += 1
                    state = "confirmed" if u.target_job_key in booked else "not_booked"
                    await self.emit(
                        tenant_id, {"type": "claim", "state": "RECONCILED", "claim_id": u.claim_id, "resolution": state}
                    )

    async def bookings(self, tenant_id: UUID, account_id: UUID) -> set[str] | None:
        """The job keys the account holds on the target, read with its vault session; None if the
        target cannot be asked right now (no session, rejected, error) — the claim stays UNKNOWN."""
        async with tenant_tx(self.engine, tenant_id) as conn:
            row = (
                await conn.execute(
                    text(
                        """SELECT id, target, username, email, account_group, otp_channel FROM accounts
                           WHERE tenant_id = :t AND id = :a"""
                    ),
                    {"t": tenant_id, "a": account_id},
                )
            ).one_or_none()
            if row is None:
                return None
            account = Account(
                tenant_id, row.id, row.target, row.username, row.email, row.account_group, row.otp_channel
            )
            session = await self.vault.load(conn, account)
        if session is None:
            return None
        spec = self.targets.get(account.target)
        cookies = "; ".join(f"{c['name']}={c['value']}" for c in session.storage_state.get("cookies", []))
        try:
            reply = await self.http.get(self.base_urls[account.target] + spec.api.bookings, headers={"Cookie": cookies})
        except httpx.HTTPError:
            return None
        if reply.status_code != 200:
            return None
        return {str(b["ref"]) for b in reply.json().get("bookings", [])}

    # ---------------- events ----------------

    async def emit(self, tenant_id: UUID, event: dict[str, Any]) -> None:
        payload = {"at": datetime.now(UTC).isoformat(), **event}
        try:
            await self.core.publish(keys.events_channel(tenant_id), json.dumps(payload, default=str))
        except Exception:
            log.warning("event publish failed", extra={"type": event.get("type")})


def _ts(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


async def move_tenant(engine: AsyncEngine, tenant_id: UUID, to_cell: str, actor: str) -> int:
    """Moves a tenant to another cell. Workers and control loops of both cells notice within their
    refresh interval. Claims still QUEUED are dispatched again through the outbox, which the new
    cell's relay publishes on its own Redis (a duplicate delivery is harmless: one lease wins).
    Returns how many queued claims were re-dispatched."""
    async with system_tx(engine) as conn:
        await conn.execute(
            text(
                """UPDATE tenant_cells SET cell_id = :c, version = version + 1, moved_at = clock_timestamp()
                   WHERE tenant_id = :t"""
            ),
            {"t": tenant_id, "c": to_cell},
        )
    async with tenant_tx(engine, tenant_id) as conn:
        moved = await conn.execute(
            text(
                """WITH q AS (UPDATE claims SET cell_id = :c WHERE tenant_id = :t AND state = 'QUEUED' RETURNING tenant_id, id)
                   INSERT INTO outbox (tenant_id, topic, payload)
                   SELECT tenant_id, :topic, jsonb_build_object('claim_id', id) FROM q"""
            ),
            {"t": tenant_id, "c": to_cell, "topic": claims.DISPATCH_TOPIC},
        )
        await conn.execute(
            text(
                """INSERT INTO audit_log (tenant_id, actor, role, action, target, detail)
                   VALUES (:t, :a, 'system', 'tenant.move', :c, 'moved to another cell')"""
            ),
            {"t": tenant_id, "a": actor, "c": to_cell},
        )
        return int(moved.rowcount)


async def main() -> None:

    cfg = load(ControlAppSettings)
    setup_logging("control", cfg.log_level)
    engine = make_engine(cfg.app_db.dsn, cfg.app_db, f"fw-control-{cfg.control.cell}")
    core = client.core(cfg.redis)
    cell_redis = client.cell(cfg.redis, cfg.control.cell, block_ms=cfg.control.read_block_ms)
    http = httpx.AsyncClient(timeout=cfg.board_client.timeout_s)
    control = Control(
        cfg=cfg.control,
        claims_cfg=cfg.claims,
        engine=engine,
        core=core,
        cell_redis=cell_redis,
        vault=Vault(Envelope(cfg.vault.master_key_b64.get_secret_value(), cfg.vault.key_id)),
        targets=load_targets(cfg.config_dir),
        base_urls={"demo-board": cfg.board_client.internal_url},
        http=http,
    )
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop.set)
    await control.start()
    try:
        await stop.wait()
    finally:
        await control.stop()
        await http.aclose()
        await core.aclose()
        await cell_redis.aclose()
        await engine.dispose()


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())
