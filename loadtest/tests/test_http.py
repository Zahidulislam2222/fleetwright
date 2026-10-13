"""Real local coordinator HTTP and gateway SSE under bounded reads/reconnect/slow consumers."""

from __future__ import annotations

import asyncio
import contextlib
import json
import socket
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
import pytest
import uvicorn
from fastapi import FastAPI
from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from dbkit import Db, new_tenant
from fw_coordinator.api import create_app as api_app
from fw_core.crypto import Envelope
from fw_core.db import make_engine, system_tx
from fw_core.settings import CoordinatorSettings, GatewayAppSettings, load
from fw_gateway.app import DROPPED
from fw_gateway.app import create_app as gateway_app
from fw_queue import client, keys
from loadtest.http import HttpConfig, benchmark, percentiles, prepare_clients


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@asynccontextmanager
async def serving(app: FastAPI) -> AsyncIterator[str]:
    port = free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    task = asyncio.create_task(server.serve())
    try:
        async with asyncio.timeout(10):
            while not server.started:
                if task.done():
                    await task
                await asyncio.sleep(0.01)
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        await asyncio.wait_for(task, 10)


def test_no_remote_stress_and_nearest_rank_percentiles() -> None:
    raw = json.loads(Path("loadtest/http.json").read_text())
    for url in (
        "https://fleetwright.example.test/v1/overview",
        "http://localhost/v1/overview",
        "http://127.0.0.1@evil.test/",
    ):
        with pytest.raises(ValidationError):
            HttpConfig.model_validate({**raw, "api_url": url})
    assert percentiles([1, 2, 3, 4, 100])["p95_ms"] == 100


async def test_client_startup_keeps_active_io_timers_responsive(monkeypatch: pytest.MonkeyPatch) -> None:
    ticks = 0
    stop = asyncio.Event()

    def slow_client(**_kwargs: object) -> object:
        time.sleep(0.01)
        return object()

    async def heartbeat() -> None:
        nonlocal ticks
        while not stop.is_set():
            ticks += 1
            await asyncio.sleep(0.005)

    monkeypatch.setattr(httpx, "AsyncClient", slow_client)
    task = asyncio.create_task(heartbeat())
    try:
        clients = await prepare_clients(20, 1)
    finally:
        stop.set()
        await task
    assert len(clients) == 20
    assert ticks >= 5, "client trust-store startup blocked active I/O timers"


@pytest.mark.integration
async def test_real_api_and_gateway_bounded_mixed_load() -> None:
    # Python3.12 Windows Proactor's shutdown(SHUT_RDWR) raises WinError10054 before
    # server._detach on rapid SSE reconnects, leaving Server.wait_closed stuck. Use
    # a dedicated standard selector loop for this network-only benchmark; no browser
    # subprocesses or shared async database pools cross event loops.
    await asyncio.to_thread(selector_acceptance)


def selector_acceptance() -> None:
    with asyncio.Runner(loop_factory=asyncio.SelectorEventLoop) as runner:
        runner.run(local_acceptance())


async def local_acceptance() -> None:
    cfg = load(CoordinatorSettings)
    engine = make_engine(cfg.app_db.dsn, cfg.app_db, "local-capacity-acceptance")
    db = Db(engine, engine, engine, Envelope(cfg.vault.master_key_b64.get_secret_value(), cfg.vault.key_id))
    try:
        await real_mixed_load(db)
    finally:
        await engine.dispose()


async def warm_pool(engine: AsyncEngine, count: int) -> None:
    """Establish the steady-load DB pool before starting a timed network measurement.

    asyncpg's Windows TLS trust-store setup is synchronous for each cold connection. Holding
    acquisitions until all are ready prevents this preflight from repeatedly warming one socket.
    """
    ready: asyncio.Queue[None] = asyncio.Queue()
    release = asyncio.Event()

    async def acquire() -> None:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            ready.put_nowait(None)
            await release.wait()

    tasks = [asyncio.create_task(acquire()) for _ in range(count)]
    try:
        async with asyncio.timeout(30):
            for _ in range(count):
                await ready.get()
    finally:
        release.set()
        await asyncio.gather(*tasks)


async def real_mixed_load(db: Db) -> None:
    tenant = await new_tenant(db)
    async with system_tx(db.app) as conn:
        slug = await conn.scalar(text("SELECT slug FROM tenants WHERE id=:t"), {"t": tenant})
    api_cfg = load(CoordinatorSettings)
    api_cfg = api_cfg.model_copy(
        update={"demo": api_cfg.demo.model_copy(update={"tenant_slug": slug, "public_read": True})}
    )
    gateway_cfg = load(GatewayAppSettings)
    gateway_cfg = gateway_cfg.model_copy(
        update={"demo": gateway_cfg.demo.model_copy(update={"tenant_slug": slug, "public_read": True})}
    )
    gateway = gateway_app(gateway_cfg)
    redis = client.core(gateway_cfg.redis)
    stop = asyncio.Event()
    api = api_app(api_cfg)

    async def publish() -> None:
        while not stop.is_set():
            await redis.publish(
                keys.events_channel(tenant), json.dumps({"type": "benchmark", "benchmark_sent_at": time.time()})
            )
            await asyncio.sleep(0.05)

    try:
        async with serving(api) as api_url, serving(gateway) as sse_url:
            setup_started = time.monotonic()
            raw = json.loads(Path("loadtest/http.json").read_text())
            await warm_pool(api.state.services.engine, min(raw["api_clients"], api_cfg.app_db.pool_size))
            await warm_pool(gateway.state.gateway.engine, min(raw["sse_clients"], gateway_cfg.app_db.pool_size))
            assert await redis.ping()
            pool_setup_duration = time.monotonic() - setup_started
            cfg = HttpConfig.model_validate(
                {**raw, "api_url": api_url + "/v1/overview", "sse_url": sse_url + "/v1/stream"}
            )
            client_setup_started = time.monotonic()
            clients = await prepare_clients(cfg.api_clients + cfg.sse_clients, cfg.request_timeout_s)
            client_setup_duration = time.monotonic() - client_setup_started
            # Force a bounded queue overflow independently of OS/TCP read buffering.
            slow = gateway.state.gateway.hub.join(tenant)
            publisher = asyncio.create_task(publish())
            try:
                report = await benchmark(cfg, clients)
            finally:
                stop.set()
                await publisher
            report["hub_slow_consumer_evicted"] = slow.queue.get_nowait() is DROPPED
            report["database_pool_setup_duration_s"] = pool_setup_duration
            report["client_setup_duration_s"] = client_setup_duration
            cfg.report.write_text(json.dumps(report, indent=2))
            assert report["errors"] == {}, report
            assert report["api_requests"] > cfg.api_clients
            assert report["reconnects"] >= cfg.sse_clients
            assert report["event_delivery_latency"]["count"] > cfg.sse_clients
            assert report["hub_slow_consumer_evicted"]
            print(json.dumps(report), flush=True)
    finally:
        with contextlib.suppress(Exception):
            await redis.aclose()
