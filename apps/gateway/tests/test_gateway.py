"""The live-update gateway over a real socket: a signed-in viewer gets its own tenant's events and
no one else's, anonymous visitors see only the demo tenant, a client that falls behind is cut off
instead of slowing the rest, and the connection cap answers 503 so the console falls back to polling."""

from __future__ import annotations

import asyncio
import contextlib
import json
import socket
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest
import uvicorn
from pydantic_settings import SettingsConfigDict
from redis.asyncio import Redis
from sqlalchemy import text

from dbkit import Db, new_tenant
from fw_core.db import system_tx
from fw_core.settings import GatewayAppSettings
from fw_gateway.app import DROPPED, Gateway, create_app
from fw_queue import client, keys, sessions
from fw_queue.sessions import Principal

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[3]
WAIT_S = 10.0


class GatewayTestSettings(GatewayAppSettings):
    model_config = SettingsConfigDict(
        env_prefix="FW_", env_nested_delimiter="__", extra="ignore", env_file=ROOT / ".env"
    )


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


async def _settings(db: Db, **gateway: Any) -> tuple[GatewayAppSettings, UUID]:
    """Settings whose demo tenant is a fresh tenant of this test."""
    demo = await new_tenant(db)
    async with system_tx(db.app) as conn:
        slug = (await conn.execute(text("SELECT slug FROM tenants WHERE id = :t"), {"t": demo})).scalar_one()
    base = GatewayTestSettings()  # type: ignore[call-arg]
    cfg = base.model_copy(
        update={
            "demo": base.demo.model_copy(update={"tenant_slug": slug, "public_read": True}),
            "gateway": base.gateway.model_copy(update={"port": _free_port(), **gateway}),
        }
    )
    return cfg, demo


@asynccontextmanager
async def serving(cfg: GatewayAppSettings) -> AsyncIterator[tuple[str, Gateway]]:
    app = create_app(cfg)
    server = uvicorn.Server(
        uvicorn.Config(app, host="127.0.0.1", port=cfg.gateway.port, log_level="warning", lifespan="on")
    )
    task = asyncio.create_task(server.serve())
    loop = asyncio.get_running_loop()
    deadline = loop.time() + WAIT_S
    while not server.started:
        if task.done() or loop.time() > deadline:
            raise RuntimeError("gateway did not start")
        await asyncio.sleep(0.05)
    try:
        yield f"http://127.0.0.1:{cfg.gateway.port}", app.state.gateway
    finally:
        server.should_exit = True
        with contextlib.suppress(asyncio.CancelledError):
            await task


async def events(lines: AsyncIterator[str]) -> AsyncIterator[tuple[str, str]]:
    """(event, data) pairs from an SSE line stream; keep-alive comments are skipped."""
    name, data = "message", ""
    async for line in lines:
        if line.startswith("event:"):
            name = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            data = line.split(":", 1)[1].strip()
        elif line == "" and data:
            yield name, data
            name, data = "message", ""


async def subscribed(redis: Redis, tenant_id: UUID) -> None:
    """Waits until the gateway's pump listens, so a test's publish is not lost."""
    channel = keys.events_channel(tenant_id)
    for _ in range(int(WAIT_S / 0.05)):
        counts = {(k.decode() if isinstance(k, bytes) else k): v for k, v in await redis.pubsub_numsub(channel)}
        if counts.get(channel):
            return
        await asyncio.sleep(0.05)
    raise AssertionError("gateway never subscribed")


async def test_viewers_get_only_their_own_tenants_events(db: Db) -> None:
    cfg, demo = await _settings(db)
    tenant = await new_tenant(db)
    redis = client.core(cfg.redis)
    token, _ = await sessions.create(
        redis, Principal(tenant, "viewer", user_id=uuid4(), email="v@example.test"), cfg.auth.session_ttl_s
    )
    try:
        async with serving(cfg) as (url, _gw), httpx.AsyncClient(timeout=WAIT_S) as http:
            http.cookies.set(cfg.auth.cookie_name, token)
            async with http.stream("GET", f"{url}/v1/stream") as reply:
                assert reply.status_code == 200
                assert reply.headers["content-type"].startswith("text/event-stream")
                stream = events(reply.aiter_lines())
                kind, data = await asyncio.wait_for(anext(stream), WAIT_S)
                assert kind == "hello" and json.loads(data)["role"] == "viewer"
                await subscribed(redis, tenant)
                await redis.publish(keys.events_channel(demo), json.dumps({"type": "other-tenant"}))
                await redis.publish(keys.events_channel(tenant), json.dumps({"type": "mine", "n": 1}))
                kind, data = await asyncio.wait_for(anext(stream), WAIT_S)
                assert kind == "update" and json.loads(data) == {"type": "mine", "n": 1}
    finally:
        await redis.aclose()


async def test_anonymous_visitors_see_the_demo_tenant(db: Db) -> None:
    cfg, demo = await _settings(db)
    redis = client.core(cfg.redis)
    try:
        async with (
            serving(cfg) as (url, _gw),
            httpx.AsyncClient(timeout=WAIT_S) as http,
            http.stream("GET", f"{url}/v1/stream") as reply,
        ):
            stream = events(reply.aiter_lines())
            kind, data = await asyncio.wait_for(anext(stream), WAIT_S)
            assert json.loads(data)["role"] == "public"
            await subscribed(redis, demo)
            await redis.publish(keys.events_channel(demo), json.dumps({"type": "claim", "state": "CONFIRMED"}))
            kind, data = await asyncio.wait_for(anext(stream), WAIT_S)
            assert kind == "update" and json.loads(data)["state"] == "CONFIRMED"
        # with public reading off, an anonymous visitor is refused
        closed = cfg.model_copy(
            update={
                "demo": cfg.demo.model_copy(update={"public_read": False}),
                "gateway": cfg.gateway.model_copy(update={"port": _free_port()}),
            }
        )
        async with serving(closed) as (url, _gw), httpx.AsyncClient(timeout=WAIT_S) as http:
            assert (await http.get(f"{url}/v1/stream")).status_code == 401
    finally:
        await redis.aclose()


async def test_a_client_that_falls_behind_is_cut_off(db: Db) -> None:
    cfg, demo = await _settings(db, client_queue=3)
    redis = client.core(cfg.redis)
    try:
        async with serving(cfg) as (_url, gw):
            slow = gw.hub.join(demo)  # never reads its queue
            fast = gw.hub.join(demo)
            await subscribed(redis, demo)
            got: list[Any] = []
            for n in range(6):
                await redis.publish(keys.events_channel(demo), str(n))
                got.append(await asyncio.wait_for(fast.queue.get(), WAIT_S))
            assert got == [str(n) for n in range(6)]  # the fast reader lost nothing
            assert slow.queue.get_nowait() is DROPPED  # the slow one was told to go
            assert gw.hub.count == 1  # and is no longer fed
            gw.hub.leave(demo, fast)
            assert gw.hub.count == 0 and demo not in gw.hub.tasks
    finally:
        await redis.aclose()


async def test_the_connection_cap_answers_503(db: Db) -> None:
    cfg, _demo = await _settings(db, max_clients=1)
    async with serving(cfg) as (url, gw), httpx.AsyncClient(timeout=WAIT_S) as http:
        async with http.stream("GET", f"{url}/v1/stream") as first:
            assert first.status_code == 200
            await asyncio.wait_for(anext(events(first.aiter_lines())), WAIT_S)
            assert gw.hub.count == 1
            assert (await http.get(f"{url}/v1/stream")).status_code == 503
        health = (await http.get(f"{url}/healthz")).json()
        assert health["status"] == "ok"
