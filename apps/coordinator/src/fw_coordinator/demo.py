"""The public demo: presets and caps from config/demo.yaml, a capped "demo run", adversity switches a
visitor may flip, and a reset loop that puts the board back to its idle preset. Every cap is
enforced here, server-side, whatever a browser sends."""

from __future__ import annotations

import asyncio
import contextlib
import logging
from pathlib import Path
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator
from redis.asyncio import Redis

from fw_core.data import load_yaml
from fw_core.settings import BoardClientSettings, DemoSettings
from fw_queue import keys

log = logging.getLogger(__name__)

RUN_KEYS = ("feed_rate_per_min",)


class Cap(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max: float | None = None
    choices: list[str] | None = None

    @model_validator(mode="after")
    def _one(self) -> Cap:
        if (self.max is None) == (self.choices is None):
            raise ValueError("a cap needs exactly one of max or choices")
        return self


class SeedFilter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    origin: str = "Any"
    destination: str = "Any"
    min_rate_usd: int = Field(default=0, ge=0)


class SeedWindow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    days: list[int]
    start: str
    end: str


class SeedSchedule(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    timezone: str
    windows: list[SeedWindow]
    filters: list[str]


class SeedCell(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    region: str
    capacity: int = Field(gt=0)


class DemoSeed(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tenant_name: str
    cell: SeedCell
    demo_user_name: str
    board_accounts: int = Field(ge=1, le=50)
    filters: list[SeedFilter]
    schedules: list[SeedSchedule] = []


class DemoConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idle: dict[str, Any]
    run: dict[str, Any]
    adversity: dict[str, Cap]
    seed: DemoSeed

    def check_adversity(self, changes: dict[str, Any]) -> dict[str, Any]:
        """Returns the accepted changes or raises ValueError naming the first one outside its cap."""
        accepted: dict[str, Any] = {}
        for name, value in changes.items():
            cap = self.adversity.get(name)
            if cap is None:
                raise ValueError(f"{name} cannot be changed in the demo")
            if cap.choices is not None:
                if value not in cap.choices:
                    raise ValueError(f"{name} must be one of {cap.choices}")
            elif isinstance(value, bool) or not isinstance(value, int | float) or not 0 <= value <= (cap.max or 0):
                raise ValueError(f"{name} must be a number from 0 to {cap.max}")
            accepted[name] = value
        return accepted


def load_demo(config_dir: Path) -> DemoConfig:
    return load_yaml(config_dir, "demo.yaml", DemoConfig)


class RunActive(Exception):
    """A demo run is already going; runs do not stack or extend."""


class Demo:
    """Talks to the board's admin API. State that must survive a restart lives in core Redis."""

    def __init__(
        self, cfg: DemoSettings, data: DemoConfig, board: BoardClientSettings, redis: Redis, http: httpx.AsyncClient
    ) -> None:
        self.cfg = cfg
        self.data = data
        self.redis = redis
        self.http = http
        self.base = board.internal_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {board.admin_token.get_secret_value()}"}

    async def _patch(self, changes: dict[str, Any]) -> dict[str, Any]:
        reply = await self.http.patch(f"{self.base}/admin/settings", json=changes, headers=self.headers)
        reply.raise_for_status()
        return dict(reply.json())

    async def board_settings(self) -> dict[str, Any]:
        reply = await self.http.get(f"{self.base}/admin/settings", headers=self.headers)
        reply.raise_for_status()
        return dict(reply.json())

    async def status(self) -> dict[str, Any]:
        run_ttl = await self.redis.ttl(keys.demo_run())
        current = await self.board_settings()
        return {
            "run_active": run_ttl > 0,
            "run_ends_in_s": max(run_ttl, 0),
            "run_max_minutes": self.cfg.run_max_minutes,
            "reset_after_s": self.cfg.reset_after_s,
            "feed_rate_per_min": current.get("feed_rate_per_min"),
            "adversity": {name: current.get(name) for name in self.data.adversity},
            "caps": {name: cap.model_dump(exclude_none=True) for name, cap in self.data.adversity.items()},
        }

    async def start_run(self) -> dict[str, Any]:
        run = {k: v for k, v in self.data.run.items() if k in RUN_KEYS}
        run["feed_rate_per_min"] = min(float(run.get("feed_rate_per_min", 0)), self.cfg.run_max_rate_per_min)
        # Claim the run first and atomically, so two visitors pressing at once start one run, and a run
        # cannot be kept going forever by pressing again before it ends.
        if not await self.redis.set(keys.demo_run(), "1", ex=self.cfg.run_max_minutes * 60, nx=True):
            raise RunActive
        try:
            await self._patch(run)
        except BaseException:
            await self.redis.delete(keys.demo_run())
            raise
        await self.redis.set(keys.demo_run_dirty(), "1")
        return await self.status()

    async def change_adversity(self, changes: dict[str, Any]) -> dict[str, Any]:
        accepted = self.data.check_adversity(changes)
        if accepted:
            await self._patch(accepted)
            async with self.redis.pipeline(transaction=True) as pipe:
                pipe.set(keys.demo_changed(), "1", ex=self.cfg.reset_after_s)
                pipe.set(keys.demo_adversity_dirty(), "1")
                await pipe.execute()
        return await self.status()

    async def reset_due(self) -> list[str]:
        """Restores idle presets whose time is up. Returns which parts were reset."""
        done = []
        if not await self.redis.exists(keys.demo_run()) and await self.redis.exists(keys.demo_run_dirty()):
            await self._patch({k: self.data.idle[k] for k in RUN_KEYS if k in self.data.idle})
            await self.redis.delete(keys.demo_run_dirty())
            done.append("run")
        if not await self.redis.exists(keys.demo_changed()) and await self.redis.exists(keys.demo_adversity_dirty()):
            await self._patch({k: v for k, v in self.data.idle.items() if k not in RUN_KEYS})
            await self.redis.delete(keys.demo_adversity_dirty())
            done.append("adversity")
        return done

    async def reset_loop(self, every_s: float, stopping: asyncio.Event) -> None:
        while not stopping.is_set():
            try:
                reset = await self.reset_due()
                if reset:
                    log.info("demo reset", extra={"parts": reset})
            except (httpx.HTTPError, OSError):
                log.warning("demo reset failed; will retry")
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(stopping.wait(), every_s)
