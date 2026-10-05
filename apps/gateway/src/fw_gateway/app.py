"""Live-update gateway: server-sent events for the console (`GET /v1/stream`).

Each instance subscribes ONCE per tenant to the tenant's events channel in core Redis and fans the
messages out to its own connected clients. Redis load therefore grows with tenants, not viewers,
and instances scale horizontally behind a load balancer with no sticky sessions. A client that
cannot keep up (its bounded queue is full) is disconnected rather than slowing everyone else."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from sse_starlette import EventSourceResponse, ServerSentEvent

from fw_core.db import make_engine, system_tx
from fw_core.logs import setup_logging
from fw_core.settings import GatewayAppSettings, load
from fw_queue import client, keys, sessions
from fw_queue.sessions import Principal

log = logging.getLogger(__name__)

DROPPED = object()  # queued to a client that fell behind: its stream ends


@dataclass(eq=False)
class Listener:
    queue: asyncio.Queue[Any]


@dataclass
class Hub:
    redis: Redis
    client_queue: int
    listeners: dict[UUID, set[Listener]] = field(default_factory=dict)
    tasks: dict[UUID, asyncio.Task[None]] = field(default_factory=dict)

    @property
    def count(self) -> int:
        return sum(len(s) for s in self.listeners.values())

    def join(self, tenant_id: UUID) -> Listener:
        listener = Listener(asyncio.Queue(self.client_queue))
        self.listeners.setdefault(tenant_id, set()).add(listener)
        if tenant_id not in self.tasks:
            self.tasks[tenant_id] = asyncio.create_task(self._pump(tenant_id), name=f"pump-{tenant_id}")
        return listener

    def leave(self, tenant_id: UUID, listener: Listener) -> None:
        group = self.listeners.get(tenant_id)
        if group is None:
            return
        group.discard(listener)
        if not group:
            del self.listeners[tenant_id]
            task = self.tasks.pop(tenant_id, None)
            if task is not None:
                task.cancel()

    async def _pump(self, tenant_id: UUID) -> None:
        pubsub = self.redis.pubsub()
        try:
            await pubsub.subscribe(keys.events_channel(tenant_id))
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message is None:
                    continue
                data = message["data"]
                payload = data.decode() if isinstance(data, bytes) else str(data)
                for listener in list(self.listeners.get(tenant_id, ())):
                    try:
                        listener.queue.put_nowait(payload)
                    except asyncio.QueueFull:
                        self._evict(tenant_id, listener)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("event pump failed", extra={"tenant_id": str(tenant_id)})
            self.tasks.pop(tenant_id, None)
            for listener in list(self.listeners.get(tenant_id, ())):
                self._evict(tenant_id, listener)
        finally:
            with contextlib.suppress(Exception):
                await pubsub.aclose()  # type: ignore[no-untyped-call]

    def _evict(self, tenant_id: UUID, listener: Listener) -> None:
        """Stops feeding a listener and tells its stream to end."""
        self.leave(tenant_id, listener)
        with contextlib.suppress(asyncio.QueueEmpty):
            while True:
                listener.queue.get_nowait()
        listener.queue.put_nowait(DROPPED)

    async def close(self) -> None:
        for task in self.tasks.values():
            task.cancel()
        for task in list(self.tasks.values()):
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self.tasks.clear()


@dataclass
class Gateway:
    cfg: GatewayAppSettings
    engine: AsyncEngine
    redis: Redis
    hub: Hub
    demo_tenant: UUID | None = None

    async def principal(self, request: Request) -> Principal:
        found = await sessions.load(self.redis, request.cookies.get(self.cfg.auth.cookie_name))
        if found is not None:
            return found
        if self.cfg.demo.public_read:
            if self.demo_tenant is None:
                async with system_tx(self.engine) as conn:
                    self.demo_tenant = (
                        await conn.execute(
                            text("SELECT id FROM tenants WHERE slug = :s"), {"s": self.cfg.demo.tenant_slug}
                        )
                    ).scalar_one_or_none()
            if self.demo_tenant is not None:
                return Principal(self.demo_tenant, "public")
        raise HTTPException(401, "sign in required")


def create_app(cfg: GatewayAppSettings | None = None) -> FastAPI:
    cfg = cfg or load(GatewayAppSettings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        engine = make_engine(cfg.app_db.dsn, cfg.app_db, "fw-gateway")
        redis = client.core(cfg.redis)
        gateway = Gateway(cfg, engine, redis, Hub(redis, cfg.gateway.client_queue))
        app.state.gateway = gateway
        try:
            yield
        finally:
            await gateway.hub.close()
            await redis.aclose()
            await engine.dispose()

    app = FastAPI(title="Fleetwright live updates", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/healthz")
    async def healthz(request: Request) -> dict[str, Any]:
        gateway: Gateway = request.app.state.gateway
        await gateway.redis.ping()
        return {"status": "ok", "clients": gateway.hub.count}

    @app.get("/v1/stream")
    async def stream(request: Request) -> EventSourceResponse:
        gateway: Gateway = request.app.state.gateway
        who = await gateway.principal(request)
        if gateway.hub.count >= cfg.gateway.max_clients:
            raise HTTPException(503, "too many live connections; the console falls back to polling")
        listener = gateway.hub.join(who.tenant_id)

        async def events() -> AsyncIterator[ServerSentEvent]:
            try:
                yield ServerSentEvent(json.dumps({"type": "hello", "role": who.role}), event="hello")
                while True:
                    item = await listener.queue.get()
                    if item is DROPPED:
                        return
                    yield ServerSentEvent(item, event="update")
            finally:
                gateway.hub.leave(who.tenant_id, listener)

        return EventSourceResponse(
            events(), ping=cfg.gateway.keepalive_s, headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"}
        )

    return app


def main() -> None:
    cfg = load(GatewayAppSettings)
    setup_logging("gateway", cfg.log_level)
    uvicorn.run(create_app(cfg), host=cfg.gateway.host, port=cfg.gateway.port, log_config=None)
