"""Bounded loopback-only HTTP/SSE measurement; never stress the public/shared server."""

from __future__ import annotations

import asyncio
import json
import math
import ssl
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import certifi
import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

from loadtest.density import atomic_json


class HttpConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    api_url: str
    sse_url: str
    api_clients: int = Field(ge=1, le=256)
    sse_clients: int = Field(ge=1, le=256)
    slow_clients: int = Field(ge=0, le=256)
    duration_s: float = Field(gt=0, le=3600)
    request_interval_s: float = Field(ge=0.01)
    request_timeout_s: float = Field(gt=0)
    reconnect_interval_s: float = Field(gt=0)
    slow_read_s: float = Field(gt=0)
    max_samples: int = Field(ge=1, le=1000000)
    report: Path

    @field_validator("api_url", "sse_url")
    @classmethod
    def loopback_only(cls, value: str) -> str:
        parts = urlsplit(value)
        if parts.scheme != "http" or parts.hostname not in {"127.0.0.1", "::1"} or parts.username or parts.password:
            raise ValueError("benchmark accepts literal HTTP loopback origins only")
        if parts.fragment or parts.query:
            raise ValueError("no URL query secrets/fragments permitted")
        return value


def percentiles(samples: list[float]) -> dict[str, float | int | None]:
    ordered = sorted(samples)
    return {
        "count": len(ordered),
        **{
            name: ordered[max(0, math.ceil(len(ordered) * share) - 1)] if ordered else None
            for name, share in (("p50_ms", 0.5), ("p95_ms", 0.95), ("p99_ms", 0.99))
        },
    }


async def prepare_clients(count: int, timeout_s: float) -> list[httpx.AsyncClient]:
    """SSL trust-store loading must not starve active server/Redis connection timers."""

    def construct() -> list[httpx.AsyncClient]:
        verified = ssl.create_default_context(cafile=certifi.where())
        return [
            httpx.AsyncClient(timeout=timeout_s, trust_env=False, follow_redirects=False, verify=verified)
            for _ in range(count)
        ]

    return await asyncio.to_thread(construct)


async def benchmark(cfg: HttpConfig, clients: list[httpx.AsyncClient] | None = None) -> dict[str, Any]:
    setup_started = time.monotonic()
    if clients is None:
        clients = await prepare_clients(cfg.api_clients + cfg.sse_clients, cfg.request_timeout_s)
    if len(clients) != cfg.api_clients + cfg.sse_clients:
        raise ValueError("prepared client count differs from configured workload")
    client_setup_duration = time.monotonic() - setup_started
    start = time.monotonic()
    deadline = start + cfg.duration_s
    latencies: list[float] = []
    connects: list[float] = []
    deliveries: list[float] = []
    errors: dict[str, int] = {}
    state: dict[str, int] = {
        "api_requests": 0,
        "sse_connections": 0,
        "sse_events": 0,
        "reconnects": 0,
        "slow_events": 0,
    }

    def failed(kind: str) -> None:
        errors[kind] = errors.get(kind, 0) + 1

    async def api_client(index: int) -> None:
        async with clients[index] as client:
            while time.monotonic() < deadline:
                before = time.perf_counter()
                try:
                    response = await client.get(cfg.api_url)
                    state["api_requests"] += 1
                    if len(latencies) < cfg.max_samples:
                        latencies.append((time.perf_counter() - before) * 1000)
                    if response.status_code != 200:
                        failed(f"http_{response.status_code}")
                except httpx.HTTPError as error:
                    failed(type(error).__name__)
                await asyncio.sleep(min(cfg.request_interval_s, max(0, deadline - time.monotonic())))

    async def sse_client(index: int, slow: bool) -> None:
        async with clients[cfg.api_clients + index] as client:
            attempts = 0
            while time.monotonic() < deadline:
                attempts += 1
                if attempts > 1:
                    state["reconnects"] += 1
                before = time.perf_counter()
                try:
                    reconnect_at = min(deadline, time.monotonic() + cfg.reconnect_interval_s)
                    async with client.stream("GET", cfg.sse_url) as response:
                        if response.status_code != 200:
                            failed(f"sse_{response.status_code}")
                            await asyncio.sleep(cfg.request_interval_s)
                            continue
                        if len(connects) < cfg.max_samples:
                            connects.append((time.perf_counter() - before) * 1000)
                        state["sse_connections"] += 1
                        async for line in response.aiter_lines():
                            if time.monotonic() >= reconnect_at:
                                break
                            if line.startswith("data:"):
                                state["sse_events"] += 1
                                if slow:
                                    state["slow_events"] += 1
                                    await asyncio.sleep(cfg.slow_read_s)
                                try:
                                    data = json.loads(line[5:])
                                    if data.get("benchmark_sent_at") is not None and len(deliveries) < cfg.max_samples:
                                        deliveries.append(
                                            max(0, (time.time() - float(data["benchmark_sent_at"])) * 1000)
                                        )
                                except (ValueError, TypeError, AttributeError):
                                    failed("invalid_event")
                except httpx.HTTPError as error:
                    failed(type(error).__name__)
                    await asyncio.sleep(cfg.request_interval_s)

    await asyncio.gather(
        *(api_client(n) for n in range(cfg.api_clients)),
        *(sse_client(n, n < cfg.slow_clients) for n in range(cfg.sse_clients)),
    )
    report = {
        "finished_utc": datetime.now(UTC).isoformat(),
        "actual_duration_s": time.monotonic() - start,
        "requested_duration_s": cfg.duration_s,
        "client_setup_duration_s": client_setup_duration,
        "api_clients": cfg.api_clients,
        "sse_clients": cfg.sse_clients,
        "slow_clients": cfg.slow_clients,
        "latency_sample_limit": cfg.max_samples,
        **state,
        "errors": errors,
        "api_latency": percentiles(latencies),
        "sse_connect_latency": percentiles(connects),
        "event_delivery_latency": percentiles(deliveries),
        "limitations": (
            "Loopback public reads only; intentional slow readers are not proof of network queue eviction. "
            "No million-user/SLO claim."
        ),
    }
    await asyncio.to_thread(atomic_json, cfg.report, report)
    return report


async def main(config_path: Path) -> None:
    cfg = HttpConfig.model_validate_json(await asyncio.to_thread(config_path.read_text, encoding="utf-8"))
    print(json.dumps(await benchmark(cfg)), flush=True)


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1])))
